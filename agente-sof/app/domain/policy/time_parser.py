# =============================================================================
# app/domain/policy/time_parser.py - Extração Ancorada de Horário de Término
# =============================================================================

import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

try:
    RECIFE_TZ = ZoneInfo("America/Recife")
except ZoneInfoNotFoundError:
    RECIFE_TZ = timezone(timedelta(hours=-3))

# Âncora obrigatória: exige 'até', 'ate', 'por volta de'
_ANCORA = r"(?:at[eé]|ate|por\s+volta\s+d[ae]s?|no\s+m[aá]ximo\s+at[eé])"
_HORA = r"(?P<h>[01]?\d|2[0-3])(?:\s*[:h.]\s*(?P<m>[0-5]\d))?"
_SUFIXO = r"(?:\s*(?:h|hs|hrs|horas?))?"

_RE_HORARIO_ANCORADO = re.compile(rf"{_ANCORA}\s*(?:as|às|a)?\s*{_HORA}{_SUFIXO}\b", re.IGNORECASE)
_RE_DISCARD_PREFIX = re.compile(r"\b(?:sala|andar|piso|n[ºo°]|numero|número)\s*$", re.IGNORECASE)

def extrair_horario_termino(mensagem: str, agora: Optional[datetime] = None) -> Optional[datetime]:
    """
    Extrai o horário de término mencionado na mensagem de forma ancorada e determinística.
    
    Exemplos válidos:
      - 'reunião até as 20h' -> 20:00 hoje
      - 'fechamento até 21:30' -> 21:30 hoje
      - 'não desliga até 22 horas' -> 22:00 hoje
      - 'reunião dia 30 até 21h' -> 21:00 hoje
      
    Exemplos ignorados (retornam None sem default inventado):
      - 'reunião na sala 3' -> None (ignora o número da sala)
    """
    if not mensagem:
        return None

    if agora is None:
        agora = datetime.now(RECIFE_TZ)

    texto = mensagem.lower().strip()
    matches = list(_RE_HORARIO_ANCORADO.finditer(texto))

    if not matches:
        logger.info(f"   [TimeParser] Nenhum horário ancorado encontrado na mensagem: '{mensagem}'")
        return None

    # Pega o ÚLTIMO match válido (ex: 'de 14h até 16h' -> 16h)
    ultimo_match = matches[-1]
    
    # Verifica se a palavra imediatamente anterior ao match é um prefixo de sala/andar (ex: 'sala 3')
    texto_antes = texto[:ultimo_match.start()].strip()
    if _RE_DISCARD_PREFIX.search(texto_antes):
        logger.info(f"   [TimeParser] Horário descartado por prefixo de sala/andar: '{mensagem}'")
        return None

    try:
        hora = int(ultimo_match.group("h"))
        minuto = int(ultimo_match.group("m")) if ultimo_match.group("m") else 0

        # Heurística comercial: se hora < 12 e sem 'da manhã', converte para a tarde (+12) se fizer mais sentido no horário comercial
        if hora < 12 and "manhã" not in texto and "am" not in texto:
            if (hora + 12) >= agora.hour or hora < agora.hour:
                hora += 12

        data_alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)

        # Se a hora informada já passou hoje no horário local, considera o dia seguinte
        if data_alvo < agora:
            data_alvo += timedelta(days=1)

        # Se o atraso resultante passar de 18 horas, descarta por ambiguidade
        if (data_alvo - agora).total_seconds() > 18 * 3600:
            logger.info(f"   [TimeParser] Horário {data_alvo} descartado por ambiguidade/atraso > 18h")
            return None

        logger.info(f"   [TimeParser] Horário extraído com sucesso: {data_alvo.strftime('%H:%M:%S')}")
        return data_alvo

    except (ValueError, TypeError) as e:
        logger.warning(f"⚠️ Erro ao converter horário extraído: {e}")
        return None
