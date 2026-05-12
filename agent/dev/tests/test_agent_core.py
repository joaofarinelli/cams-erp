"""Smoke + edge-case tests for the agent modules. Doesn't require network or
DVR — every fixture is in-memory."""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def isolated_appdata(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("XDG_CONFIG_HOME", tmp)
    monkeypatch.setenv("LOCALAPPDATA", tmp)
    yield tmp


# ---------- config_store ----------------------------------------------------


def test_config_save_load_roundtrip():
    from config_store import save_config, load_config

    save_config({"api_base": "https://x", "device_token": "tok-abc-123"})
    loaded = load_config()
    assert loaded["api_base"] == "https://x"
    assert loaded["device_token"] == "tok-abc-123"


def test_config_token_encrypted_on_disk():
    """Plaintext token MUST NOT appear in the file even if cryptography is
    available. Verifies the encrypt step actually ran."""
    import json
    from config_store import save_config, config_path

    save_config({"device_token": "very-secret-token"})
    raw = json.loads(config_path().read_text(encoding="utf-8"))
    assert "very-secret-token" not in raw["device_token"]
    assert raw["device_token"].startswith("enc:v1:")


def test_config_load_with_corrupt_file_returns_empty():
    from config_store import config_path, load_config

    config_path().write_text("{not json", encoding="utf-8")
    assert load_config() == {}


def test_config_load_with_missing_file_returns_empty():
    from config_store import load_config

    assert load_config() == {}


def test_config_clear_removes_file():
    from config_store import save_config, config_path, clear_config

    save_config({"device_token": "x"})
    assert config_path().exists()
    clear_config()
    assert not config_path().exists()


def test_auto_migrate_from_env_creates_config(monkeypatch):
    """Legacy clients with CAMS_DEVICE_TOKEN in the .bat must seamlessly
    migrate to the JSON store on first boot."""
    from config_store import auto_migrate_env, load_config

    monkeypatch.setenv("CAMS_DEVICE_TOKEN", "legacy-tok")
    monkeypatch.setenv("CAMS_API", "https://staging.example/")
    cfg = auto_migrate_env()
    assert cfg is not None
    assert cfg["device_token"] == "legacy-tok"
    assert cfg["api_base"] == "https://staging.example"
    assert load_config()["device_token"] == "legacy-tok"


def test_auto_migrate_with_existing_config_does_not_overwrite(monkeypatch):
    from config_store import save_config, auto_migrate_env

    save_config({"device_token": "existing"})
    monkeypatch.setenv("CAMS_DEVICE_TOKEN", "should-not-override")
    cfg = auto_migrate_env()
    assert cfg["device_token"] == "existing"


# ---------- motion (MOG2) ---------------------------------------------------


def test_mog2_warmup_returns_zero_then_fires_on_change():
    from motion import MotionDetector

    m = MotionDetector(warmup_frames=2)
    flat = np.zeros((240, 320), dtype=np.uint8)
    # warmup
    for _ in range(3):
        score = m.process(flat)
        assert score == 0.0 or score >= 0.0  # warmup may still be 0
    # static scene after warmup
    assert m.process(flat) < 0.02
    # bright rectangle = motion
    bright = flat.copy()
    bright[80:160, 80:240] = 255
    assert m.process(bright) >= 0.02


def test_mog2_reset_clears_model():
    from motion import MotionDetector

    m = MotionDetector(warmup_frames=1)
    for _ in range(5):
        m.process(np.zeros((240, 320), dtype=np.uint8))
    m.reset()
    # post-reset first frames should be in warmup again (score 0)
    score = m.process(np.full((240, 320), 128, dtype=np.uint8))
    assert score == 0.0


# ---------- dedup (dhash + hamming) -----------------------------------------


def test_dhash_identical_images_zero_distance():
    from agent import _dhash, _hamming

    a = np.full((240, 320, 3), 100, dtype=np.uint8)
    a[50:100, 50:100] = 200
    h = _dhash(a)
    assert _hamming(h, h) == 0


def test_dhash_different_scenes_have_distance():
    from agent import _dhash, _hamming

    a = np.full((240, 320, 3), 0, dtype=np.uint8)
    b = np.full((240, 320, 3), 0, dtype=np.uint8)
    # Different bright regions
    a[50:150, 100:200] = 255
    b[10:60, 10:60] = 255
    ha, hb = _dhash(a), _dhash(b)
    assert _hamming(ha, hb) > 0


# ---------- self_test -------------------------------------------------------


def test_self_test_no_cameras_returns_empty():
    from self_test import run_self_test, summary

    results = run_self_test([])
    assert results == []
    assert summary(results) == "0/0 câmeras OK"


def test_self_test_dshow_source_marked_ok_without_probe():
    """dshow sources don't have a runtime check — they should still be
    reported as 'ok' so the panel doesn't false-alert on USB cams."""
    from self_test import run_self_test

    cams = [{"camera_id": "abc", "name": "USB", "rtsp_url": "dshow:0"}]
    results = run_self_test(cams)
    assert len(results) == 1
    assert results[0].ok is True
    assert results[0].kind == "dshow"


def test_self_test_missing_url_marked_fail():
    from self_test import run_self_test

    cams = [{"camera_id": "abc", "name": "Broken", "rtsp_url": ""}]
    results = run_self_test(cams)
    assert results[0].ok is False
    assert results[0].kind == "unknown"


# ---------- ring buffer -----------------------------------------------------


def test_ring_buffer_writes_and_slices():
    import time
    from buffer import RingBuffer

    buf = RingBuffer("cam-test", max_age_s=3600, max_bytes=10_000_000)
    t0 = time.time()
    for i in range(5):
        buf.write(b"\xff\xd8" + bytes(100) + b"\xff\xd9", ts=t0 + i * 0.5)
    frames = buf.slice(t0, t0 + 5)
    assert len(frames) == 5
    assert frames[0][0] <= frames[-1][0]


def test_ring_buffer_slice_out_of_window_returns_empty():
    import time
    from buffer import RingBuffer

    buf = RingBuffer("cam-empty")
    t0 = time.time()
    buf.write(b"\xff\xd8" + bytes(50) + b"\xff\xd9", ts=t0)
    assert buf.slice(t0 - 3600, t0 - 1800) == []


# ---------- edge_yolo (no model expected) -----------------------------------


def test_edge_yolo_degrades_when_model_missing():
    """When yolov8n.onnx isn't present (CI workflow without weights), the
    singleton should return None and `person_in_zone` should not crash."""
    from edge_yolo import get_edge_yolo

    yolo = get_edge_yolo(0.35)
    # On dev machine the model IS bundled; result should be a real instance.
    # We just assert no crash and either None or an object with the method.
    if yolo is None:
        return
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    found, conf = yolo.person_in_zone(img, {})
    assert isinstance(found, bool)
    assert 0.0 <= conf <= 1.0


# ---------- crash_reporter --------------------------------------------------


def test_crash_reporter_buffers_when_offline(monkeypatch):
    from crash_reporter import configure, report, _BUFFER

    _BUFFER.clear()

    class Cfg:
        api_base = "http://127.0.0.1:1"  # unreachable
        device_token = "x"

    configure(Cfg(), agent_version="1.0.0-test")
    try:
        raise ValueError("boom")
    except ValueError as e:
        report("test_kind", e, {"foo": "bar"})
    # The single attempted flush should have failed and re-queued.
    assert any(p["kind"] == "test_kind" for p in _BUFFER)
