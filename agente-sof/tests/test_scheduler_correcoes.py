# =============================================================================
# tests/test_scheduler_correcoes.py
# =============================================================================
# Travas para os achados da auditoria do scheduler:
#   C1 - duas chaves de task para a mesma linha => resume dobrado
#   C2 - segunda pausa no mesmo dia nao cancelava a primeira
#   C3 - linhas vencidas disparavam imediatamente a cada restart
#   A5 - cancelamento varria agendamentos de outros dias/homes
#   A7 - erros de banco engolidos sem log
#
# Todos rodam sem banco: `async_session_maker` e os CRUDs sao mockados.
# =============================================================================

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scheduler_service import RECIFE_TZ, TOLERANCIA_ATRASO_SEGUNDOS, _task_key


def _fake_row(agendamento_id, id_grupo, home_id, horario_execucao, fase="resume",
              data_execucao=None, nome_revenda="Revenda Teste", automacao_ids=None):
    """Row indexavel equivalente ao retorno de fetchall()."""
    data = [
        agendamento_id, id_grupo, nome_revenda, home_id,
        automacao_ids if automacao_ids is not None else ["a1"],
        horario_execucao, fase,
        data_execucao if data_execucao is not None else horario_execucao.date(),
    ]
    row = MagicMock()
    row.__getitem__ = lambda self, idx: data[idx]
    row.__len__ = lambda self: len(data)
    return row


def _mock_session():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


async def _drenar(scheduler):
    """Aguarda as tasks vivas terminarem (usado quando o delay e 0)."""
    tasks = list(scheduler._tasks.values())
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


# =============================================================================
# C1 - chave de task unificada
# =============================================================================

def test_chave_de_task_nao_confunde_homes_de_prefixo_comum():
    """`startswith` casava home '123' com '1234'. A chave agora e delimitada."""
    assert _task_key("G", "123", "x") != _task_key("G", "1234", "x")
    assert not _task_key("G", "1234", "x").startswith(_task_key("G", "123", "x"))


async def test_tick_nao_duplica_task_criada_na_pausa(scheduler_isolado):
    """C1: a task criada por agendar_reativacao_automacao e a criada pelo tick
    referem a MESMA linha e devem compartilhar a chave.

    Regressao: com `{grupo}_{home}_resume_imediata` de um lado e
    `{grupo}_{home}_{id}` do outro, o guard de idempotencia nao casava e o
    agendamento rodava duas vezes - inclusive a cena de desligamento geral.
    """
    agora = datetime.now(RECIFE_TZ)
    horario = agora + timedelta(hours=3)

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.agendamentos.salvar_agendamento", new_callable=AsyncMock, return_value="ag-1"), \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock,
               return_value=[_fake_row("ag-1", "GRUPO-C1", "HOME-C1", horario)]):

        await scheduler_isolado.agendar_reativacao_automacao(
            id_grupo="GRUPO-C1", nome_revenda="R", home_id="HOME-C1",
            automacao_ids=["a1"], horario_execucao=horario,
        )
        assert len(scheduler_isolado._tasks) == 1

        await scheduler_isolado.carregar_agendamentos_pendentes()
        await scheduler_isolado.carregar_agendamentos_pendentes()

        assert len(scheduler_isolado._tasks) == 1, (
            f"tasks empilharam para a mesma linha: {list(scheduler_isolado._tasks)}"
        )


# =============================================================================
# C2 - segunda pausa no mesmo dia substitui a primeira
# =============================================================================

async def test_segunda_pausa_no_mesmo_dia_cancela_a_primeira(scheduler_isolado):
    """C2: 'reuniao ate 20h' seguido de 'na verdade ate 22h' nao pode deixar o
    resume das 20h vivo - ele desligaria a loja no meio da reuniao."""
    agora = datetime.now(RECIFE_TZ)
    h20 = agora.replace(hour=20, minute=0, second=0, microsecond=0)
    h22 = agora.replace(hour=22, minute=0, second=0, microsecond=0)
    if h20 < agora:
        h20 += timedelta(days=1)
        h22 += timedelta(days=1)

    ids = iter(["ag-20h", "ag-22h"])

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.agendamentos.salvar_agendamento", new_callable=AsyncMock,
               side_effect=lambda *a, **k: next(ids)):

        await scheduler_isolado.agendar_reativacao_automacao(
            id_grupo="GRUPO-C2", nome_revenda="R", home_id="HOME-C2",
            automacao_ids=["a1"], horario_execucao=h20,
        )
        task_20h = scheduler_isolado._tasks[_task_key("GRUPO-C2", "HOME-C2", "ag-20h")]

        await scheduler_isolado.agendar_reativacao_automacao(
            id_grupo="GRUPO-C2", nome_revenda="R", home_id="HOME-C2",
            automacao_ids=["a1"], horario_execucao=h22,
        )

    assert task_20h.cancelled() or task_20h.cancelling(), "o resume das 20h continuou vivo"
    assert len(scheduler_isolado._tasks) == 1
    assert _task_key("GRUPO-C2", "HOME-C2", "ag-22h") in scheduler_isolado._tasks


