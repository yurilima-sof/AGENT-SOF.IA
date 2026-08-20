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
        logger.error(f"❌ Falha crítica ao gravar log da operação: {e}")
