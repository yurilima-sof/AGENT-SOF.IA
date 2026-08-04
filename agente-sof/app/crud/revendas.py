import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def buscar_credenciais_revenda(db: AsyncSession, id_grupo: str) -> Optional[dict]:
    """
    Consulta a tabela mapa_revendas para obter todas as credenciais_tuya do grupo.
    """
    try:
        result = await db.execute(
            text("""
                SELECT credenciais_tuya
                FROM mapa_revendas
                WHERE id_grupo_wpp = :id_grupo
                  AND ativo = true
            """),
            {"id_grupo": id_grupo}
        )
        row = result.fetchone()
        if row:
            if hasattr(row, "credenciais_tuya"):
                return row.credenciais_tuya
            elif isinstance(row, dict):
                return row.get("credenciais_tuya")
            elif hasattr(row, "_mapping"):
                return row._mapping.get("credenciais_tuya")
            elif isinstance(row, (tuple, list)):
                return row[0]
        return None
    except Exception as e:
        logger.warning(f"⚠️ Erro ao consultar mapa_revendas: {e}")
        return None
