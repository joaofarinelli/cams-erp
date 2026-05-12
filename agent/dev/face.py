"""Face recognition scaffolding (whitelist match).

Uses `insightface` (ONNX, CPU) when installed — it's a 50MB dependency,
not pinned in pyproject yet because the bundle size matters for everyone
who doesn't use the feature. Wire path:

  agent.CameraWorker on trigger → face.extract_embeddings(frame)
      → ship embeddings in Event.context
  inference.vlm before VLM call → face.match_whitelist(embeddings, db)
      → if score > 0.8 → alert=False, msg="known: <name>"

When insightface is absent, extract_embeddings returns [] (no-op).
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np


class FaceMatcher:
    _singleton: "FaceMatcher | None" = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "FaceMatcher | None":
        with cls._lock:
            if cls._singleton is None:
                try:
                    cls._singleton = FaceMatcher()
                except Exception:  # noqa: BLE001
                    return None
            return cls._singleton

    def __init__(self) -> None:
        self._app: Any | None = None
        try:
            from insightface.app import FaceAnalysis  # type: ignore

            self._app = FaceAnalysis(providers=["CPUExecutionProvider"])
            self._app.prepare(ctx_id=0, det_size=(640, 640))
        except Exception:  # noqa: BLE001
            self._app = None

    def is_available(self) -> bool:
        return self._app is not None

    def extract_embeddings(self, frame: np.ndarray) -> list[list[float]]:
        if self._app is None or frame is None or frame.size == 0:
            return []
        try:
            faces = self._app.get(frame)
        except Exception:  # noqa: BLE001
            return []
        return [list(map(float, f.embedding)) for f in faces if hasattr(f, "embedding")]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    na = np.array(a, dtype=np.float32)
    nb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(na) * np.linalg.norm(nb)) or 1.0
    return float(np.dot(na, nb) / denom)