async def test_salvar_agendamento_cancela_pendentes_do_mesmo_dia():
    """C2 no banco: o INSERT do fluxo 'hoje' tem que ser precedido do
    cancelamento das pendencias do dia, como o fluxo 'futuro' ja fazia."""
    from app.crud.agendamentos import salvar_agendamento

    db = MagicMock()
    db.commit = AsyncMock()
    horario = datetime(2026, 10, 1, 20, 0, tzinfo=RECIFE_TZ)

    with patch("app.crud.agendamentos.cancelar_pendentes_do_dia", new_callable=AsyncMock, return_value=1) as mock_cancel, \
         patch("app.crud.agendamentos._salvar_linha", new_callable=AsyncMock, return_value="novo-id"):
        await salvar_agendamento(db, "G", "R", "H", ["a1"], horario)

    mock_cancel.assert_awaited_once()
    args = mock_cancel.await_args.args
    assert args[1] == "G" and args[2] == "H"
    assert args[3] == horario.date()


# =============================================================================
# C3 - linhas vencidas
# =============================================================================

async def test_pause_vencido_e_descartado_sem_tocar_na_tuya(scheduler_isolado):
    """C3: um `pause` de um dia que ja passou NAO pode desativar as automacoes
    de OFF hoje - essa e a classe exata do incidente de 21/09."""
    agora = datetime.now(RECIFE_TZ)
    ontem = agora - timedelta(days=1)

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.services.scheduler_service.tuya_service.set_automation_status", new_callable=AsyncMock) as mock_set, \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock,
               return_value=[_fake_row("ag-velho", "G", "H", ontem, fase="pause")]), \
         patch("app.crud.agendamentos.marcar_agendamento_executado", new_callable=AsyncMock, return_value=True) as mock_marcar:

        await scheduler_isolado.carregar_agendamentos_pendentes()
        await _drenar(scheduler_isolado)

    assert len(scheduler_isolado._tasks) == 0, "pause vencido nao deveria virar task"
    mock_set.assert_not_awaited()
    mock_marcar.assert_awaited_once()


async def test_resume_vencido_religa_automacoes_mas_suprime_cena_off(scheduler_isolado):
    """C3: o `resume` atrasado ainda precisa religar as automacoes (senao a loja
    fica sem desligamento automatico), mas NAO pode disparar a cena de
    desligamento geral num horario arbitrario do expediente."""
    agora = datetime.now(RECIFE_TZ)
    vencido = agora - timedelta(seconds=TOLERANCIA_ATRASO_SEGUNDOS + 600)

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.services.scheduler_service.tuya_service.set_automation_status", new_callable=AsyncMock) as mock_set, \
         patch("app.services.scheduler_service.tuya_service.execute_scene", new_callable=AsyncMock) as mock_cena, \
         patch("app.crud.tuya.get_scene_by_ambiente", new_callable=AsyncMock, return_value={"scene_id": "S1"}), \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock,
               return_value=[_fake_row("ag-atrasado", "G", "H", vencido, fase="resume",
                                       data_execucao=agora.date())]), \
         patch("app.crud.agendamentos.marcar_agendamento_executado", new_callable=AsyncMock, return_value=True):

        await scheduler_isolado.carregar_agendamentos_pendentes()
        await _drenar(scheduler_isolado)

    mock_set.assert_awaited_once_with("H", "a1", enable=True)
    assert not mock_cena.await_count, "cena de desligamento disparada fora da janela"


async def test_resume_dentro_da_tolerancia_dispara_cena_off(scheduler_isolado):
    """Contraprova do teste acima: dentro da janela, o T-OFF pos-reuniao continua
    acontecendo. Sem esta trava, suprimir a cena sempre passaria despercebido."""
    agora = datetime.now(RECIFE_TZ)
    no_prazo = agora - timedelta(seconds=60)

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.services.scheduler_service.tuya_service.set_automation_status", new_callable=AsyncMock), \
         patch("app.services.scheduler_service.tuya_service.execute_scene", new_callable=AsyncMock) as mock_cena, \
         patch("app.crud.tuya.get_scene_by_ambiente", new_callable=AsyncMock, return_value={"scene_id": "S1"}), \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock,
               return_value=[_fake_row("ag-ok", "G", "H", no_prazo, fase="resume",
                                       data_execucao=agora.date())]), \
         patch("app.crud.agendamentos.marcar_agendamento_executado", new_callable=AsyncMock, return_value=True):

        await scheduler_isolado.carregar_agendamentos_pendentes()
        await _drenar(scheduler_isolado)

    mock_cena.assert_awaited_once_with("H", "S1")


