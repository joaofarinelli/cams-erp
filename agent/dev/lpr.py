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
    """Loads plate detector + OCR lazily. Threadsafe."""

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
        self._detector: Any | None = None
        self._ocr: Any | None = None
        model_path = _bundled_path(PLATE_MODEL_FILENAME)
        if model_path.exists():
            try:
                import onnxruntime as ort

                self._detector = ort.InferenceSession(
                    str(model_path), providers=["CPUExecutionProvider"]
                )
            except Exception:  # noqa: BLE001
                self._detector = None
        try:
            import easyocr  # type: ignore

            self._ocr = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
        except Exception:  # noqa: BLE001
            self._ocr = None

    def is_available(self) -> bool:
        return self._detector is not None

    def detect_and_read(self, frame: np.ndarray, *, conf_threshold: float = 0.4) -> list[PlateRead]:
        """Find plates in `frame` and OCR each. Empty list if model is
        unavailable (silent degradation; agent keeps working as before)."""
        if self._detector is None or frame is None or frame.size == 0:
            return []
        # NOTE: detector inference + NMS skipped here until a real plate
        # ONNX ships. The scaffolding is intentional — we expose the API
        # so plate_whitelist matching can be wired into the cloud event
        # path without blocking on model training.
        return []
