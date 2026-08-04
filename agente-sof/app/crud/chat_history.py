import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

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
              AND criado_em >= NOW() - (:minutos || ' minutes')::INTERVAL
            ORDER BY criado_em DESC
            LIMIT :limite
        """)
        result = await db.execute(query, {"id_grupo": id_grupo_wpp, "minutos": minutos, "limite": limite})
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
                WHERE criado_em < NOW() - (:minutos || ' minutes')::INTERVAL
            """),
            {"minutos": minutos}
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"⚠️ Erro ao limpar histórico antigo de chat: {e}")
