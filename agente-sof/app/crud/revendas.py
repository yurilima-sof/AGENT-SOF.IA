import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def inicializar_colunas_revendas(db: AsyncSession) -> None:
    """
    Garante que colunas necessárias (como tuya_home_id) existam na tabela mapa_revendas (Auto-Migration).
    """
    try:
        await db.execute(text("""
            ALTER TABLE mapa_revendas ADD COLUMN IF NOT EXISTS tuya_home_id VARCHAR(100);
        """))
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_mapa_revendas_home_id ON mapa_revendas(tuya_home_id);
        """))
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Não foi possível inicializar colunas de mapa_revendas: {e}", extra={"status": "erro"}, exc_info=True)

async def verificar_revenda_ativa(db: AsyncSession, id_grupo: str) -> bool:
    try:
        result = await db.execute(
            text("SELECT ativo FROM mapa_revendas WHERE id_grupo_wpp = :id_grupo"),
            {"id_grupo": id_grupo}
        )
        row = result.fetchone()
        if row:
            return bool(row[0])
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Erro ao checar status da revenda: {e}", extra={"status": "erro"}, exc_info=True)
        return True

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
        await db.rollback()
        logger.error(f"⚠️ Erro ao consultar mapa_revendas: {e}", extra={"status": "erro"}, exc_info=True)
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
        await db.rollback()
        logger.error(f"⚠️ Erro ao resolver home_id para grupo '{id_grupo}': {e}", extra={"status": "erro"}, exc_info=True)
        return None


async def buscar_revenda_por_grupo(db: AsyncSession, id_grupo: str) -> Optional[dict]:
    """
    Retorna nome_revenda, estado, tuya_home_id e ativo de uma revenda pelo id_grupo_wpp.
    Usada pelo painel admin (disparo manual de ação, exibição de detalhes) para não
    depender de dados enviados pelo cliente.
    """
    try:
        result = await db.execute(
            text("""
                SELECT nome_revenda, estado, tuya_home_id, ativo
                FROM mapa_revendas
                WHERE id_grupo_wpp = :id_grupo
            """),
            {"id_grupo": id_grupo}
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "id_grupo_wpp": id_grupo,
            "nome_revenda": row.nome_revenda,
            "estado": row.estado,
            "tuya_home_id": row.tuya_home_id,
            "ativo": row.ativo,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Erro ao buscar revenda por grupo '{id_grupo}': {e}", extra={"status": "erro"}, exc_info=True)
        return None


async def atualizar_mapeamento_revenda(db: AsyncSession, id_grupo: str, tuya_home_id: str) -> bool:
    """
    Atualiza o tuya_home_id de uma revenda existente (correção manual de mapeamento
    pelo painel admin). Retorna True se a revenda foi encontrada e atualizada.
    """
    try:
        result = await db.execute(
            text("""
                UPDATE mapa_revendas
                SET tuya_home_id = :tuya_home_id, atualizado_em = NOW()
                WHERE id_grupo_wpp = :id_grupo
                RETURNING id_grupo_wpp
            """),
            {"tuya_home_id": tuya_home_id, "id_grupo": id_grupo}
        )
        atualizado = result.fetchone() is not None
        await db.commit()
        if atualizado:
            logger.info(f"✅ tuya_home_id da revenda '{id_grupo}' atualizado para '{tuya_home_id}' via painel admin.")
        return atualizado
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Erro ao atualizar mapeamento da revenda '{id_grupo}': {e}", extra={"status": "erro"}, exc_info=True)
        return False
