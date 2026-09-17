import re
from datetime import datetime, date, time, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass

class EscopoTemporal(str, Enum):
    HOJE = "hoje"
    FUTURO = "futuro"
    INDEFINIDO = "indefinido"

@dataclass
class JanelaEvento:
    escopo: EscopoTemporal
    data: Optional[date] = None
    hora_fim: Optional[time] = None

_ANCORA = r"(?:at[eé]|ate|por\s+volta\s+d[ae]s?|no\s+m[aá]ximo\s+at[eé]|extenderat[eé]|estenderat[eé]|hora\s+final\s+evento\s*:?|as|às|ás)"
_HORA = r"(?P<h>[01]?\d|2[0-3])(?:\s*[:h.]\s*(?P<m>[0-5]\d))?"
_SUFIXO = r"(?:\s*(?:h|hs|hrs|horas?))?"
_RE_HORARIO_ANCORADO = re.compile(rf"{_ANCORA}\s*(?:as|às|a|ás)?\s*{_HORA}{_SUFIXO}\b", re.IGNORECASE)
_RE_DISCARD_PREFIX = re.compile(r"\b(?:sala|andar|piso|n[ºo°]|numero|número)(?:\s+\w+)?\s*$", re.IGNORECASE)

_RE_HOJE = re.compile(r"\bhoje\b", re.IGNORECASE)
_RE_DATA_BARRA = re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})(?:/(?P<y>\d{2,4}))?\b", re.IGNORECASE)
_RE_DIA_DA_SEMANA = re.compile(r"\b(segunda|terça|quarta|quinta|sexta|sábado|sabado|domingo)(?:-?feira)?\b", re.IGNORECASE)

DIAS_SEMANA = {
    "segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6
}

def extrair_janela_evento(mensagem: str, agora: Optional[datetime] = None) -> Optional[JanelaEvento]:
    if not mensagem: return None
    if agora is None: 
        from zoneinfo import ZoneInfo
        agora = datetime.now(ZoneInfo("America/Recife"))
        
    texto = mensagem.lower().strip()
    
    # 1. Extrair Hora
    matches = list(_RE_HORARIO_ANCORADO.finditer(texto))
    if not matches:
        return JanelaEvento(escopo=EscopoTemporal.INDEFINIDO)
    
    ultimo_match = matches[-1]
    texto_antes = texto[:ultimo_match.start()].strip()
    if _RE_DISCARD_PREFIX.search(texto_antes):
        return JanelaEvento(escopo=EscopoTemporal.INDEFINIDO)
        
    hora = int(ultimo_match.group("h"))
    minuto = int(ultimo_match.group("m")) if ultimo_match.group("m") else 0
    if hora < 12 and "manhã" not in texto and "am" not in texto:
        if (hora + 12) >= agora.hour or hora < agora.hour:
            hora += 12
    hora = hora % 24
    hora_obj = time(hora, minuto)
    
    # 2. Extrair Escopo Temporal / Data
    data_alvo = None
    escopo = EscopoTemporal.INDEFINIDO
    is_hoje = _RE_HOJE.search(texto) is not None
    data_match = _RE_DATA_BARRA.search(texto)
    dia_semana_match = _RE_DIA_DA_SEMANA.search(texto)
    
    if data_match:
        d = int(data_match.group("d"))
        m = int(data_match.group("m"))
        y_str = data_match.group("y")
        y = int(y_str) if y_str else agora.year
        if y < 100: y += 2000
        try:
            data_alvo = date(y, m, d)
            if data_alvo < agora.date():
                return JanelaEvento(escopo=EscopoTemporal.INDEFINIDO)
        except ValueError:
            pass
    elif dia_semana_match:
        dia_nome = dia_semana_match.group(1).replace("á", "a").replace("ç", "c")
        dia_idx = DIAS_SEMANA[dia_nome]
        hoje_idx = agora.weekday()
        diff = dia_idx - hoje_idx
        if diff <= 0: diff += 7
        data_alvo = agora.date() + timedelta(days=diff)
        
    if data_alvo:
        if data_alvo == agora.date() or is_hoje:
            escopo = EscopoTemporal.HOJE
            data_alvo = agora.date()
        elif data_alvo > agora.date():
            escopo = EscopoTemporal.FUTURO
    elif is_hoje:
        escopo = EscopoTemporal.HOJE
        data_alvo = agora.date()
    else:
        return JanelaEvento(escopo=EscopoTemporal.INDEFINIDO)
        
    return JanelaEvento(escopo=escopo, data=data_alvo, hora_fim=hora_obj)
