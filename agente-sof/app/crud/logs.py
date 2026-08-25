import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

import json

async def registrar_log(
    db: AsyncSession,
    id_grupo: str,
    nome_revenda: str,
    mensagem_original: str,
    intencao: Optional[str],
    status_op: str,
    tempo_resposta_ms: int,
    acao_executada: Optional[str] = None,
    ambiente: Optional[str] = None
) -> None:
    """
    Insere um log detalhado na tabela logs_operacoes.
    """
    try:
        detalhes_json = json.dumps({
            "acao_ifttt": acao_executada,
            "ambiente": ambiente
        })
        
        await db.execute(
            text("""
                INSERT INTO logs_operacoes (
                    id_grupo, nome_revenda, mensagem_original,
                    intencao, status, tempo_resposta_ms, detalhes
                ) VALUES (
                    :id_grupo, :nome_revenda, :msg,
                    :intencao, :status, :tempo, :detalhes
                )
            """),
            {
                "id_grupo": id_grupo,
                "nome_revenda": nome_revenda,
                "msg": mensagem_original,
                "intencao": intencao,
                "status": status_op,
                "tempo": tempo_resposta_ms,
                "detalhes": detalhes_json
            }
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        # Erros de log não devem falhar a requisição principal
        logger.error(f"❌ Falha crítica ao gravar log da operação: {e}", extra={"status": "erro"}, exc_info=True)


async def obter_logs_recentes(db: AsyncSession, limite: int = 50, id_grupo: Optional[str] = None) -> list[dict]:
    """
    Retorna as últimas N linhas de logs_operacoes, mais recentes primeiro.
    Usada pelo painel admin (tabela de logs com auto-refresh). Se `id_grupo`
    for informado, filtra apenas as operações daquele grupo.
    """
    try:
        if id_grupo:
            query = text("""
                SELECT timestamp, id_grupo, nome_revenda, mensagem_original,
                       intencao, status, tempo_resposta_ms, detalhes
                FROM logs_operacoes
                WHERE id_grupo = :id_grupo
                ORDER BY timestamp DESC
                LIMIT :limite
            """)
            params = {"id_grupo": id_grupo, "limite": int(limite)}
        else:
            query = text("""
                SELECT timestamp, id_grupo, nome_revenda, mensagem_original,
                       intencao, status, tempo_resposta_ms, detalhes
                FROM logs_operacoes
                ORDER BY timestamp DESC
                LIMIT :limite
            """)
            params = {"limite": int(limite)}

        result = await db.execute(query, params)
        rows = result.fetchall()
        return [
            {
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "id_grupo": row.id_grupo,
                "nome_revenda": row.nome_revenda,
                "mensagem_original": row.mensagem_original,
                "intencao": row.intencao,
                "status": row.status,
                "tempo_resposta_ms": row.tempo_resposta_ms,
                "detalhes": row.detalhes,
            }
            for row in rows
        ]
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Erro ao consultar logs recentes: {e}", extra={"status": "erro"}, exc_info=True)
        return []
