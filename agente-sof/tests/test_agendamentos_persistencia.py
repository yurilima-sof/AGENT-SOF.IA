import pytest
from datetime import date, datetime
from sqlalchemy import text

@pytest.mark.integration
async def test_salva_duas_fases_para_evento_futuro(db_session):
    from app.crud.agendamentos import salvar_agendamento_evento, inicializar_tabela_agendamentos
    await inicializar_tabela_agendamentos(db_session)
    
    ids = await salvar_agendamento_evento(db_session, id_grupo_wpp="TESTE-sched-001",
        nome_revenda="R", home_id="999999", automacao_ids=["a1", "a2"],
        data_execucao=date(2026, 9, 19),
        hora_pause=datetime(2026, 9, 19, 6, 0), hora_resume=datetime(2026, 9, 19, 18, 0))
    assert len(ids) == 2
    res = await db_session.execute(text(
        "SELECT fase FROM agendamentos WHERE id_grupo_wpp='TESTE-sched-001' ORDER BY fase"))
    fases = [r[0] for r in res.fetchall()]
    assert "pause" in fases and "resume" in fases
    await db_session.execute(text("DELETE FROM agendamentos WHERE id_grupo_wpp='TESTE-sched-001'"))
    await db_session.commit()

@pytest.mark.integration
async def test_conflito_mesmo_grupo_data_substitui(db_session):
    from app.crud.agendamentos import salvar_agendamento_evento, inicializar_tabela_agendamentos
    await inicializar_tabela_agendamentos(db_session)
    
    await salvar_agendamento_evento(db_session, id_grupo_wpp="TESTE-sched-002",
        nome_revenda="R", home_id="111", automacao_ids=["a1"],
        data_execucao=date(2026, 9, 20),
        hora_pause=datetime(2026, 9, 20, 6, 0), hora_resume=datetime(2026, 9, 20, 18, 0))
        
    await salvar_agendamento_evento(db_session, id_grupo_wpp="TESTE-sched-002",
        nome_revenda="R", home_id="111", automacao_ids=["a1"],
        data_execucao=date(2026, 9, 20),
        hora_pause=datetime(2026, 9, 20, 7, 0), hora_resume=datetime(2026, 9, 20, 19, 0))
        
    res = await db_session.execute(text(
        "SELECT count(*) FROM agendamentos WHERE id_grupo_wpp='TESTE-sched-002'"))
    count = res.scalar()
    assert count == 2
    await db_session.execute(text("DELETE FROM agendamentos WHERE id_grupo_wpp='TESTE-sched-002'"))
    await db_session.commit()

@pytest.mark.integration
async def test_migration_idempotente(db_session):
    from app.crud.agendamentos import inicializar_tabela_agendamentos
    await inicializar_tabela_agendamentos(db_session)
    await inicializar_tabela_agendamentos(db_session)  # 2x sem erro

@pytest.mark.integration
async def test_backfill_legado_recebe_fase_resume(db_session):
    """Registro antigo (fase NULL) é tratado como resume após backfill — não fica órfão."""
    from app.crud.agendamentos import inicializar_tabela_agendamentos
    await inicializar_tabela_agendamentos(db_session)
    
    # Inserir sem fase
    await db_session.execute(text("""
        INSERT INTO agendamentos (id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao, executado)
        VALUES ('TESTE-LEGADO', 'R', '123', '[]', '2026-09-17 20:00:00', FALSE)
    """))
    await db_session.commit()
    
    # Rodar backfill
    await db_session.execute(text("""
        UPDATE agendamentos
        SET fase = 'resume', data_execucao = horario_execucao::date
        WHERE executado = false AND fase IS NULL
    """))
    await db_session.commit()
    
    res = await db_session.execute(text("SELECT fase, data_execucao FROM agendamentos WHERE id_grupo_wpp='TESTE-LEGADO'"))
    row = res.fetchone()
    assert row[0] == 'resume'
    assert row[1] == date(2026, 9, 17)
    
    await db_session.execute(text("DELETE FROM agendamentos WHERE id_grupo_wpp='TESTE-LEGADO'"))
    await db_session.commit()


# =============================================================================
# I1.1 - Resume do fluxo "hoje" tem que ficar efetivamente no banco
# =============================================================================

@pytest.mark.integration
async def test_pausa_hoje_persiste_resume_no_banco(db_session, cleanup_scheduler_tasks):
    """Apos um 'plantao hoje ate 21h', deve existir UMA linha resume no banco,
    data de hoje, executado=false.

    Bug de producao (21/09): a consulta voltava vazia. Causa-raiz: o caminho
    "hoje" (salvar_agendamento -> _salvar_linha) fazia o INSERT mas NAO commitava,
    e agendar_reativacao_automacao abre a propria sessao via async_session_maker;
    ao sair do `async with` sem commit, a transacao e revertida e a linha some.
    O caminho "futuro" (salvar_agendamento_evento) sempre commitou — por isso so
    o "hoje" desaparecia.

    Sensivel a mutacao: removendo o commit, este teste volta a ver 0 linhas.
    """
    from app.services.scheduler_service import scheduler_service
    from app.crud.agendamentos import inicializar_tabela_agendamentos
    from zoneinfo import ZoneInfo

    await inicializar_tabela_agendamentos(db_session)
    await db_session.execute(
        text("DELETE FROM agendamentos WHERE id_grupo_wpp='TESTE-persist'"))
    await db_session.commit()

    TZ = ZoneInfo("America/Recife")
    hoje_21h = datetime.now(TZ).replace(hour=21, minute=0, second=0, microsecond=0)

    await scheduler_service.agendar_reativacao_automacao(
        id_grupo="TESTE-persist", nome_revenda="R", home_id="H1",
        automacao_ids=["a1"], horario_execucao=hoje_21h)

    res = await db_session.execute(text(
        "SELECT fase, data_execucao, executado FROM agendamentos "
        "WHERE id_grupo_wpp='TESTE-persist' AND executado=false"))
    linhas = res.fetchall()

    assert len(linhas) == 1, f"esperava 1 linha resume persistida, veio {len(linhas)}"
    assert linhas[0][0] == "resume"
    assert linhas[0][1] == hoje_21h.date(), (
        f"data_execucao deve ser a data de HOJE em Recife ({hoje_21h.date()}), "
        f"veio {linhas[0][1]}")
    assert linhas[0][2] is False

    await db_session.execute(
        text("DELETE FROM agendamentos WHERE id_grupo_wpp='TESTE-persist'"))
    await db_session.commit()
