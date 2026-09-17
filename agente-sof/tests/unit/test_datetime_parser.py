import pytest
from app.domain.policy.datetime_parser import extrair_janela_evento, EscopoTemporal

def test_extrai_hora_com_typo_extenderate(agora_fixo):                       # Caso B
    j = extrair_janela_evento("hoje vamos extenderaté ás 19:00", agora=agora_fixo)
    assert j is not None and j.escopo == EscopoTemporal.HOJE
    assert j.hora_fim.hour == 19 and j.hora_fim.minute == 0

def test_extrai_data_futura_sabado_dia_19(agora_fixo):                       # Caso C
    msg = ("Evento Missão Impossível somente dia 19/09 (sábado). "
           "Hora Inicio Evento: 08:00 Hora Final Evento: 18:00")
    j = extrair_janela_evento(msg, agora=agora_fixo)
    assert j.escopo == EscopoTemporal.FUTURO
    assert j.data.day == 19 and j.data.month == 9 and j.hora_fim.hour == 18

def test_extrai_manaus_sabado_ate_17(agora_fixo):                           # Caso E
    j = extrair_janela_evento(
        "Manaus apenas no sábado, dia 19 vamos estender o horário até as 17:00", agora=agora_fixo)
    assert j.escopo == EscopoTemporal.FUTURO and j.data.day == 19 and j.hora_fim.hour == 17

def test_extrai_hoje_ate_1930(agora_fixo):                                  # Caso A (regressão)
    j = extrair_janela_evento("E hoje até 19:30 ligado", agora=agora_fixo)
    assert j.escopo == EscopoTemporal.HOJE and j.hora_fim.hour == 19 and j.hora_fim.minute == 30

def test_descarta_numero_de_sala(agora_fixo):                              # regressão time_parser
    j = extrair_janela_evento("reunião na sala 3", agora=agora_fixo)
    assert j is None or j.hora_fim is None

def test_sem_hora_retorna_indefinido(agora_fixo):                          # bug-raiz
    j = extrair_janela_evento("Deixa programado", agora=agora_fixo)
    assert j is None or j.escopo == EscopoTemporal.INDEFINIDO

def test_data_no_passado_e_rejeitada(agora_fixo):                          # guardrail
    j = extrair_janela_evento("evento dia 10/09 até 18:00", agora=agora_fixo)
    assert j is None or j.escopo == EscopoTemporal.INDEFINIDO

def test_extrai_caso_d_desligar_as_19h(agora_fixo):                          # Caso D (produção, grupo ...786392)
    j = extrair_janela_evento(
        "Evento no sábado dia 19/09 , pode estender o horário para desligar as 19:00", agora=agora_fixo)
    assert j is not None
    assert j.escopo == EscopoTemporal.FUTURO
    assert j.data.day == 19 and j.data.month == 9
    assert j.hora_fim.hour == 19 and j.hora_fim.minute == 0

def test_as_solto_nao_captura_numero_de_sala(agora_fixo):                    # guarda contra régua solta
    j = extrair_janela_evento("reunião na sala 3 às 15h", agora=agora_fixo)
    # a hora até pode ser lida (15h), mas "sala 3" não pode virar horário/escopo espúrio;
    # o que NÃO pode acontecer é o "3" da sala virar 03:00.
    assert j is None or j.hora_fim is None or j.hora_fim.hour == 15

def test_as_sem_horario_continua_indefinido(agora_fixo):                     # "as" sem hora não inventa nada
    j = extrair_janela_evento("desligar as máquinas depois", agora=agora_fixo)
    assert j is None or j.escopo == EscopoTemporal.INDEFINIDO
