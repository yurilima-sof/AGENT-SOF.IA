import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from app.domain.policy.time_parser import extrair_horario_termino

TZ = ZoneInfo("America/Recife")


def test_plantao_ate_as_20hrs_com_acento_errado():
    """Bug 21/09: 'até ás 20hrs' (á no lugar de à) deve extrair 20:00."""
    agora = datetime(2026, 9, 21, 9, 29, tzinfo=TZ)
    r = extrair_horario_termino("Hoje vamos ficar de plantão até ás 20hrs", agora=agora)
    assert r is not None
    assert r.hour == 20 and r.minute == 0


def test_variacoes_de_conector_e_sufixo_continuam_ok():
    """Regressão: os formatos que já funcionavam não podem quebrar."""
    agora = datetime(2026, 9, 21, 9, 0, tzinfo=TZ)
    for msg in [
        "reunião até as 20h",
        "plantão até às 20 horas",
        "até 20hrs",
        "fechamento até 21:30",
        "até ás 19:30",
    ]:
        assert extrair_horario_termino(msg, agora=agora) is not None, msg


def test_regressao_sala_nao_vira_horario():
    """Regressão: número de sala não pode virar horário."""
    agora = datetime(2026, 9, 21, 9, 0, tzinfo=TZ)
    assert extrair_horario_termino("reunião na sala 3", agora=agora) is None
