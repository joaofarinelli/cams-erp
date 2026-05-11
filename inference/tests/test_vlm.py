from unittest.mock import MagicMock

import numpy as np

from inference import vlm
from inference.vlm import score_clip


def test_yolo_confidence_from_sensitivity_mapping() -> None:
    from inference.worker import _yolo_confidence_from_sensitivity

    assert _yolo_confidence_from_sensitivity(None) == 0.35
    assert _yolo_confidence_from_sensitivity(0) == 0.7
    assert _yolo_confidence_from_sensitivity(50) == 0.4
    assert _yolo_confidence_from_sensitivity(100) == 0.1
    assert _yolo_confidence_from_sensitivity(-50) == 0.7
    assert _yolo_confidence_from_sensitivity(200) == 0.1


def test_is_active_now_handles_overnight_and_none() -> None:
    from inference.worker import _is_active_now

    assert _is_active_now(None) is True
    assert _is_active_now({}) is True
    _is_active_now(
        {"timezone": "America/Sao_Paulo", "windows": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "22:00", "end": "06:00"}]}
    )


def test_score_clip_empty_prompt_returns_no_alert() -> None:
    result = score_clip("/nonexistent.mp4", "", {})
    assert result.alert is False
    assert "empty rule prompt" in result.message


def test_score_clip_skips_vlm_when_yolo_finds_no_person(monkeypatch) -> None:
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    monkeypatch.setattr(vlm, "sample_frames_motion_peak", lambda *_args, **_kw: [fake_frame] * 4)
    monkeypatch.setattr(
        "inference.yolo.person_in_any_zone",
        lambda frames, zones, confidence=0.35: (False, 0.12),
    )

    fake_client = MagicMock()
    result = vlm.score_clip(
        "/x.mp4",
        "Detectar mãos na gaveta",
        {"gaveta": [[0, 0], [1, 0], [1, 1]]},
        client=fake_client,
        yolo_filter=True,
    )
    assert result.alert is False
    assert "no person" in result.message
    fake_client.chat.completions.create.assert_not_called()


def test_score_clip_no_frames_returns_no_alert(monkeypatch) -> None:
    monkeypatch.setattr(vlm, "sample_frames_motion_peak", lambda *_args, **_kw: [])
    result = score_clip("/nonexistent.mp4", "qualquer regra", {})
    assert result.alert is False
    assert "no frames" in result.message
