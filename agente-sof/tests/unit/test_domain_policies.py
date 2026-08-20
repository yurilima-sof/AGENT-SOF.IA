# =============================================================================
# tests/unit/test_domain_policies.py - Testes Unitários de Políticas de Domínio
# =============================================================================

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.policy.keyword_fallback import classificar_familia, FamiliaIntencao
from app.domain.policy.escalation import determinar_acao_e_intencao
from app.domain.policy.pause_rules import avaliar_pausa, DecisaoPausa
from app.domain.policy.time_parser import extrair_horario_termino

RECIFE_TZ = ZoneInfo("America/Recife")

# -----------------------------------------------------------------------------
# 1. Testes de Keyword Fallback & Escalonamento (U-04)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("mensagem, familia_esperada", [
    ("tá muito quente aqui", FamiliaIntencao.RESFRIAMENTO),
    ("loja abafada", FamiliaIntencao.RESFRIAMENTO),
    ("sala fria demais", FamiliaIntencao.AQUECIMENTO),
    ("preciso esquentar o showroom", FamiliaIntencao.AQUECIMENTO),
    ("coloca no médio", FamiliaIntencao.TEMPERATURA_MEDIA),
    ("pode desligar as máquinas", FamiliaIntencao.DESLIGAR),
    ("ligar equipamentos", FamiliaIntencao.LIGAR),
    ("bom dia equipe", None),
])
def test_keyword_fallback_classificacao(mensagem, familia_esperada):
    resultado = classificar_familia(mensagem)
    assert resultado == familia_esperada

def test_escalonamento_progressivo_resfriamento():
    # 1º Chamado -> T-Medium (medio)
    acao, intencao, _ = determinar_acao_e_intencao(FamiliaIntencao.RESFRIAMENTO, chamados_recentes=0)
    assert acao == "medio"
    assert intencao == "ligar_temperatura_media"

    # 2º Chamado -> T-Low (freezer)
    acao, intencao, _ = determinar_acao_e_intencao(FamiliaIntencao.RESFRIAMENTO, chamados_recentes=1)
    assert acao == "freezer"
    assert intencao == "ligar_resfriamento"

    # 3º Chamado -> T-Freezer (freezer)
    acao, intencao, _ = determinar_acao_e_intencao(FamiliaIntencao.RESFRIAMENTO, chamados_recentes=2)
    assert acao == "freezer"
    assert intencao == "ligar_resfriamento"

# -----------------------------------------------------------------------------
# 2. Testes de Regras de Pausa de Automação (U-05 / L4)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("mensagem, decisao_esperada", [
    ("vamos ter reunião até as 20h", DecisaoPausa.PAUSAR),
    ("fechamento de mês hoje até 22h", DecisaoPausa.PAUSAR),
    ("não desliga o ar até 21:30", DecisaoPausa.PAUSAR),
    ("a sala de reunião está quente", DecisaoPausa.NAO_PAUSAR),  # Regressão L4
    ("tá quente na reunião", DecisaoPausa.NAO_PAUSAR),           # Regressão L4
    ("não precisa pausar nada, cancela", DecisaoPausa.NAO_PAUSAR),
    ("bom dia", DecisaoPausa.NAO_PAUSAR),
])
def test_avaliar_pausa(mensagem, decisao_esperada):
    assert avaliar_pausa(mensagem) == decisao_esperada

# -----------------------------------------------------------------------------
# 3. Testes de Extração de Horário de Término (U-06 / L5)
# -----------------------------------------------------------------------------

def test_extrair_horario_termino():
    agora = datetime(2026, 8, 13, 14, 0, 0, tzinfo=RECIFE_TZ)

    # Reunião com horário válido ancorado em 'até'
    res1 = extrair_horario_termino("reunião até as 20h", agora=agora)
    assert res1 is not None
    assert res1.hour == 20 and res1.minute == 0

    # Horário com minutos
    res2 = extrair_horario_termino("fechamento de mês até 21:30", agora=agora)
    assert res2 is not None
    assert res2.hour == 21 and res2.minute == 30

    # Regressão L5: Sala 3 não deve ser extraída como 03:00
    res3 = extrair_horario_termino("reunião na sala 3", agora=agora)
    assert res3 is None

    # Regressão L5: 'dia 30' não deve estragar 'até 21h'
    res4 = extrair_horario_termino("reunião dia 30 até 21h", agora=agora)
    assert res4 is not None
    assert res4.hour == 21 and res4.minute == 0

    # Heurística comercial: 'até as 8' sem 'da manhã' deve virar 20:00
    res5 = extrair_horario_termino("reunião até as 8", agora=agora)
    assert res5 is not None
    assert res5.hour == 20
