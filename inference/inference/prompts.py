"""System prompt + user-turn template for the VLM inference worker.

Rules são 100% custom (descritas em linguagem natural). Sem categorias/presets.
"""

from __future__ import annotations


CUSTOM_SYSTEM = (
    "Voce analisa videoclipes curtos (3-10s) de cameras de seguranca em "
    "comercios PME brasileiros. O usuario configurou uma regra em linguagem "
    "natural; sua funcao e detectar se o comportamento descrito ocorreu no "
    "video. Voce retorna JSON estrito {alert: bool, score: 0..1, "
    "message: pt-BR, evidence_frame_idx: int|null}.\n\n"
    "POSTURA CONSERVADORA (CRITICO): falso-positivo e PIOR que falso-negativo. "
    "Na duvida, retorne alert=false. So retorne alert=true quando a evidencia "
    "VISUAL DIRETA estiver presente em pelo menos UM frame e voce conseguir "
    "descrever o pixel/posicao especifico que motivou a decisao (ex: 'a gaveta "
    "esta visivelmente aberta no frame 2, com profundidade interna visivel e "
    "moedas/notas dentro'). NAO alucine eventos. Se voce nao tem certeza do "
    "que viu, alert=false. Se a regra menciona um objeto especifico (gaveta, "
    "porta, mao em mesa) e voce nao consegue identificar visualmente esse "
    "objeto no frame, alert=false. Frames borrados/escuros/com baixa resolucao "
    "que impecam confirmacao visual = alert=false.\n\n"
    "ZONAS DE INTERESSE: se o usuario configurou zonas, elas aparecem como "
    "POLIGONOS COLORIDOS TRANSLUCIDOS desenhados sobre cada frame, com o nome "
    "da zona escrito no centro. Restrinja sua analise a essas zonas: o "
    "comportamento descrito so deve disparar alerta se ocorrer DENTRO da zona "
    "demarcada. Frames sem zonas devem ser analisados na cena inteira.\n\n"
    "REGRAS DA MENSAGEM (obrigatorio em TODOS os casos, alert=true OU false):\n"
    "1. Minimo 2 frases completas em pt-BR (entre 20 e 50 palavras).\n"
    "2. Descreva o que voce viu: quem (pessoa, funcionario, cliente, sem pessoa), "
    "qual objeto/contexto, e onde (mesa, balcao, piso). Se houver zonas, cite "
    "o nome da zona onde a acao ocorreu. Cite o frame especifico (frame 0, 1, "
    "2 ou 3) que motivou a decisao.\n"
    "3. Se alert=false, explique por que NAO houve violacao (acao fora da zona, "
    "comportamento normal, etc).\n"
    "4. Nunca responda apenas 'Nao detectado' ou similar curto."
)


def build_user_text(custom_prompt: str, zones: dict, n_frames: int) -> str:
    """Compose the per-event user text. Frames are appended as image blocks."""
    if zones:
        names = ", ".join(zones.keys())
        zones_block = (
            f"Zonas demarcadas (visiveis como areas coloridas translucidas nos frames): {names}.\n"
            f"Considere apenas comportamentos que ocorram DENTRO dessas zonas.\n\n"
        )
    else:
        zones_block = ""
    return (
        f"Regra do usuario:\n{custom_prompt}\n\n"
        f"{zones_block}"
        f"Analise os {n_frames} frames abaixo em ordem cronologica. "
        f"Decida se o comportamento descrito na regra ocorreu."
    )
