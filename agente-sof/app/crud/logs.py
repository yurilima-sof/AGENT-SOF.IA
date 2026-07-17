import logging
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def registrar_log(
    db: AsyncSession,
    id_grupo: str,
    nome_revenda: str,
    mensagem_original: str,
    intencao: Optional[str],
    status_op: str,
    tempo_resposta_ms: int,
    acao_executada: Optional[str] = None,
    ambiente: Optional[str] = None,
    texto_parecer: Optional[str] = None
) -> None:
    """
    Insere um log detalhado na tabela logs_operacoes.
    """
    try:
        await db.execute(
            text("""
                INSERT INTO logs_operacoes (
                    id_grupo_wpp, nome_revenda, mensagem_original,
                    intencao, acao_executada, ambiente,
                    status, tempo_resposta_ms, texto_parecer
                ) VALUES (
                    :id_grupo, :nome_revenda, :msg,
                    :intencao, :acao, :ambiente,
                    :status, :tempo, :parecer
                )
            """),
            {
                "id_grupo": id_grupo,
                "nome_revenda": nome_revenda,
                "msg": mensagem_original,
                "intencao": intencao,
                "acao": acao_executada,
                "ambiente": ambiente,
                "status": status_op,
                "tempo": tempo_resposta_ms,
                "parecer": texto_parecer
            }
        )
        await db.commit()
    except Exception as e:
        # Erros de log não devem falhar a requisição principal
        logger.error(f"❌ Falha crítica ao gravar log da operação: {e}")
