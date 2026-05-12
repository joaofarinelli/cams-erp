"""VLM call via OpenRouter (default: Qwen3.5-35B-A3B vision).

Provider/model are env-driven so we can swap to Anthropic/Gemini/etc without
touching this file:

  CAMS_VLM_BASE_URL  default https://openrouter.ai/api/v1
  CAMS_VLM_MODEL     default qwen/qwen3.5-35b-a3b
  CAMS_VLM_API_KEY   required (OpenRouter or compatible)
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import cv2
import numpy as np
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from inference.prompts import CUSTOM_SYSTEM, build_user_text


class AlertResult(BaseModel):
    alert: bool = Field(description="True if suspicious behavior matching the rule is observed.")
    score: float = Field(ge=0.0, le=1.0, description="Confidence 0..1.")
    message: str = Field(description="Short message in Brazilian Portuguese describing the evidence.")
    evidence_frame_idx: int | None = Field(
        default=None, description="Index of the frame that most strongly motivated the decision."
    )
    # Token counters propagated from the provider response so the cloud
    # can charge accurately. Populated by `_run_vlm` from completion.usage
    # when available; absent on parse errors.
    tokens_in: int = 0
    tokens_out: int = 0
    cascade_used: bool = False
    yolo_max_conf: float | None = None
    skipped_reason: str | None = None


def sample_frames(clip_path: str, n: int = 4) -> list[np.ndarray]:
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


def sample_frames_motion_peak(clip_path: str, n: int = 4) -> list[np.ndarray]:
    """Pick `n` frames at motion-peak timestamps in temporal order.

    Reads the whole clip (cheap — these are short clips), computes the L1
    delta between consecutive grayscale frames, then keeps the `n` frames
    with the largest delta-to-previous score. Fast actions (drawer open,
    quick bite) ARE motion peaks, so this dominates uniform sampling for
    short events without raising the per-call frame budget.

    Falls back to uniform sampling when the clip is too short to score."""
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        return []
    raw_frames: list[np.ndarray] = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        raw_frames.append(frame)
    cap.release()

    if len(raw_frames) <= n:
        return raw_frames
    if len(raw_frames) < n + 2:
        # Too short for stable peak detection — use uniform.
        idxs = [int(i * (len(raw_frames) - 1) / max(n - 1, 1)) for i in range(n)]
        return [raw_frames[i] for i in idxs]

    # Inter-frame deltas at a small fixed resolution (cheap; ~ms).
    small = [cv2.cvtColor(cv2.resize(f, (160, 90)), cv2.COLOR_BGR2GRAY) for f in raw_frames]
    deltas = [0.0]
    for i in range(1, len(small)):
        deltas.append(float(np.mean(cv2.absdiff(small[i - 1], small[i]))))

    # Top-N peak indices, then sort temporally so frames keep narrative order.
    ranked = sorted(range(len(deltas)), key=lambda i: deltas[i], reverse=True)
    picked = sorted(ranked[:n])
    return [raw_frames[i] for i in picked]


_ZONE_COLORS_BGR = [
    (255, 80, 0),   # blue
    (0, 80, 255),   # red
    (0, 200, 80),   # green
    (0, 200, 200),  # yellow
    (200, 0, 200),  # magenta
    (200, 200, 0),  # cyan
]


def overlay_zones(frame: np.ndarray, zones: dict) -> np.ndarray:
    """Draw filled translucent polygons + labels onto a copy of `frame`.

    Coords in `zones` are normalized 0..1 (poly per zone). Overlaying inside
    the JPEG that goes to the VLM is more reliable than passing raw numbers
    in text — small models grasp 'this colored area' visually without having
    to map normalized coordinates onto the image.
    """
    if not zones:
        return frame
    h, w = frame.shape[:2]
    overlay = frame.copy()
    for i, (name, pts) in enumerate(zones.items()):
        if not pts or len(pts) < 3:
            continue
        color = _ZONE_COLORS_BGR[i % len(_ZONE_COLORS_BGR)]
        poly = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts], dtype=np.int32)
        cv2.fillPoly(overlay, [poly], color)
        cv2.polylines(frame, [poly], isClosed=True, color=color, thickness=2)
        cx, cy = int(poly[:, 0].mean()), int(poly[:, 1].mean())
        cv2.putText(
            frame,
            name,
            (cx - 30, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return cv2.addWeighted(overlay, 0.35, frame, 0.65, 0)


def encode_frame(frame: np.ndarray, max_long_edge: int = 512, jpeg_quality: int = 80) -> str:
    h, w = frame.shape[:2]
    long_edge = max(h, w)
    if long_edge > max_long_edge:
        scale = max_long_edge / long_edge
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return base64.standard_b64encode(buf.tobytes()).decode()


def _client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("CAMS_VLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY", ""),
        base_url=os.environ.get("CAMS_VLM_BASE_URL", "https://openrouter.ai/api/v1"),
        default_headers={
            "HTTP-Referer": os.environ.get("CAMS_VLM_REFERER", "https://cams-erp-api.fly.dev"),
            "X-Title": "cams-erp",
        },
    )


_RESULT_SCHEMA = {
    "name": "AlertResult",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "alert": {"type": "boolean"},
            "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "message": {"type": "string"},
            "evidence_frame_idx": {"type": ["integer", "null"]},
        },
        "required": ["alert", "score", "message", "evidence_frame_idx"],
    },
}


def _parse_result(raw: str) -> AlertResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        s = raw.strip()
        if s.startswith("```"):
            s = s.strip("`")
            s = s.split("\n", 1)[1] if "\n" in s else s
            s = s.rsplit("```", 1)[0] if "```" in s else s
        data = json.loads(s)
    return AlertResult(**data)


# Per-intensity profiles. Critical rules (e.g. "ate hidden") get more frames
# and longer effective context; passive monitors get the cheap path.
_INTENSITY_PROFILES: dict[str, dict[str, Any]] = {
    "light":  {"n_frames": 2, "cascade_min": 0.40, "cascade_max": 0.75},
    "normal": {"n_frames": 4, "cascade_min": 0.35, "cascade_max": 0.70},
    "strict": {"n_frames": 6, "cascade_min": 0.30, "cascade_max": 0.80},
}


def _run_vlm(
    client: OpenAI,
    model: str,
    frames: list[np.ndarray],
    zones: dict,
    custom_prompt: str,
) -> AlertResult:
    user_text = build_user_text(custom_prompt, zones, len(frames))
    rendered_frames = [overlay_zones(f, zones) for f in frames]

    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for i, frame in enumerate(rendered_frames):
        user_content.append({"type": "text", "text": f"Frame {i}:"})
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encode_frame(frame)}"},
            }
        )

    messages = [
        {"role": "system", "content": CUSTOM_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
            temperature=0.0,
            response_format={"type": "json_schema", "json_schema": _RESULT_SCHEMA},
        )
    except Exception:
        messages[0]["content"] = (
            CUSTOM_SYSTEM
            + "\n\nResponda APENAS um JSON valido com chaves:"
            ' {"alert": bool, "score": 0..1, "message": str, "evidence_frame_idx": int|null}.'
        )
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=512,
            temperature=0.0,
        )

    raw = completion.choices[0].message.content or "{}"
    tin = getattr(getattr(completion, "usage", None), "prompt_tokens", 0) or 0
    tout = getattr(getattr(completion, "usage", None), "completion_tokens", 0) or 0
    try:
        result = _parse_result(raw)
        result.tokens_in = int(tin)
        result.tokens_out = int(tout)
        return result
    except (json.JSONDecodeError, ValidationError) as e:
        r = AlertResult(alert=False, score=0.0, message=f"vlm parse error: {e}; raw={raw[:120]}")
        r.tokens_in = int(tin)
        r.tokens_out = int(tout)
        return r


def _sample_frames_uniform(clip_path: str, n: int) -> list[np.ndarray]:
    """Uniform-time sampling. Used together with motion-peak sampling when YOLO
    pre-filter is disabled, to raise the chance of catching a slow-entering
    person whose presence isn't a motion peak."""
    if n <= 0:
        return []
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


