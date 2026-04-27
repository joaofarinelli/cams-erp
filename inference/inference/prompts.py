"""Per-preset prompt templates for the VLM inference worker.

System prompts are stable across many requests — they sit at the top of the
prefix and are cached via cache_control. The user-turn template injects the
specific zone polygons for the rule being evaluated.
"""

from __future__ import annotations

PRESET_PROMPTS: dict[str, dict] = {
    "cash_register": {
        "system": (
            "Voce analisa videoclipes curtos (3-10s) de cameras de seguranca em "
            "comercios PME brasileiros. Sua funcao e detectar comportamento "
            "suspeito no caixa: mao na gaveta sem operacao correspondente no "
            "PC/POS, retirada de dinheiro sem registro, demora suspeita sobre a "
            "gaveta aberta, ocultacao de cedulas. Voce retorna JSON estrito "
            "{alert: bool, score: 0..1, message: pt-BR curto, "
            "evidence_frame_idx: int|null}. Nao gere falso positivo: so flag "
            "evidencia clara. Mensagem deve mencionar o frame que motivou a "
            "decisao."
        ),
        "zone_keys": ["gaveta", "pc_operador"],
    },
    "kitchen_consumption": {
        "system": (
            "Voce analisa videoclipes curtos de cameras em cozinhas de "
            "restaurante/lanchonete brasileiros. Sua funcao e detectar consumo "
            "indevido por funcionarios: levar comida ou bebida a boca, beber "
            "diretamente de garrafa/recipiente, comer da area de preparo. Voce "
            "retorna JSON {alert, score, message pt-BR, evidence_frame_idx}. "
            "Nao confunda com prova legitima de tempero."
        ),
        "zone_keys": ["ingredients", "prep_area"],
    },
    "retail_shelf": {
        "system": (
            "Voce analisa videoclipes curtos de cameras em prateleiras de "
            "varejo brasileiro (mini-mercado, conveniencia). Sua funcao e "
            "detectar furto em prateleira: pegar item e ocultar no corpo "
            "(bolso, jaqueta, mochila) ao inves de colocar em cesta/carrinho. "
            "Voce retorna JSON {alert, score, message pt-BR, "
            "evidence_frame_idx}."
        ),
        "zone_keys": ["shelf"],
    },
}


CUSTOM_SYSTEM = (
    "Voce analisa videoclipes curtos (3-10s) de cameras de seguranca em "
    "comercios PME brasileiros. O usuario configurou uma regra customizada "
    "em linguagem natural; sua funcao e detectar se o comportamento descrito "
    "ocorreu no video. Voce retorna JSON estrito {alert: bool, score: 0..1, "
    "message: pt-BR curto, evidence_frame_idx: int|null}. Nao gere falso "
    "positivo: so flag se a evidencia for clara e diretamente alinhada a "
    "regra do usuario. Mensagem deve mencionar o frame que motivou a decisao."
)


def build_user_text(preset_type: str, zones: dict, n_frames: int) -> str:
    """Compose the per-event user text for a preset rule. Frames are appended
    as image blocks."""
    cfg = PRESET_PROMPTS[preset_type]
    zone_lines = []
    for key in cfg["zone_keys"]:
        poly = zones.get(key, [])
        zone_lines.append(f"- {key}: {poly}")
    zones_block = "\n".join(zone_lines) if zone_lines else "(no zones configured)"
    return (
        f"Preset: {preset_type}\n"
        f"Zonas configuradas (poligonos normalizados 0..1):\n"
        f"{zones_block}\n\n"
        f"Analise os {n_frames} frames abaixo em ordem cronologica. "
        f"Decida se o comportamento suspeito do preset ocorreu."
    )


def build_custom_user_text(custom_prompt: str, zones: dict, n_frames: int) -> str:
    """Compose the per-event user text for a custom-prompt rule."""
    if zones:
        zone_lines = "\n".join(f"- {k}: {v}" for k, v in zones.items())
        zones_block = f"Zonas configuradas (poligonos normalizados 0..1):\n{zone_lines}\n\n"
    else:
        zones_block = ""
    return (
        f"Regra do usuario:\n{custom_prompt}\n\n"
        f"{zones_block}"
        f"Analise os {n_frames} frames abaixo em ordem cronologica. "
        f"Decida se o comportamento descrito na regra ocorreu."
    )
