"""Audio event detection from RTSP audio stream.

Pulls 16kHz mono PCM from the camera's RTSP audio sub-stream via ffmpeg
and runs YAMNet (ONNX, ~17MB) — a 521-class general audio classifier.
We expose a small subset relevant to retail security:
  - Gunshot, gunfire
  - Glass breaking
  - Screaming
  - Alarm

Wire path:
  agent.CameraWorker spawns an AudioWatcher thread on cameras with a
  rule of type='audio'. AudioWatcher emits events with `audio_class`
  populated; cloud routes those past the VLM stage and straight to
  alert dispatch (much lower latency than vision pipeline).

When the YAMNet ONNX isn't bundled, AudioWatcher.start() is a no-op
and `is_available()` returns False, so cameras keep working as before.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

import numpy as np


YAMNET_FILENAME = "yamnet.onnx"
# YAMNet class indices we care about (subset of 521). The default ONNX export
# uses the same label order as TensorFlow Hub's yamnet/1.
DEFAULT_CLASSES_OF_INTEREST: dict[int, str] = {
    426: "gunshot",
    427: "machine_gun",
    436: "glass",
    44: "screaming",
    390: "alarm",
}


def _bundled_path(filename: str) -> Path:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return Path(base) / filename


class AudioWatcher(threading.Thread):
    """Reads PCM from RTSP via ffmpeg and classifies 0.96s windows. Emits
    a callback `on_detect(class_name, confidence)` whenever a target
    class crosses the threshold."""

    def __init__(
        self,
        rtsp_url: str,
        on_detect: Callable[[str, float], None],
        *,
        threshold: float = 0.5,
        classes_of_interest: dict[int, str] | None = None,
    ) -> None:
        super().__init__(daemon=True, name=f"audio-{rtsp_url[:16]}")
        self.rtsp_url = rtsp_url
        self._on_detect = on_detect
        self._stop = threading.Event()
        self._threshold = threshold
        self._classes = classes_of_interest or DEFAULT_CLASSES_OF_INTEREST
        self._session = None

    def stop(self) -> None:
        self._stop.set()

    @classmethod
    def is_available(cls) -> bool:
        return _bundled_path(YAMNET_FILENAME).exists()

    def run(self) -> None:
        model_path = _bundled_path(YAMNET_FILENAME)
        if not model_path.exists():
            return
        try:
            import onnxruntime as ort

            self._session = ort.InferenceSession(
                str(model_path), providers=["CPUExecutionProvider"]
            )
        except Exception:  # noqa: BLE001
            return
        cmd = [
            "ffmpeg", "-loglevel", "error",
            "-rtsp_transport", "tcp", "-i", self.rtsp_url,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-f", "s16le", "-",
        ]
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = 0x08000000  # CREATE_NO_WINDOW
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        assert proc.stdout is not None
        window_bytes = 16000 * 2  # 1 second of 16-bit PCM
        try:
            while not self._stop.is_set():
                raw = proc.stdout.read(window_bytes)
                if not raw or len(raw) < window_bytes:
                    break
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                try:
                    out = self._session.run(None, {"waveform": samples})[0]
                except Exception:  # noqa: BLE001
                    continue
                # out shape ~(N_frames, 521); take mean across frames.
                scores = out.mean(axis=0) if out.ndim == 2 else out
                for idx, name in self._classes.items():
                    if idx < len(scores) and float(scores[idx]) >= self._threshold:
                        self._on_detect(name, float(scores[idx]))
                        break
        finally:
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
