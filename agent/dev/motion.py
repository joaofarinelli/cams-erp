"""Per-camera background-subtraction motion detector.

Replaces the old `motion_score(prev_gray, gray)` heuristic (frame-diff
between consecutive samples) with cv2.createBackgroundSubtractorMOG2,
which keeps a running model of the scene. Two practical wins:

1. A person who walks in and then stays still still triggers — frame
   diff goes to 0 once they stop, but MOG2 keeps them as "foreground"
   for ~history frames.
2. Gradual lighting changes (sunset, fluorescent flicker) are absorbed
   into the background model and don't fire false alerts.

Each CameraWorker owns its own `MotionDetector` so the model is per-cam.
Output is normalized 0..1 (fraction of pixels marked as foreground)
so the existing motion_threshold (default 0.02) keeps working.
"""

from __future__ import annotations

import cv2
import numpy as np


class MotionDetector:
    def __init__(
        self,
        *,
        history: int = 200,
        var_threshold: int = 16,
        detect_shadows: bool = True,
        warmup_frames: int = 5,
    ) -> None:
        self._bg = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=detect_shadows,
        )
        self._frames_seen = 0
        self._warmup = warmup_frames

    def process(self, gray: np.ndarray) -> float:
        """Returns motion score in [0, 1]. During warmup returns 0 so the
        model has time to learn the static scene before we start triggering."""
        if gray.ndim != 2:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        mask = self._bg.apply(gray)
        self._frames_seen += 1
        if self._frames_seen <= self._warmup:
            return 0.0
        # Strip "shadow" pixels (value 127 when detectShadows=True) so we
        # only count true foreground.
        fg = (mask >= 200).astype(np.uint8)
        return float(fg.mean())

    def reset(self) -> None:
        self._bg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=16)
        self._frames_seen = 0
