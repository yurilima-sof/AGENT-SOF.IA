import logging
from datetime import datetime, date
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import json

logger = logging.getLogger(__name__)

async def inicializar_tabela_agendamentos(db: AsyncSession) -> None:
    """
    Garante que a tabela agendamentos existe no PostgreSQL e atualiza schema
    com colunas fase e data_execucao se necessário.
    """
    try:
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS agendamentos (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                id_grupo_wpp VARCHAR(100) NOT NULL,
                nome_revenda VARCHAR(100) NOT NULL,
                home_id VARCHAR(100) NOT NULL,
                automacao_ids JSONB NOT NULL,
                horario_execucao TIMESTAMP WITH TIME ZONE NOT NULL,
                executado BOOLEAN DEFAULT FALSE,
                criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
        """))
        
        # Add new columns IF NOT EXISTS
        await db.execute(text("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS data_execucao DATE;"))
        await db.execute(text("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS fase VARCHAR(10);"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS idx_agendamentos_exec_fase ON agendamentos (executado, data_execucao, fase);"))
        
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Não foi possível inicializar a tabela agendamentos: {e}", extra={"status": "erro"}, exc_info=True)

async def salvar_agendamento(
    db: AsyncSession,
    id_grupo_wpp: str,
    nome_revenda: str,
    home_id: str,
    automacao_ids: list,
    horario_execucao: datetime
) -> Optional[str]:
    # Legacy wrapper — usado pelo fluxo de pausa de "hoje"
    # (scheduler_service.agendar_reativacao_automacao).
    #
    # O commit fica AQUI, e não em _salvar_linha, porque _salvar_linha é
    # compartilhada com salvar_agendamento_evento, que precisa inserir as duas
    # fases (pause + resume) na MESMA transação e commita uma vez só no fim.
    # Cada função pública é responsável pelo próprio commit.
    #
    # Sem este commit o INSERT era revertido ao fechar a sessão
    # (async_session_maker) e o resume do "hoje" nunca chegava ao banco —
    # bug de produção de 21/09, em que a consulta de agendamentos voltava vazia.
    agendamento_id = await _salvar_linha(
        db, id_grupo_wpp, nome_revenda, home_id, automacao_ids,
        horario_execucao, "resume", horario_execucao.date(),
    )
    await db.commit()
    return agendamento_id

async def _salvar_linha(db, id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao, fase, data_execucao):
    try:
        result = await db.execute(
            text("""
                INSERT INTO agendamentos (id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao, fase, data_execucao)
                VALUES (:id_grupo_wpp, :nome_revenda, :home_id, :automacao_ids, :horario_execucao, :fase, :data_execucao)
                RETURNING id
            """),
            {
                "id_grupo_wpp": id_grupo_wpp,
                "nome_revenda": nome_revenda,
                "home_id": home_id,
                "automacao_ids": json.dumps(automacao_ids),
                "horario_execucao": horario_execucao,
                "fase": fase,
                "data_execucao": data_execucao
            }
        )
        row = result.fetchone()
        return str(row[0]) if row else None
    except Exception as e:
        logger.error(f"❌ Erro ao salvar agendamento no banco: {e}")
        raise

async def salvar_agendamento_evento(
    db: AsyncSession,
    id_grupo_wpp: str,
    nome_revenda: str,
    home_id: str,
    automacao_ids: list,
    data_execucao: date,
    hora_pause: datetime,
    hora_resume: datetime
) -> list[str]:
    """
    Salva duas fases (pause e resume) deletando qualquer pendência futura no mesmo dia para a home.
    """
    try:
        # Delete old pending items for same home and date
        await db.execute(text("""
            DELETE FROM agendamentos 
            WHERE id_grupo_wpp = :id_g AND home_id = :h_id 
              AND data_execucao = :d_exec AND executado = FALSE
        """), {"id_g": id_grupo_wpp, "h_id": home_id, "d_exec": data_execucao})
        
        id1 = await _salvar_linha(db, id_grupo_wpp, nome_revenda, home_id, automacao_ids, hora_pause, "pause", data_execucao)
        id2 = await _salvar_linha(db, id_grupo_wpp, nome_revenda, home_id, automacao_ids, hora_resume, "resume", data_execucao)
        await db.commit()
        return [id1, id2]
    except Exception as e:
        await db.rollback()
        logger.error(f"Erro ao salvar evento futuro: {e}")
        return []

async def obter_agendamentos_pendentes(db: AsyncSession) -> list:
    try:
        query = text("""
            SELECT id, id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao, fase, data_execucao
            FROM agendamentos
            WHERE executado = FALSE
        """)
        result = await db.execute(query)
        return result.fetchall()
    except Exception as e:
        await db.rollback()
        return []

async def marcar_agendamento_executado(db: AsyncSession, agendamento_id: str) -> None:
    try:
        await db.execute(
            text("""
                UPDATE agendamentos
                SET executado = TRUE
                WHERE id = :id
            """),
            {"id": agendamento_id}
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
