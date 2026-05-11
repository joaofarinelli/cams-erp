"""Edge YOLO pre-filter for the agent (runs on the PDV PC, before any clip is
uploaded to the cloud).

Uses onnxruntime + a bundled yolov8n.onnx (~12MB). When a motion event fires,
we read the first frame from the just-recorded clip, run YOLO, and decide:

  * no person at all          -> skip upload + skip /events
  * person detected, no zone  -> upload (whole-frame zone)
  * person detected, in zone  -> upload
  * person detected, no zone hit -> skip

Cuts cloud bandwidth, S3 cost, and VLM tokens by 70-90% on typical PDV cams.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_PERSON_CLASS_ID = 0  # 'person' in COCO


def _bundled_path(filename: str) -> Path:
    """Resolve a path inside the PyInstaller bundle (or source dir in dev)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return Path(base) / filename


class EdgeYolo:
    """Thin onnxruntime wrapper around yolov8n.onnx. Threadsafe per-call."""

    def __init__(
        self,
        model_path: str | os.PathLike | None = None,
        *,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        input_size: int = 640,
    ) -> None:
        import onnxruntime as ort  # local import: optional dep

        path = Path(model_path) if model_path else _bundled_path("yolov8n.onnx")
        if not path.exists():
            raise FileNotFoundError(f"yolov8n.onnx not found at {path}")

        # CPUExecutionProvider always; ONNX Runtime auto-picks OpenVINO/DirectML
        # if installed. We keep the build CPU-only to avoid GPU driver surprises.
        so = ort.SessionOptions()
        so.log_severity_level = 3  # warnings only
        self._session = ort.InferenceSession(str(path), sess_options=so, providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name
        self.conf = conf_threshold
        self.iou = iou_threshold
        self.size = input_size

    @staticmethod
    def _letterbox(img: np.ndarray, new_size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Resize keeping aspect ratio + pad to new_size x new_size. Returns
        (padded_image, scale, (pad_x, pad_y))."""
        h, w = img.shape[:2]
        scale = min(new_size / h, new_size / w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((new_size, new_size, 3), 114, dtype=np.uint8)
        pad_x = (new_size - nw) // 2
        pad_y = (new_size - nh) // 2
        canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized
        return canvas, scale, (pad_x, pad_y)

    @staticmethod
    def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
        """Greedy NMS. boxes is (N,4) xyxy in pixel space."""
        if boxes.size == 0:
            return []
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1).clip(min=0) * (y2 - y1).clip(min=0)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            if order.size == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
            order = order[1:][iou <= iou_thr]
        return keep

    def detect_persons(self, frame: np.ndarray) -> list[tuple[float, float, float, float, float]]:
        """Return list of (x1,y1,x2,y2,score) for class 'person' in pixel space."""
        if frame is None or frame.size == 0:
            return []
        img, scale, (pad_x, pad_y) = self._letterbox(frame, self.size)
        # BGR -> RGB, HWC -> CHW, float32 /255
        blob = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        out = self._session.run(None, {self._input_name: blob})[0]  # shape (1, 84, 8400) for v8

        # v8 head: 4 box (cxcywh) + 80 class scores per anchor
        pred = out[0]  # (84, N)
        boxes = pred[:4, :]  # (4, N)
        cls_scores = pred[4:, :]  # (80, N)
        person_scores = cls_scores[_PERSON_CLASS_ID]  # (N,)
        mask = person_scores > self.conf
        if not mask.any():
            return []
        boxes = boxes[:, mask]
        scores = person_scores[mask]

        # cxcywh -> xyxy (still in 640x640 padded space)
        cx, cy, w, h = boxes
        xyxy = np.stack(
            [cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0],
            axis=1,
        )
        # undo letterbox: subtract padding then divide by scale to map to frame coords
        xyxy[:, [0, 2]] -= pad_x
        xyxy[:, [1, 3]] -= pad_y
        xyxy /= scale

        keep = self._nms(xyxy, scores, self.iou)
        H, W = frame.shape[:2]
        out_boxes: list[tuple[float, float, float, float, float]] = []
        for i in keep:
            x1, y1, x2, y2 = xyxy[i]
            out_boxes.append(
                (
                    float(max(0.0, min(W - 1, x1))),
                    float(max(0.0, min(H - 1, y1))),
                    float(max(0.0, min(W - 1, x2))),
                    float(max(0.0, min(H - 1, y2))),
                    float(scores[i]),
                )
            )
        return out_boxes

    def person_in_zone(self, frame: np.ndarray, zones: dict | None) -> tuple[bool, float]:
        """Returns (any_person_in_zone, max_confidence).

        zones is the same dict shape the cloud rules use: {name: [(x,y), ...]}
        with coords normalized 0..1. Empty dict -> whole frame is the zone
        (returns True if any person at all)."""
        boxes = self.detect_persons(frame)
        if not boxes:
            return False, 0.0
        max_conf = max(b[4] for b in boxes)
        if not zones:
            return True, max_conf

        H, W = frame.shape[:2]
        polys: list[np.ndarray] = []
        for pts in zones.values():
            if pts and len(pts) >= 3:
                polys.append(np.array([[p[0] * W, p[1] * H] for p in pts], dtype=np.float32))
        if not polys:
            return True, max_conf  # zone list empty/invalid -> behave like no zone

        for x1, y1, x2, y2, conf in boxes:
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            # Bottom-center (feet) — usually the relevant ground contact point.
            fx, fy = (x1 + x2) / 2.0, y2
            for poly in polys:
                for px, py in ((cx, cy), (fx, fy)):
                    if cv2.pointPolygonTest(poly, (px, py), False) >= 0:
                        return True, conf
        return False, max_conf


_singleton: EdgeYolo | None = None
_singleton_err: Exception | None = None


def get_edge_yolo(conf: float = 0.35) -> EdgeYolo | None:
    """Lazy singleton. Returns None if onnxruntime is missing or model unavailable,
    so callers can degrade gracefully (just skip the filter)."""
    global _singleton, _singleton_err
    if _singleton is not None:
        return _singleton
    if _singleton_err is not None:
        return None
    try:
        _singleton = EdgeYolo(conf_threshold=conf)
        return _singleton
    except Exception as e:  # noqa: BLE001
        _singleton_err = e
        return None


def first_frame_from_clip(path: str | os.PathLike) -> np.ndarray | None:
    """Read the first decodable frame from an mp4 clip on disk."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    try:
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def first_frame_from_jpeg_bytes(jpeg: bytes) -> np.ndarray | None:
    """Decode a JPEG buffer (e.g. straight from an HTTP snapshot) to BGR."""
    if not jpeg:
        return None
    arr = np.frombuffer(jpeg, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)
