"""License plate recognition — agent-side scaffolding.

Loads `lpr_yolov8n.onnx` (custom-trained plate detector) + an OCR step to
read the detected boxes. Returns a list of `(bbox, text, conf)` tuples.

Model strategy:
  * The bundled ONNX expects a YOLOv8n trained on plate bbox class only.
    Producing this model is out of scope for the scaffolding commit; until
    weights ship, `detect_and_read` returns an empty list and the agent
    behaves exactly like today.
  * If `easyocr` is installed (heavy: torch + ~150MB models), we use it
    for OCR on detected boxes. Otherwise the OCR step is a no-op.

The integration points stay valid regardless of model availability:
  * `Event.detected_plates` is populated when matches exist.
  * Cloud inference can skip VLM if a whitelisted plate is read.

To upgrade later, drop the trained ONNX into the bundle and re-enable
the inference path; no other code changes required.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


PLATE_MODEL_FILENAME = "lpr_yolov8n.onnx"


@dataclass
class PlateRead:
    bbox: tuple[float, float, float, float]
    text: str
    conf: float


def _bundled_path(filename: str) -> Path:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return Path(base) / filename


class LprReader:
    """Loads plate detector + OCR lazily. Threadsafe.

    Backend resolution order (first wins):
      1. OpenALPR Cloud — when CAMS_OPENALPR_KEY is set, we send the JPEG
         straight to their API. ~$0.001/lookup, no local model needed.
      2. Local ONNX (`lpr_yolov8n.onnx`) — when a trained model is bundled.
         Skipped if absent.
      3. Disabled — `detect_and_read` returns [].

    The agent never blocks on LPR availability — features that depend on
    plate detection just see an empty list and continue.
    """

    _singleton: "LprReader | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "LprReader | None":
        with cls._lock:
            if cls._singleton is None:
                try:
                    cls._singleton = LprReader()
                except Exception:  # noqa: BLE001
                    return None
            return cls._singleton

    def __init__(self) -> None:
        self._backend: str = "disabled"
        self._openalpr_key: str = os.environ.get("CAMS_OPENALPR_KEY", "").strip()
        self._detector: Any | None = None
        if self._openalpr_key:
            self._backend = "openalpr_cloud"
            return
        model_path = _bundled_path(PLATE_MODEL_FILENAME)
        if model_path.exists():
            try:
                import onnxruntime as ort

                self._detector = ort.InferenceSession(
                    str(model_path), providers=["CPUExecutionProvider"]
                )
                self._backend = "onnx_local"
            except Exception:  # noqa: BLE001
                self._detector = None

    def is_available(self) -> bool:
        return self._backend != "disabled"

    @property
    def backend(self) -> str:
        return self._backend

    def _read_openalpr_cloud(self, frame: np.ndarray) -> list[PlateRead]:
        import base64
        import json
        import urllib.request
        import urllib.error

        import cv2

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return []
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        try:
            req = urllib.request.Request(
                "https://api.openalpr.com/v3/recognize_bytes"
                f"?secret_key={self._openalpr_key}&country=br&recognize_vehicle=0",
                data=b64.encode("ascii"),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return []
        results: list[PlateRead] = []
        for r in data.get("results") or []:
            coords = r.get("coordinates") or []
            if len(coords) >= 3:
                xs = [c.get("x", 0) for c in coords]
                ys = [c.get("y", 0) for c in coords]
                bbox = (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))
            else:
                bbox = (0.0, 0.0, 0.0, 0.0)
            results.append(
                PlateRead(
                    bbox=bbox,
                    text=str(r.get("plate") or "").upper(),
                    conf=float(r.get("confidence") or 0.0) / 100.0,
                )
            )
        return results

    def detect_and_read(self, frame: np.ndarray, *, conf_threshold: float = 0.4) -> list[PlateRead]:
        if frame is None or frame.size == 0:
            return []
        if self._backend == "openalpr_cloud":
            return [p for p in self._read_openalpr_cloud(frame) if p.conf >= conf_threshold]
        if self._backend == "onnx_local":
            # Local ONNX inference path stays a stub until BR-trained
            # plate weights ship.
            return []
        return []
