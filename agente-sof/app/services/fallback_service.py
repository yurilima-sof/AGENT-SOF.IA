import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Mapeamento de palavras-chave → ação IFTTT
_KEYWORDS: dict[str, list[str]] = {
    "freezer": [
        "quente", "quente demais", "muito quente", "calor", "ta quente", "tá quente",
        "sala quente", "loja quente", "abafado", "abafada", "congelar", "esfriar", "gelar",
        "freezer", "freeze", "opção 1", "opcao 1", "🔥", "opção1", "opcao1",
        "ação:freezer", "t-low", "tlow", "baixo", "low",
        "16", "17", "18", "19", "20", "16c", "17c", "18c", "19c", "20c",
    ],
    "esquentar": [
        "frio", "fria", "gelado", "gelada", "sala fria", "sala gelada", "loja fria",
        "frio demais", "muito frio", "gelado demais", "ta frio", "tá frio",
        "esquentar", "aquecer", "warm", "high", "t-high", "thigh",
        "opção 2", "opcao 2", "🥶", "opção2", "opcao2", "ação:esquentar",
        "24", "25", "26", "27", "24c", "25c", "26c", "27c",
    ],
    "medio": [
        "medio", "médio", "medium", "t-medium", "t-médium",
        "temperatura média", "primeiro calor",
        "21", "22", "23", "21c", "22c", "23c",
    ],
    "off": [
        "desligar arcondicionado", "desligar ar-condicionado", "desligar ar condicionado", "desligar o ar", "desliga o ar",
        "desligar maquinas", "desligar", "desliga", "off", "parar", "cancelar",
        "podem desligar todas", "opção 3", "opcao 3", "❌",
        "opção3", "opcao3", "ação:off",
        "revenda fechada hoje", "estamos fechado",
        "por favor desligar maquinas", "toff", "t-off"
    ],
    "ligar": [
        "ligar arcondicionado", "ligar ar-condicionado", "ligar ar condicionado",
        "ligar maquina", "ligar maquinas", "ligar todos", "ligar tudo",
        "ligar ar", "ligar", "ação:ligar",
    ],
}

_ACAO_PARA_INTENCAO: dict[str, str] = {
    "freezer": "ligar_resfriamento",
    "esquentar": "ligar_aquecimento",
    "medio": "ligar_temperatura_media",
    "off": "desligar_dispositivos",
    "ligar": "ligar_dispositivos",
}

_MENSAGENS_RESPOSTA: dict[str, str] = {
    "freezer": "Entendido! ❄️ Ativando modo resfriamento. Aguarde alguns instantes.",
    "esquentar": "Entendido! 🔆 Ativando aquecimento. Aguarde alguns instantes.",
    "medio": "Entendido! 🌤️ Ajustando para uma temperatura média. Aguarde alguns instantes.",
    "off": "Ok! ✅ Desativando os equipamentos. Qualquer dúvida, estou aqui.",
    "ligar": "Entendido! ⚡ Ligando os equipamentos. Aguarde alguns instantes.",
    "nenhuma": "Olá! 🤖 Sou a Sofia. Como posso te ajudar com a temperatura do ambiente hoje?",
}

_KEYWORDS_ORDENADAS: list[tuple[str, str]] = sorted(
    [(kw, acao) for acao, kws in _KEYWORDS.items() for kw in kws],
    key=lambda item: len(item[0]),
    reverse=True,
)

def identificar_acao(mensagem: str) -> Optional[str]:
    """
    Analisa a mensagem do usuário e identifica a ação IoT correspondente.
    """
    texto = mensagem.lower().strip()
    for keyword, acao in _KEYWORDS_ORDENADAS:
        if keyword in texto:
            logger.info(f"   Keyword detectada: '{keyword}' → ação: '{acao}'")
            return acao
    return None

def get_intencao_and_message(acao: Optional[str]) -> tuple[str, str]:
    """
    Retorna a intenção semântica e a mensagem de resposta baseada na ação.
    """
    if acao:
        return _ACAO_PARA_INTENCAO[acao], _MENSAGENS_RESPOSTA[acao]
    return "sem_acao", _MENSAGENS_RESPOSTA["nenhuma"]
