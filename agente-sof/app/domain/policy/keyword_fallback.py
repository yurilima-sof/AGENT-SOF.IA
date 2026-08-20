# =============================================================================
# app/domain/policy/keyword_fallback.py - Classificação Determinística por Keywords
# =============================================================================

from enum import Enum
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class FamiliaIntencao(str, Enum):
    RESFRIAMENTO = "resfriamento"
    AQUECIMENTO = "aquecimento"
    TEMPERATURA_MEDIA = "temperatura_media"
    DESLIGAR = "desligar"
    LIGAR = "ligar"
    PAUSAR_AUTOMACAO = "pausar_automacao"

# Mapeamento de palavras-chave → família de intenção (sem escolher o nível de escalonamento)
_KEYWORDS: dict[FamiliaIntencao, list[str]] = {
    FamiliaIntencao.RESFRIAMENTO: [
        "quente", "quente demais", "muito quente", "calor", "ta quente", "tá quente",
        "sala quente", "loja quente", "abafado", "abafada", "congelar", "esfriar", "gelar",
        "freezer", "freeze", "opção 1", "opcao 1", "🔥", "opção1", "opcao1",
        "ação:freezer", "t-low", "tlow", "baixo", "low",
    ],
    FamiliaIntencao.AQUECIMENTO: [
        "frio", "fria", "gelado", "gelada", "sala fria", "sala gelada", "loja fria",
        "frio demais", "muito frio", "gelado demais", "ta frio", "tá frio",
        "esquentar", "aquecer", "warm", "high", "t-high", "thigh",
        "opção 2", "opcao 2", "🥶", "opção2", "opcao2", "ação:esquentar",
    ],
    FamiliaIntencao.TEMPERATURA_MEDIA: [
        "medio", "médio", "medium", "t-medium", "t-médium",
        "temperatura média", "primeiro calor",
    ],
    FamiliaIntencao.DESLIGAR: [
        "off", "desligar", "desliga", "parar", "apagar", "fechar", "fechado", "fechando",
        "t-off", "toff", "opção 0", "opcao 0", "🔴", "opção0", "opcao0", "ação:off",
    ],
    FamiliaIntencao.LIGAR: [
        "ligar", "liga", "iniciar", "ligar ar", "ligar máquinas", "ligar equipamentos",
    ],
}

# Ordena palavras por tamanho decrescente para evitar falso positivo de substrings curtas
_KEYWORDS_ORDENADAS: list[Tuple[FamiliaIntencao, str]] = []
for familia, lista_kw in _KEYWORDS.items():
    for kw in lista_kw:
        _KEYWORDS_ORDENADAS.append((familia, kw))
_KEYWORDS_ORDENADAS.sort(key=lambda item: len(item[1]), reverse=True)

def classificar_familia(mensagem: str) -> Optional[FamiliaIntencao]:
    """
    Identifica a família da intenção por correspondência de palavras-chave.
    Retorna a Família (ex: RESFRIAMENTO) sem escolher o nível físico final.
    """
    if not mensagem:
        return None

    texto = mensagem.lower().strip()
    for familia, kw in _KEYWORDS_ORDENADAS:
        if kw in texto:
            logger.info(f"   Keyword detectada: '{kw}' → Família: '{familia.value}'")
            return familia

    return None
