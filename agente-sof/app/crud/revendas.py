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

async def resolver_home_id_por_grupo(db: AsyncSession, id_grupo: str, nome_revenda_fallback: Optional[str] = None) -> Optional[str]:
    """
    Resolve o tuya_home_id do cliente de forma isolada (Multi-tenant), exclusivamente a
    partir do id_grupo_wpp autenticado (chave UNIQUE de mapa_revendas).

    NUNCA cai para busca fuzzy por nome_revenda (payload não confiável): revenda sem
    tuya_home_id cadastrado simplesmente não tem comando Tuya nativo disponível (o
    chamador trata home_id=None caindo no fallback IFTTT, se configurado). Ver achado L7.
    """
    try:
        result = await db.execute(
            text("""
                SELECT tuya_home_id
                FROM mapa_revendas
                WHERE id_grupo_wpp = :id_grupo
                  AND ativo = true
            """),
            {"id_grupo": id_grupo}
        )
        row = result.fetchone()
        if row:
            home_id = getattr(row, "tuya_home_id", None) or (row._mapping.get("tuya_home_id") if hasattr(row, "_mapping") else None)
            if home_id:
                logger.info(f"   [Tenant] Home ID resolvido via id_grupo_wpp ('{id_grupo}'): {home_id}")
                return home_id

        logger.warning(f"⚠️ Revenda '{id_grupo}' sem tuya_home_id cadastrado em mapa_revendas. Comando Tuya nativo indisponível (sem fallback por nome, ver L7).")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Erro ao resolver home_id para grupo '{id_grupo}': {e}")
        return None
