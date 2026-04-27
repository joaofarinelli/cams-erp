from unittest.mock import MagicMock

import numpy as np

from inference import vlm
from inference.vlm import AlertResult, score_clip


def _fake_response(parsed: AlertResult) -> MagicMock:
    resp = MagicMock()
    resp.parsed_output = parsed
    return resp


def test_score_clip_unknown_preset_returns_no_alert() -> None:
    result = score_clip("/nonexistent.mp4", "wat", {})
    assert result.alert is False
    assert "unknown preset" in result.message


def test_score_clip_no_frames_returns_no_alert(monkeypatch) -> None:
    monkeypatch.setattr(vlm, "sample_frames", lambda *_args, **_kw: [])
    result = score_clip("/nonexistent.mp4", "cash_register", {"gaveta": [[0, 0], [1, 0], [1, 1]]})
    assert result.alert is False
    assert "no frames" in result.message


def test_score_clip_with_custom_prompt_uses_custom_system(monkeypatch) -> None:
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    monkeypatch.setattr(vlm, "sample_frames", lambda *_args, **_kw: [fake_frame] * 4)

    fake_client = MagicMock()
    fake_client.messages.parse.return_value = _fake_response(
        AlertResult(alert=True, score=0.77, message="Bateu na bancada com a mao no frame 1", evidence_frame_idx=1)
    )

    result = score_clip(
        "/x.mp4",
        "cash_register",
        {},
        custom_prompt="Toda vez que alguem bate no balcao com a mao",
        client=fake_client,
    )
    assert result.alert is True
    assert result.evidence_frame_idx == 1

    call_args = fake_client.messages.parse.call_args
    system_text = call_args.kwargs["system"][0]["text"]
    assert "regra customizada" in system_text.lower()
    user_text = call_args.kwargs["messages"][0]["content"][0]["text"]
    assert "Toda vez que alguem bate no balcao com a mao" in user_text


def test_score_clip_calls_anthropic_and_returns_parsed(monkeypatch) -> None:
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    monkeypatch.setattr(vlm, "sample_frames", lambda *_args, **_kw: [fake_frame] * 4)

    fake_client = MagicMock()
    fake_client.messages.parse.return_value = _fake_response(
        AlertResult(alert=True, score=0.88, message="Mao na gaveta no frame 2", evidence_frame_idx=2)
    )

    result = score_clip(
        "/x.mp4",
        "cash_register",
        {"gaveta": [[0, 0], [1, 0], [1, 1]], "pc_operador": [[0, 0], [1, 0], [1, 1]]},
        client=fake_client,
    )

    assert result.alert is True
    assert result.score == 0.88
    assert result.evidence_frame_idx == 2

    call_args = fake_client.messages.parse.call_args
    assert call_args.kwargs["model"] == "claude-haiku-4-5"
    system = call_args.kwargs["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    user_content = call_args.kwargs["messages"][0]["content"]
    image_blocks = [b for b in user_content if isinstance(b, dict) and b.get("type") == "image"]
    assert len(image_blocks) == 4
    assert image_blocks[0]["source"]["media_type"] == "image/jpeg"
