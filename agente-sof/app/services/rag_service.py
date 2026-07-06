import logging
from sqlalchemy import text
import google.generativeai as genai
from app.config import get_settings
from app.database import async_session_maker

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGService:
    """
    Serviço para gerenciar a busca semântica vetorial utilizando a API de
    embeddings do Google Gemini (text-embedding-004) e o pgvector do PostgreSQL.
    """

    def __init__(self):
        # Configura o SDK Gemini de forma preguiçosa caso a chave esteja presente
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)



    async def get_relevant_context(self, query: str, group_id: str, limit: int = 3) -> str:
        """
        Gera o embedding para a consulta do usuário via Gemini, executa a busca vetorial por
        similaridade de cosseno filtrada pelo ID do grupo no PostgreSQL e retorna
        o contexto formatado.
        """
        # Se não for o grupo de teste, não busca no RAG (como solicitado pelo usuário)
        if group_id != "120363422455765261-group":
            return ""

        # 1. Gera o embedding da pergunta do usuário usando o Gemini (768 dimensões)
        try:
            response = genai.embed_content(
                model="models/gemini-embedding-001",
                content=query,
                task_type="retrieval_query",
                output_dimensionality=768,
            )
            query_embedding = response["embedding"]
        except Exception as e:
            # Fallback seguro caso a chamada de API falhe
            logger.warning(f"Erro ao gerar embedding da consulta com Gemini: {e}")
            return ""

        # 2. Executa a busca por similaridade de cosseno (operador <=>) no banco de dados
        async with async_session_maker() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT conteudo
                        FROM rag_documentos
                        WHERE id_grupo_wpp = :group_id
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
                context_chunks = [row[0] for row in rows]
                if not context_chunks:
                    return ""
                
                context_formatted = "\n\n---\n\n".join(context_chunks)
                return context_formatted
            except Exception as e:
                logger.warning(f"Erro ao consultar o banco vetorial: {e}")
                return ""


# Singleton para uso no app
rag_service = RAGService()