def score_clip(
    clip_path: str,
    custom_prompt: str,
    zones: dict,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
    n_frames: int | None = None,
    yolo_filter: bool = True,
    yolo_confidence: float = 0.35,
    intensity: str = "normal",
    cascade_model: str | None = None,
) -> AlertResult:
    if not custom_prompt or not custom_prompt.strip():
        return AlertResult(alert=False, score=0.0, message="empty rule prompt")

    profile = _INTENSITY_PROFILES.get(intensity, _INTENSITY_PROFILES["normal"])
    effective_n = n_frames if n_frames is not None else profile["n_frames"]

    if yolo_filter:
        frames = sample_frames_motion_peak(clip_path, n=effective_n)
    else:
        # Mix motion-peak with uniform-time samples so we catch slow entries
        # (which don't register as motion peaks). Dedup picks unique frames
        # by id() since frames are independent ndarrays.
        half = max(1, effective_n // 2)
        peak = sample_frames_motion_peak(clip_path, n=half)
        uniform = _sample_frames_uniform(clip_path, n=effective_n - len(peak))
        frames = (peak + uniform)[:effective_n]
    if not frames:
        return AlertResult(alert=False, score=0.0, message="no frames extracted from clip")

    if yolo_filter:
        from inference.yolo import person_in_any_zone

        found, max_conf = person_in_any_zone(frames, zones, confidence=yolo_confidence)
        if not found:
            return AlertResult(
                alert=False,
                score=0.0,
                message=f"yolo: no person in zone (max_conf={max_conf:.2f}); skipped VLM",
                yolo_max_conf=float(max_conf),
                skipped_reason="yolo_no_person",
            )

    if client is None:
        client = _client()
    stage1_model = model or os.environ.get("CAMS_VLM_MODEL", "google/gemini-2.0-flash-lite-001")

    result = _run_vlm(client, stage1_model, frames, zones, custom_prompt)

    cascade_model = cascade_model or os.environ.get("CAMS_VLM_CASCADE_MODEL")
    if (
        cascade_model
        and not result.alert  # only re-roll when stage1 said False but ambiguous
        and profile["cascade_min"] <= result.score <= profile["cascade_max"]
    ):
        # Re-run with stronger model + 50% more frames for hard cases.
        bigger_n = min(effective_n + 2, 8)
        bigger_frames = sample_frames_motion_peak(clip_path, n=bigger_n)
        if bigger_frames:
            stage2 = _run_vlm(client, cascade_model, bigger_frames, zones, custom_prompt)
            stage2.message = f"[cascade] {stage2.message}"
            stage2.cascade_used = True
            # Carry stage 1 tokens too so caller can bill total VLM usage.
            stage2.tokens_in += result.tokens_in
            stage2.tokens_out += result.tokens_out
            return stage2

    return result
