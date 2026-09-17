import pytest
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch, AsyncMock, MagicMock


RECIFE_TZ = ZoneInfo("America/Recife")


def _make_fake_row(agendamento_id, id_grupo, nome_revenda, home_id, automacao_ids, horario_execucao, fase="resume"):
    """Cria uma row mockada que se comporta como resultado de fetchall (indexável)."""
    data = [agendamento_id, id_grupo, nome_revenda, home_id, automacao_ids, horario_execucao, fase]
    row = MagicMock()
    row.__getitem__ = lambda self, idx: data[idx]
    row.__len__ = lambda self: len(data)
    return row


@pytest.mark.integration
async def test_tick_repetido_nao_duplica_task(scheduler_isolado):
    """Bug 3: chamar carregar_agendamentos_pendentes 3x seguidas não pode criar 3 tasks
    para o mesmo agendamento."""
    agora = datetime.now(RECIFE_TZ)
    hora_resume = agora + timedelta(minutes=10)

    fake_row = _make_fake_row(
        agendamento_id=42,
        id_grupo="TESTE-C3",
        nome_revenda="Revenda C3",
        home_id="HOME_C3",
        automacao_ids=["a1"],
        horario_execucao=hora_resume.replace(tzinfo=None),
        fase="resume"
    )

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.scheduler_service.tuya_service.set_automation_status", new_callable=AsyncMock), \
         patch("app.services.scheduler_service.tuya_service.execute_scene", new_callable=AsyncMock), \
         patch("app.crud.tuya.get_scene_by_ambiente", new_callable=AsyncMock, return_value=None), \
         patch("app.database.async_session_maker", return_value=mock_session), \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock, return_value=[fake_row]):

        await scheduler_isolado.carregar_agendamentos_pendentes()
        n1 = len(scheduler_isolado._tasks)
        assert n1 >= 1, "Deveria ter criado pelo menos 1 task"

        await scheduler_isolado.carregar_agendamentos_pendentes()
        await scheduler_isolado.carregar_agendamentos_pendentes()
        assert len(scheduler_isolado._tasks) == n1, f"Tasks empilharam: esperado {n1}, obtido {len(scheduler_isolado._tasks)}"


@pytest.mark.integration
async def test_tick_nao_reexecuta_automacao_ja_agendada(scheduler_isolado):
    """A automação não pode receber enable=True em duplicidade por causa de ticks repetidos."""
    agora = datetime.now(RECIFE_TZ)
    hora_resume = agora + timedelta(seconds=1)

    fake_row = _make_fake_row(
        agendamento_id=99,
        id_grupo="TESTE-C3B",
        nome_revenda="Revenda C3B",
        home_id="HOME_C3B",
        automacao_ids=["a1"],
        horario_execucao=hora_resume.replace(tzinfo=None),
        fase="resume"
    )

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.scheduler_service.tuya_service.set_automation_status", new_callable=AsyncMock) as mock_set, \
         patch("app.services.scheduler_service.tuya_service.execute_scene", new_callable=AsyncMock), \
         patch("app.crud.tuya.get_scene_by_ambiente", new_callable=AsyncMock, return_value=None), \
         patch("app.database.async_session_maker", return_value=mock_session), \
         patch("app.crud.agendamentos.obter_agendamentos_pendentes", new_callable=AsyncMock, return_value=[fake_row]), \
         patch("app.crud.agendamentos.marcar_agendamento_executado", new_callable=AsyncMock), \
         patch("app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock):

        # Dois ticks rápidos
        await scheduler_isolado.carregar_agendamentos_pendentes()
        await scheduler_isolado.carregar_agendamentos_pendentes()

        # Aguardar tasks finalizarem (sleep mockado, então instant)
        await asyncio.sleep(0.2)

        # set_automation_status deve ter sido chamado no máximo 1 vez por automação
        assert mock_set.call_count <= 1, f"set_automation_status chamado {mock_set.call_count}x (duplicação!)"
