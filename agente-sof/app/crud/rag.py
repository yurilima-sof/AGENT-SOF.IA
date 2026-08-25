# =============================================================================
# app/crud/rag.py - Leitura/gestão administrativa da memória vetorial (RAG)
# =============================================================================
# Consultas simples de manutenção sobre rag_documentos, usadas pelo painel
# admin. A geração/busca de embeddings continua em app/services/rag_service.py.

import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def listar_memoria_por_grupo(db: AsyncSession, id_grupo: str, limite: int = 50) -> list[dict]:
    """
    Lista as entradas de memória RAG (rag_documentos) de um grupo específico,
    da mais recente para a mais antiga. Não inclui o embedding (payload pesado
    e sem utilidade para exibição administrativa).
    """
    try:
        result = await db.execute(
            text("""
                SELECT id, conteudo, metadados, criado_em
                FROM rag_documentos
                WHERE id_grupo_wpp = :id_grupo
                ORDER BY criado_em DESC
                LIMIT :limite
            """),
            {"id_grupo": id_grupo, "limite": int(limite)}
        )
        rows = result.fetchall()
        return [
            {
                "id": str(row.id),
                "conteudo": row.conteudo,
                "metadados": row.metadados,
                "criado_em": row.criado_em.isoformat() if row.criado_em else None,
            }
            for row in rows
        ]
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Erro ao listar memória RAG do grupo '{id_grupo}': {e}", extra={"status": "erro"}, exc_info=True)
        return []


async def deletar_memoria(db: AsyncSession, doc_id: str) -> bool:
    """
    Remove uma entrada específica de rag_documentos pelo seu id (UUID).
    Retorna True se algo foi de fato removido.
    """
    try:
        result = await db.execute(
            text("DELETE FROM rag_documentos WHERE id = :id RETURNING id"),
            {"id": doc_id}
        )
        removido = result.fetchone() is not None
        await db.commit()
        return removido
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Erro ao deletar memória RAG '{doc_id}': {e}", extra={"status": "erro"}, exc_info=True)
        return False
