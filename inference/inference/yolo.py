"""YOLOv8n person detector — cheap pre-filter for the VLM stage.

If no person is visible across the sampled frames, the VLM call is skipped
entirely. Cuts ~70-90% of cost on cameras pointed at empty scenes.
"""

from __future__ import annotations

import threading
from typing import Any

import cv2
import numpy as np

_PERSON_CLASS_ID = 0  # 'person' in the COCO classes used by yolov8

_model_lock = threading.Lock()
_model: Any | None = None


def _get_model() -> Any:
    """Lazy-load yolov8n. First call downloads weights to ~/.config/ultralytics."""
    global _model
    with _model_lock:
        if _model is None:
            from ultralytics import YOLO

            _model = YOLO("yolov8n.pt")
        return _model


def has_person(frames: list[np.ndarray], confidence: float = 0.35) -> tuple[bool, float]:
    """Return (any_person, max_confidence) across frames.

    confidence is the per-detection threshold passed to YOLO. Lower values
    flag more frames as containing a person (false positives toward the VLM
    stage, which is desired — cheap filter, expensive verifier)."""
    if not frames:
        return False, 0.0
    model = _get_model()
    # Single batched inference — much faster than per-frame.
    results = model.predict(frames, classes=[_PERSON_CLASS_ID], conf=confidence, verbose=False)
    max_conf = 0.0
    found = False
    for res in results:
        if res.boxes is None or len(res.boxes) == 0:
            continue
        confs = res.boxes.conf.cpu().numpy().tolist()
        if confs:
            found = True
            max_conf = max(max_conf, max(confs))
    return found, max_conf


def person_in_any_zone(
    frames: list[np.ndarray],
    zones: dict,
    *,
    confidence: float = 0.35,
) -> tuple[bool, float]:
    """Return (any_bbox_intersects_zone, max_conf_of_overlapping_box).

    Zones are normalized polygons {name: [(x,y), ...]} with coords in 0..1.
    Used as a cheap pre-filter before the VLM: if YOLO sees a person but
    nobody is anywhere near a rule's zone, skip the VLM call entirely.

    Empty `zones` -> treat as "whole frame is the zone" (returns same as
    `has_person`)."""
    if not frames:
        return False, 0.0
    if not zones:
        return has_person(frames, confidence=confidence)

    model = _get_model()
    results = model.predict(frames, classes=[_PERSON_CLASS_ID], conf=confidence, verbose=False)
    max_conf = 0.0
    found = False
    for frame, res in zip(frames, results, strict=False):
        if res.boxes is None or len(res.boxes) == 0:
            continue
        h, w = frame.shape[:2]
        # Pixel-space polygons for this frame.
        polys = []
        for pts in zones.values():
            if pts and len(pts) >= 3:
                polys.append(np.array([[p[0] * w, p[1] * h] for p in pts], dtype=np.float32))
        if not polys:
            continue
        xyxy = res.boxes.xyxy.cpu().numpy()
        confs = res.boxes.conf.cpu().numpy()
        for (x1, y1, x2, y2), conf in zip(xyxy, confs, strict=False):
            # Test bbox center + bottom-center (feet) against each zone polygon.
            probes = [
                ((x1 + x2) / 2, (y1 + y2) / 2),
                ((x1 + x2) / 2, y2),
            ]
            hit = False
            for poly in polys:
                for px, py in probes:
                    if cv2.pointPolygonTest(poly, (float(px), float(py)), False) >= 0:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                found = True
                max_conf = max(max_conf, float(conf))
    return found, max_conf