async def test_agendamento_futuro_nao_e_tratado_como_vencido(scheduler_isolado):
    """O evento de sabado nao pode ser confundido com atraso: tem que virar uma
    task dormindo, nao uma execucao imediata."""
    agora = datetime.now(RECIFE_TZ)
    sabado = agora + timedelta(days=3)

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.services.scheduler_service.tuya_service.set_automation_status", new_callable=AsyncMock) as mock_set, \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock,
               return_value=[_fake_row("ag-futuro", "G", "H", sabado, fase="pause")]), \
         patch("app.crud.agendamentos.marcar_agendamento_executado", new_callable=AsyncMock) as mock_marcar:

        await scheduler_isolado.carregar_agendamentos_pendentes()
        await asyncio.sleep(0)

    assert len(scheduler_isolado._tasks) == 1
    mock_set.assert_not_awaited()
    mock_marcar.assert_not_awaited()


# =============================================================================
# A5 - cancelamento com recorte por dia
# =============================================================================

async def test_cancelar_hoje_preserva_evento_de_outro_dia(scheduler_isolado):
    """A5: 'reuniao cancelada' hoje nao pode apagar o evento ja agendado para
    sabado. Antes o UPDATE varria todas as pendencias do grupo/home."""
    agora = datetime.now(RECIFE_TZ)
    hoje_21h = agora + timedelta(hours=2)
    sabado = agora + timedelta(days=3)

    rows = [
        _fake_row("ag-hoje", "G", "H", hoje_21h, fase="resume"),
        _fake_row("ag-sabado", "G", "H", sabado, fase="pause"),
    ]

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock, return_value=rows), \
         patch("app.crud.agendamentos.marcar_agendamento_executado", new_callable=AsyncMock, return_value=True):
        await scheduler_isolado.carregar_agendamentos_pendentes()

    assert len(scheduler_isolado._tasks) == 2
    task_sabado = scheduler_isolado._tasks[_task_key("G", "H", "ag-sabado")]

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.agendamentos.cancelar_pendentes_do_dia", new_callable=AsyncMock, return_value=1) as mock_cancel:
        cancelou = await scheduler_isolado.cancelar_reativacao_pendente("G", "H")

    assert cancelou is True
    assert mock_cancel.await_args.args[3] == agora.date(), "cancelamento deve ser recortado em HOJE"
    assert not task_sabado.cancelled(), "o evento de sabado foi cancelado junto"
    assert _task_key("G", "H", "ag-sabado") in scheduler_isolado._tasks
    assert _task_key("G", "H", "ag-hoje") not in scheduler_isolado._tasks


async def test_cancelar_nao_afeta_home_de_prefixo_comum(scheduler_isolado):
    """A5: o antigo `startswith(f'{grupo}_{home}')` cancelava a home '1234' ao
    cancelar a home '123'."""
    agora = datetime.now(RECIFE_TZ)
    daqui_a_pouco = agora + timedelta(hours=2)

    rows = [
        _fake_row("ag-123", "G", "123", daqui_a_pouco),
        _fake_row("ag-1234", "G", "1234", daqui_a_pouco),
    ]

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock, return_value=rows), \
         patch("app.crud.agendamentos.marcar_agendamento_executado", new_callable=AsyncMock, return_value=True):
        await scheduler_isolado.carregar_agendamentos_pendentes()

    task_1234 = scheduler_isolado._tasks[_task_key("G", "1234", "ag-1234")]

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.agendamentos.cancelar_pendentes_do_dia", new_callable=AsyncMock, return_value=1):
        await scheduler_isolado.cancelar_reativacao_pendente("G", "123")

    assert not task_1234.cancelled(), "home '1234' foi cancelada junto com '123'"
    assert _task_key("G", "1234", "ag-1234") in scheduler_isolado._tasks


# =============================================================================
# A7 - erros de banco visiveis
# =============================================================================

async def test_marcar_executado_retorna_false_e_loga_em_falha(caplog):
    """A7: a falha do UPDATE significa re-execucao no proximo tick. Antes era
    engolida sem log nenhum."""
    from app.crud.agendamentos import marcar_agendamento_executado

    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("conexao caiu"))
    db.rollback = AsyncMock()

    with caplog.at_level("ERROR"):
        ok = await marcar_agendamento_executado(db, "ag-x")

    assert ok is False
    db.rollback.assert_awaited_once()
    assert "ag-x" in caplog.text


async def test_obter_pendentes_loga_falha_em_vez_de_virar_no_op_silencioso(caplog):
    """A7: a query falhando devolvia [] sem log - o tick inteiro virava um no-op
    invisivel e nenhum agendamento era reconstruido."""
    from app.crud.agendamentos import obter_agendamentos_pendentes

    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("timeout"))
    db.rollback = AsyncMock()

    with caplog.at_level("ERROR"):
        resultado = await obter_agendamentos_pendentes(db)

    assert resultado == []
    assert "pendentes" in caplog.text.lower()
