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
