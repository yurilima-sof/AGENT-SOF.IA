# =============================================================================
# tests/test_reconciliacao_noturna.py
# =============================================================================
# Rede de protecao diaria (23:50 America/Recife): religa automacoes de
# desligamento que ficaram pausadas por um resume que nunca aconteceu.
#
# O invariante central nao e "religa" — e "religa SEM desligar quem ainda esta
# em janela legitima de pausa". Uma reconciliacao que ignora a janela ativa
# causa exatamente o incidente que ela existe para evitar.
#
# Rodam sem banco: `async_session_maker` e os CRUDs sao mockados.
# =============================================================================

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scheduler_service import HORA_RECONCILIACAO, RECIFE_TZ


def _mock_session():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _auto(auto_id, name, enabled):
    return {"id": auto_id, "name": name, "enabled": enabled}


# Nomes escolhidos para atravessar _eh_automacao_de_desligamento de verdade,
# em vez de mocka-la: queremos que a classificacao real seja exercitada aqui.
AUTO_OFF_DESATIVADA = _auto("off-1", "Desligamento Automatico Loja", False)
AUTO_OFF_ATIVA = _auto("off-2", "Desligamento Automatico Loja", True)
AUTO_LIGAR_DESATIVADA = _auto("on-1", "Ligar Climatizacao Manha", False)


def _patch_contexto(revendas, homes_em_janela, automacoes_por_home):
    """Monta o conjunto de patches comum a todos os testes de varredura."""
    return (
        patch("app.database.async_session_maker", return_value=_mock_session()),
        patch("app.crud.revendas.listar_revendas_ativas_com_home",
              new_callable=AsyncMock, return_value=revendas),
        patch("app.crud.agendamentos.obter_homes_com_janela_ativa",
              new_callable=AsyncMock, return_value=homes_em_janela),
        patch("app.services.scheduler_service.tuya_service.get_automations_by_home",
              new_callable=AsyncMock, side_effect=lambda h: automacoes_por_home.get(h, [])),
    )


# =============================================================================
# Comportamento principal
# =============================================================================

