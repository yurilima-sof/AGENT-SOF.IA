# =============================================================================
# app/database.py - Conectividade com o Banco de Dados
# =============================================================================

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings

settings = get_settings()

# --- Conexão Assíncrona (FastAPI e Operações em tempo de execução) ---
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,  # Evita conexões mortas no pool
    pool_size=10,
    max_overflow=20,
)
async_session_maker = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db():
    """
    Dependency Injection para rotas do FastAPI.
    Garante que cada request tenha sua própria sessão e que ela seja fechada após o uso.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

# --- Conexão Síncrona (Utilitários, scripts de migração/seeding e CLI) ---
def get_sync_engine():
    """
    Retorna um engine síncrono compatível com psycopg2.
    Converte postgresql+asyncpg:// para postgresql:// automaticamente.
    """
    sync_url = settings.database_url.replace("+asyncpg", "")
    return create_engine(sync_url)
