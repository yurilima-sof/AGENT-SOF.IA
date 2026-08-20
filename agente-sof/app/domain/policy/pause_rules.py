# =============================================================================
# app/domain/policy/pause_rules.py - Validação de Pausa de Automações de Reunião
# =============================================================================

from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)

class DecisaoPausa(Enum):
    PAUSAR = "pausar"
    NAO_PAUSAR = "nao_pausar"
    INDETERMINADO = "indeterminado"

_GATILHOS_PAUSA = [
    r"\breuni[ãa]o\b", r"\bfechamento\s+de\s+m[êe]s\b", r"\bn[ãa]o\s+desliga\b",
    r"\bnao\s+desliga\b", r"\bpausar\s+automa[çc][ãa]o\b", r"\bhor[áa]rio\s+estendido\b"
]

_MARCADORES_TEMPORAIS = [
    r"\bat[eé]\b", r"\bat[eé]\s+as\b", r"\bat[eé]\s+[àa]s\b", r"\b\d{1,2}\s*(?:h|hrs|horas?)\b",
    r"\b\d{1,2}:\d{2}\b", r"\bhoje\s+[àa]s?\s+noite\b", r"\bat[eé]\s+mais\s+tarde\b"
]

_PEDIDOS_TERMICOS = [
    r"\bquente\b", r"\bcalor\b", r"\babafad[oa]\b", r"\besfria\b", r"\bgelar\b",
    r"\bfri[oa]\b", r"\bgelad[oa]\b", r"\besquentar\b"
]

_NEGACOES_CANCELAMENTOS = [
    r"\bn[ãa]o\s+precisa\b", r"\bcancela\b", r"\besquece\b", r"\bacabou\b", r"\bterminou\b"
]

def avaliar_pausa(mensagem: str) -> DecisaoPausa:
    """
    Avalia se a mensagem é um pedido legítimo de pausa temporária de automações.
    Evita falsos positivos como 'a sala de reunião está quente'.
    """
    if not mensagem:
        return DecisaoPausa.NAO_PAUSAR

    texto = mensagem.lower().strip()

    # Negações/Cancelamentos explícitos
    if any(re.search(pat, texto) for pat in _NEGACOES_CANCELAMENTOS):
        return DecisaoPausa.NAO_PAUSAR

    tem_gatilho = any(re.search(pat, texto) for pat in _GATILHOS_PAUSA)
    tem_temporal = any(re.search(pat, texto) for pat in _MARCADORES_TEMPORAIS)
    tem_termico = any(re.search(pat, texto) for pat in _PEDIDOS_TERMICOS)

    # Reclamação térmica na sala de reunião sem marcador temporal -> NÃO PAUSAR (é pedido de esfriar)
    if tem_gatilho and tem_termico and not tem_temporal:
        logger.info(f"   [Pausa] Reclamação térmica em sala de reunião sem marcador temporal: '{mensagem}' → NAO_PAUSAR")
        return DecisaoPausa.NAO_PAUSAR

    # Gatilho + marcador temporal explícito -> PAUSAR
    if tem_gatilho and tem_temporal:
        logger.info(f"   [Pausa] Pedido legítimo de pausa com horário: '{mensagem}' → PAUSAR")
        return DecisaoPausa.PAUSAR

    # Apenas gatilho genérico sem tempo nem térmico -> INDETERMINADO (passa para avaliação do LLM)
    if tem_gatilho:
        return DecisaoPausa.INDETERMINADO

    return DecisaoPausa.NAO_PAUSAR
