import asyncio
import logging
from sqlalchemy import text
from google import genai
from google.genai import types
from app.config import get_settings
from app.database import async_session_maker

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGService:
    """
    Serviço para gerenciar a busca semântica vetorial utilizando a API de
    embeddings do Google Gemini (gemini-embedding-001) e o pgvector do PostgreSQL.
    """

    def __init__(self):
        # Cliente do SDK novo (google-genai), criado de forma preguiçosa caso a
        # chave esteja presente. Client é leve (não abre conexão no construtor).
        self._client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None



    async def get_relevant_context(self, query: str, group_id: str, limit: int = 3) -> str:
        """
        Gera o embedding para a consulta do usuário via Gemini, executa a busca vetorial por
        similaridade de cosseno filtrada pelo ID do grupo no PostgreSQL e retorna
        o contexto formatado.
        """


        # 1. Gera o embedding da pergunta do usuário usando o Gemini (768 dimensões com gemini-embedding-001)
        try:
            # Define timeout estrito de 3s para NUNCA travar a API se a Google oscilar em prod.
            # client.aio é async nativo — sem precisar de asyncio.to_thread (SDK antigo era síncrono).
            response = await asyncio.wait_for(
                self._client.aio.models.embed_content(
                    model="gemini-embedding-001",
                    contents=query,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY",
                        output_dimensionality=768,
                    ),
                ),
                timeout=3.0
            )
            query_embedding = response.embeddings[0].values
        except Exception as e:
            # Fallback seguro: NUNCA quebra a API se a chamada de embedding falhar/expirar
            logger.error(f"⚠️ Erro/Timeout ao gerar embedding da consulta com Gemini ({e}). Prosseguindo sem RAG.", extra={"status": "erro"}, exc_info=True)
            return ""

        # 2. Executa a busca por similaridade de cosseno (operador <=>) no banco de dados
        async with async_session_maker() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT conteudo, id_grupo_wpp
                        FROM rag_documentos
                        WHERE id_grupo_wpp IN (:group_id, 'GLOBAL_MANUAL')
                        ORDER BY embedding <=> :query_embedding
                        LIMIT :limit
                    """),
                    {
                        "group_id": group_id,
                        "query_embedding": str(query_embedding),
                        "limit": limit
                    }
                )
                rows = result.fetchall()
                
                # Junta os blocos recuperados com uma divisória clara
                context_chunks = []
                for row in rows:
                    conteudo = row[0]
                    grupo_db = row[1]
                    etiqueta = "[REGRA GLOBAL]" if grupo_db == 'GLOBAL_MANUAL' else "[REGRA ESPECÍFICA DA REVENDA]"
                    context_chunks.append(f"{etiqueta}\n{conteudo}")
                
                if not context_chunks:
                    return ""
                
                context_formatted = "\n\n---\n\n".join(context_chunks)
                return context_formatted
            except Exception as e:
                logger.warning(f"Erro ao consultar o banco vetorial: {e}")
                return ""
    async def ingest_message(self, group_id: str, message: str) -> None:
        """
        Gera embedding para a nova mensagem e insere no banco vetorial.
        """
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.embed_content(
                    model="gemini-embedding-001",
                    contents=message,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=768,
                    ),
                ),
                timeout=5.0
            )
            embedding = response.embeddings[0].values
        except Exception as e:
            logger.error(f"Erro ao gerar embedding para ingestão: {e}", extra={"status": "erro"}, exc_info=True)
            raise
            
        async with async_session_maker() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO rag_documentos (id_grupo_wpp, conteudo, embedding)
                        VALUES (:group_id, :conteudo, :embedding)
                    """),
                    {
                        "group_id": group_id,
                        "conteudo": message,
                        "embedding": str(embedding)
                    }
                )
                await session.commit()
            except Exception as e:
                logger.warning(f"Erro ao salvar documento vetorial no banco: {e}")
                raise


# Singleton para uso no app
rag_service = RAGService()

