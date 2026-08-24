import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import json

logger = logging.getLogger(__name__)

async def inicializar_tabela_agendamentos(db: AsyncSession) -> None:
    """
    Garante que a tabela agendamentos existe no PostgreSQL.
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
    """
    Salva um novo agendamento de reativação no banco.
    """
    try:
        result = await db.execute(
            text("""
                INSERT INTO agendamentos (id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao)
                VALUES (:id_grupo_wpp, :nome_revenda, :home_id, :automacao_ids, :horario_execucao)
                RETURNING id
            """),
            {
                "id_grupo_wpp": id_grupo_wpp,
                "nome_revenda": nome_revenda,
                "home_id": home_id,
                "automacao_ids": json.dumps(automacao_ids),
                "horario_execucao": horario_execucao
            }
        )
        await db.commit()
        row = result.fetchone()
        return str(row[0]) if row else None
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Erro ao salvar agendamento no banco: {e}", extra={"status": "erro"}, exc_info=True)
        return None

async def obter_agendamentos_pendentes(db: AsyncSession) -> list:
    """
    Retorna todos os agendamentos que ainda não foram executados.
    """
    try:
        query = text("""
            SELECT id, id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao
            FROM agendamentos
            WHERE executado = FALSE
        """)
        result = await db.execute(query)
        return result.fetchall()
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Erro ao buscar agendamentos pendentes: {e}", extra={"status": "erro"}, exc_info=True)
        return []

async def marcar_agendamento_executado(db: AsyncSession, agendamento_id: str) -> None:
    """
    Marca um agendamento como executado.
    """
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
        logger.error(f"❌ Erro ao marcar agendamento como executado: {e}", extra={"status": "erro"}, exc_info=True)
