"""YOLOv8n person detector — cheap pre-filter for the VLM stage.

If no person is visible across the sampled frames, the VLM call is skipped
entirely. Cuts ~70-90% of cost on cameras pointed at empty scenes.
"""

from __future__ import annotations

import threading
from typing import Any

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
