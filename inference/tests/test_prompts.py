from inference.prompts import PRESET_PROMPTS, build_user_text


def test_all_presets_have_required_keys() -> None:
    required = {"system", "zone_keys"}
    for preset, cfg in PRESET_PROMPTS.items():
        assert required.issubset(cfg.keys()), f"{preset} missing keys"
        assert isinstance(cfg["zone_keys"], list)
        assert cfg["system"], f"{preset} system prompt is empty"


def test_build_user_text_includes_zones() -> None:
    text = build_user_text(
        "cash_register",
        {"gaveta": [[0.1, 0.5], [0.4, 0.9]], "pc_operador": [[0.6, 0.1]]},
        n_frames=4,
    )
    assert "cash_register" in text
    assert "gaveta" in text
    assert "pc_operador" in text
    assert "4 frames" in text


def test_build_user_text_handles_missing_zones() -> None:
    text = build_user_text("cash_register", {}, n_frames=2)
    assert "gaveta: []" in text
    assert "pc_operador: []" in text


def test_three_presets_supported() -> None:
    assert set(PRESET_PROMPTS.keys()) == {
        "cash_register",
        "kitchen_consumption",
        "retail_shelf",
    }
