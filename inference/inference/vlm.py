"""Claude Haiku 4.5 vision call. Pydantic-validated structured output."""

from __future__ import annotations

import base64
from typing import Any

import cv2
import numpy as np
from anthropic import Anthropic
from pydantic import BaseModel, Field

from inference.prompts import PRESET_PROMPTS, build_user_text


class AlertResult(BaseModel):
    alert: bool = Field(description="True if suspicious behavior matching the preset is observed.")
    score: float = Field(ge=0.0, le=1.0, description="Confidence 0..1.")
    message: str = Field(description="Short message in Brazilian Portuguese describing the evidence.")
    evidence_frame_idx: int | None = Field(
        default=None, description="Index of the frame that most strongly motivated the decision."
    )


def sample_frames(clip_path: str, n: int = 4) -> list[np.ndarray]:
    """Uniformly sample n frames from clip_path."""
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []
    indices = (
        [int(i * (total - 1) / max(n - 1, 1)) for i in range(n)] if n > 1 else [total // 2]
    )
    out: list[np.ndarray] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok:
            out.append(frame)
    cap.release()
    return out


def encode_frame(frame: np.ndarray, max_long_edge: int = 1024, jpeg_quality: int = 85) -> str:
    h, w = frame.shape[:2]
    long_edge = max(h, w)
    if long_edge > max_long_edge:
        scale = max_long_edge / long_edge
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return base64.standard_b64encode(buf.tobytes()).decode()


def score_clip(
    clip_path: str,
    preset_type: str,
    zones: dict,
    *,
    client: Anthropic | None = None,
    model: str = "claude-haiku-4-5",
    n_frames: int = 4,
) -> AlertResult:
    if preset_type not in PRESET_PROMPTS:
        return AlertResult(alert=False, score=0.0, message=f"unknown preset {preset_type}")

    frames = sample_frames(clip_path, n=n_frames)
    if not frames:
        return AlertResult(alert=False, score=0.0, message="no frames extracted from clip")

    if client is None:
        client = Anthropic()

    cfg = PRESET_PROMPTS[preset_type]
    system = [
        {
            "type": "text",
            "text": cfg["system"],
            "cache_control": {"type": "ephemeral"},
        }
    ]

    content: list[Any] = [{"type": "text", "text": build_user_text(preset_type, zones, len(frames))}]
    for i, frame in enumerate(frames):
        content.append({"type": "text", "text": f"Frame {i}:"})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": encode_frame(frame),
                },
            }
        )

    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_format=AlertResult,
    )
    return response.parsed_output
