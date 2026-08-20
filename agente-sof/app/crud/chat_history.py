import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def inicializar_tabela_historico(db: AsyncSession) -> None:
    """
    Garante que a tabela chat_historico_recente existe no PostgreSQL (Auto-Migration).
    """
    try:
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_historico_recente (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                id_grupo_wpp VARCHAR(100) NOT NULL,
                autor VARCHAR(20) NOT NULL,
                conteudo TEXT NOT NULL,
                criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
        """))
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chat_historico_grupo_tempo 
            ON chat_historico_recente(id_grupo_wpp, criado_em DESC);
        """))
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(f"⚠️ Não foi possível inicializar a tabela chat_historico_recente: {e}")

async def salvar_mensagem_historico(
    db: AsyncSession,
    id_grupo_wpp: str,
    autor: str,
    conteudo: str
) -> None:
    """
    Grava uma mensagem de entrada (usuário) ou resposta (sofia) no histórico recente de curto prazo.
    O conteúdo é truncado em no máximo 200 caracteres para otimização de banco e de tokens.
    """
    if not id_grupo_wpp or not conteudo:
        return
        
    try:
        texto_sanitizado = conteudo.strip()[:200]
        await db.execute(
            text("""
                INSERT INTO chat_historico_recente (id_grupo_wpp, autor, conteudo)
                VALUES (:id_grupo, :autor, :conteudo)
            """),
            {
                "id_grupo": id_grupo_wpp,
                "autor": autor,
                "conteudo": texto_sanitizado
            }
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(f"⚠️ Erro ao salvar histórico recente de chat: {e}")

async def obter_historico_recente(
    db: AsyncSession,
    id_grupo_wpp: str,
    limite: int = 6,
    minutos: int = 15
) -> str:
    """
    Retorna o histórico das últimas N mensagens dos últimos M minutos para um grupo de WhatsApp.
    Retorna a string formatada em ordem cronológica para injeção no prompt do Gemini.
    """
    if not id_grupo_wpp:
        return ""

    try:
        query = text("""
            SELECT autor, conteudo, criado_em
            FROM chat_historico_recente
            WHERE id_grupo_wpp = :id_grupo
              AND criado_em >= NOW() - (INTERVAL '1 minute' * :minutos)
            ORDER BY criado_em DESC
            LIMIT :limite
        """)
        result = await db.execute(query, {"id_grupo": id_grupo_wpp, "minutos": int(minutos), "limite": int(limite)})
        rows = result.fetchall()

        if not rows:
            return ""

        # Reverte para exibir na ordem cronológica (mais antigas primeiro)
        rows_cronologicas = list(reversed(rows))
        
        linhas_historico = []
        for row in rows_cronologicas:
            autor_db = row[0]
            conteudo_db = row[1]
            autor_nome = "Usuário" if autor_db == "usuario" else "Sofia"
            linhas_historico.append(f"- {autor_nome}: \"{conteudo_db}\"")

        return "\n".join(linhas_historico)
    except Exception as e:
        await db.rollback()
        logger.warning(f"⚠️ Erro ao buscar histórico recente de chat: {e}")
        return ""

async def limpar_historico_antigo(db: AsyncSession, minutos: int = 60) -> None:
    """
    Remove mensagens de histórico com mais de N minutos para manter a tabela leve.
    """
    try:
        await db.execute(
            text("""
                DELETE FROM chat_historico_recente
                WHERE criado_em < NOW() - (INTERVAL '1 minute' * :minutos)
            """),
            {"minutos": int(minutos)}
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(f"⚠️ Erro ao limpar histórico antigo de chat: {e}")