async def test_religa_automacao_de_desligamento_que_ficou_pausada(scheduler_isolado):
    """O caso que a rede existe para cobrir: o resume nunca rodou e a automacao
    de OFF amanheceria desativada."""
    revendas = [{"id_grupo_wpp": "G1", "nome_revenda": "Revenda A", "home_id": "H1"}]
    p1, p2, p3, p4 = _patch_contexto(revendas, set(), {"H1": [AUTO_OFF_DESATIVADA]})

    with p1, p2, p3, p4, \
         patch("app.services.scheduler_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        resumo = await scheduler_isolado.reconciliar_automacoes_noturnas()

    mock_set.assert_awaited_once_with("H1", "off-1", enable=True)
    assert resumo["automacoes_religadas"] == 1
    assert resumo["revendas_verificadas"] == 1


async def test_nao_mexe_em_automacao_ja_ativa(scheduler_isolado):
    """Idempotencia: rodar todo dia nao pode gerar chamada a Tuya a toa."""
    revendas = [{"id_grupo_wpp": "G1", "nome_revenda": "Revenda A", "home_id": "H1"}]
    p1, p2, p3, p4 = _patch_contexto(revendas, set(), {"H1": [AUTO_OFF_ATIVA]})

    with p1, p2, p3, p4, \
         patch("app.services.scheduler_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        resumo = await scheduler_isolado.reconciliar_automacoes_noturnas()

    mock_set.assert_not_awaited()
    assert resumo["automacoes_religadas"] == 0


async def test_nao_religa_automacao_de_ligar(scheduler_isolado):
    """Automacao de LIGAR desativada pode ter sido desligada de proposito pela
    loja. A rede so cuida das de desligamento."""
    revendas = [{"id_grupo_wpp": "G1", "nome_revenda": "Revenda A", "home_id": "H1"}]
    p1, p2, p3, p4 = _patch_contexto(revendas, set(), {"H1": [AUTO_LIGAR_DESATIVADA]})

    with p1, p2, p3, p4, \
         patch("app.services.scheduler_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        resumo = await scheduler_isolado.reconciliar_automacoes_noturnas()

    mock_set.assert_not_awaited()
    assert resumo["automacoes_religadas"] == 0


# =============================================================================
# A trava critica: janela de pausa que atravessa a meia-noite
# =============================================================================

async def test_pula_home_com_janela_de_pausa_ativa(scheduler_isolado):
    """'Fechamento ate 1h' => resume amanha de madrugada. As 23:50 a loja AINDA
    esta em janela legitima: religar aqui desligaria a loja no meio do
    fechamento, que e exatamente o incidente que a rede deveria evitar."""
    revendas = [
        {"id_grupo_wpp": "G1", "nome_revenda": "Em fechamento", "home_id": "H1"},
        {"id_grupo_wpp": "G2", "nome_revenda": "Normal", "home_id": "H2"},
    ]
    p1, p2, p3, p4 = _patch_contexto(
        revendas,
        {"H1"},  # H1 tem resume pendente no futuro
        {"H1": [AUTO_OFF_DESATIVADA], "H2": [AUTO_OFF_DESATIVADA]},
    )

    with p1, p2, p3, p4, \
         patch("app.services.scheduler_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        resumo = await scheduler_isolado.reconciliar_automacoes_noturnas()

    homes_tocadas = {c.args[0] for c in mock_set.await_args_list}
    assert homes_tocadas == {"H2"}, f"a rede religou uma home em janela ativa: {homes_tocadas}"
    assert resumo["revendas_puladas_janela_ativa"] == 1
    assert resumo["automacoes_religadas"] == 1


async def test_falha_ao_consultar_janelas_aborta_sem_religar_nada(scheduler_isolado):
    """Falha fechada: sem saber quem esta em janela ativa, religar as cegas pode
    desligar uma loja ocupada. Melhor nao agir e logar."""
    revendas = [{"id_grupo_wpp": "G1", "nome_revenda": "Revenda A", "home_id": "H1"}]

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.revendas.listar_revendas_ativas_com_home",
               new_callable=AsyncMock, return_value=revendas), \
         patch("app.crud.agendamentos.obter_homes_com_janela_ativa",
               new_callable=AsyncMock, side_effect=RuntimeError("banco fora")), \
         patch("app.services.scheduler_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        resumo = await scheduler_isolado.reconciliar_automacoes_noturnas()

    mock_set.assert_not_awaited()
    assert "erro" in resumo
    assert resumo["automacoes_religadas"] == 0


async def test_crud_de_janela_ativa_propaga_erro_em_vez_de_devolver_vazio():
    """Contraparte no CRUD do teste acima.

    `obter_homes_com_janela_ativa` NAO pode seguir o padrao dos outros CRUDs
    (logar e devolver vazio): um conjunto vazio significa "ninguem em janela
    ativa", que a reconciliacao le como permissao para religar TODAS as homes.
    Em caso de erro de banco, isso desligaria lojas em fechamento. Tem que
    propagar.
    """
    import pytest

    from app.crud.agendamentos import obter_homes_com_janela_ativa

    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("banco fora"))
    db.rollback = AsyncMock()

    with pytest.raises(RuntimeError):
        await obter_homes_com_janela_ativa(db, datetime.now(RECIFE_TZ))

    db.rollback.assert_awaited_once()


async def test_crud_de_janela_ativa_filtra_por_fase_e_futuro():
    """So `resume` pendente com horario no futuro caracteriza janela ativa."""
    from app.crud.agendamentos import obter_homes_com_janela_ativa

    resultado = MagicMock()
    resultado.fetchall = MagicMock(return_value=[("H1",), ("H2",)])
    db = MagicMock()
    db.execute = AsyncMock(return_value=resultado)

    agora = datetime.now(RECIFE_TZ)
    homes = await obter_homes_com_janela_ativa(db, agora)

    assert homes == {"H1", "H2"}
    sql = str(db.execute.await_args.args[0]).lower()
    assert "fase = 'resume'" in sql
    assert "horario_execucao > :agora" in sql
    assert "executado = false" in sql
    assert db.execute.await_args.args[1] == {"agora": agora}


# =============================================================================
# Robustez da varredura
# =============================================================================

async def test_erro_em_uma_revenda_nao_aborta_as_demais(scheduler_isolado):
    """Uma home com credencial quebrada nao pode deixar as outras lojas ligadas
    a noite inteira."""
    revendas = [
        {"id_grupo_wpp": "G1", "nome_revenda": "Quebrada", "home_id": "H_ERRO"},
        {"id_grupo_wpp": "G2", "nome_revenda": "Saudavel", "home_id": "H2"},
    ]

    async def _automacoes(home_id):
        if home_id == "H_ERRO":
            raise RuntimeError("Tuya 401")
        return [AUTO_OFF_DESATIVADA]

    with patch("app.database.async_session_maker", return_value=_mock_session()), \
         patch("app.crud.revendas.listar_revendas_ativas_com_home",
               new_callable=AsyncMock, return_value=revendas), \
         patch("app.crud.agendamentos.obter_homes_com_janela_ativa",
               new_callable=AsyncMock, return_value=set()), \
         patch("app.services.scheduler_service.tuya_service.get_automations_by_home",
               new_callable=AsyncMock, side_effect=_automacoes), \
         patch("app.services.scheduler_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        resumo = await scheduler_isolado.reconciliar_automacoes_noturnas()

    mock_set.assert_awaited_once_with("H2", "off-1", enable=True)
    assert resumo["revendas_com_erro"] == 1
    assert resumo["automacoes_religadas"] == 1


async def test_varredura_sem_revendas_nao_quebra(scheduler_isolado):
    p1, p2, p3, p4 = _patch_contexto([], set(), {})
    with p1, p2, p3, p4:
        resumo = await scheduler_isolado.reconciliar_automacoes_noturnas()
    assert resumo["revendas_verificadas"] == 0
    assert resumo["automacoes_religadas"] == 0


# =============================================================================
# Horario do laco
# =============================================================================

def test_horario_configurado_e_2350():
    assert (HORA_RECONCILIACAO.hour, HORA_RECONCILIACAO.minute) == (23, 50)


def test_espera_aponta_para_2350_do_mesmo_dia(scheduler_isolado):
    agora = datetime(2026, 10, 1, 18, 0, tzinfo=RECIFE_TZ)
    espera = scheduler_isolado._segundos_ate_proxima_reconciliacao(agora)
    assert agora + timedelta(seconds=espera) == datetime(2026, 10, 1, 23, 50, tzinfo=RECIFE_TZ)


def test_espera_rola_para_o_dia_seguinte_depois_das_2350(scheduler_isolado):
    """Logo depois da varredura, a proxima e amanha — nao daqui a 0 segundos
    (que faria o laco rodar em loop apertado)."""
    agora = datetime(2026, 10, 1, 23, 55, tzinfo=RECIFE_TZ)
    espera = scheduler_isolado._segundos_ate_proxima_reconciliacao(agora)
    assert espera > 0
    assert agora + timedelta(seconds=espera) == datetime(2026, 10, 2, 23, 50, tzinfo=RECIFE_TZ)


def test_espera_no_instante_exato_nao_e_zero(scheduler_isolado):
    """Caso de borda: chamar exatamente as 23:50:00 tem que agendar para amanha."""
    agora = datetime(2026, 10, 1, 23, 50, tzinfo=RECIFE_TZ)
    espera = scheduler_isolado._segundos_ate_proxima_reconciliacao(agora)
    assert espera == 24 * 3600


def test_iniciar_e_idempotente(scheduler_isolado):
    """Dois startups (ou um reload) nao podem deixar dois lacos vivos — seriam
    duas varreduras concorrentes as 23:50."""
    import asyncio

    async def _cenario():
        with patch.object(scheduler_isolado, "_loop_reconciliacao_noturna",
                          new_callable=lambda: (lambda: asyncio.sleep(3600))):
            scheduler_isolado.iniciar_reconciliacao_noturna()
            primeira = scheduler_isolado._reconciliacao_task
            scheduler_isolado.iniciar_reconciliacao_noturna()
            assert scheduler_isolado._reconciliacao_task is primeira
            scheduler_isolado.parar_reconciliacao_noturna()
            assert scheduler_isolado._reconciliacao_task is None
            await asyncio.gather(primeira, return_exceptions=True)

    asyncio.run(_cenario())
