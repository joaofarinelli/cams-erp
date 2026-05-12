from inference.prompts import CUSTOM_SYSTEM, build_user_text


def test_custom_system_is_non_empty_pt_br() -> None:
    assert isinstance(CUSTOM_SYSTEM, str)
    assert len(CUSTOM_SYSTEM) > 200
    # System prompt must instruct the model to be conservative.
    assert "falso-positivo" in CUSTOM_SYSTEM.lower() or "conservadora" in CUSTOM_SYSTEM.lower()


def test_build_user_text_includes_rule_and_zone_names() -> None:
    text = build_user_text(
        "Detectar abertura da gaveta do caixa",
        {"gaveta": [[0.1, 0.5], [0.4, 0.9], [0.2, 0.8]]},
        n_frames=4,
    )
    assert "gaveta" in text
    assert "Detectar abertura" in text
    assert "4 frames" in text


def test_build_user_text_no_zones_still_includes_rule() -> None:
    text = build_user_text("alguma regra", {}, n_frames=2)
    assert "alguma regra" in text
    assert "2 frames" in text


def test_build_user_text_multiple_zones() -> None:
    text = build_user_text(
        "regra X",
        {"gaveta": [[0, 0], [1, 0], [1, 1]], "balcao": [[0, 0], [0.5, 0.5], [0, 1]]},
        n_frames=4,
    )
    assert "gaveta" in text
    assert "balcao" in text
