import os
import pytest
from typing import Generator

# Define variáveis de ambiente de teste ANTES de importar a aplicação
os.environ["APP_ENV"] = "testing"
os.environ["API_KEY"] = "dev-api-key-insegura"
os.environ["SECRET_KEY"] = "chave-insegura-apenas-para-desenvolvimento"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://agente_user:agente_senha_dev@localhost:5432/agente_sof_db"

from app.config import get_settings
get_settings.cache_clear()

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def settings():
    return get_settings()

@pytest.fixture
def auth_headers(settings):
    return {"Authorization": f"Bearer {settings.api_key}"}

from unittest.mock import patch, AsyncMock

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with patch("app.crud.chat_history.inicializar_tabela_historico", new_callable=AsyncMock), \
         patch("app.crud.revendas.inicializar_colunas_revendas", new_callable=AsyncMock), \
         patch("app.crud.agendamentos.inicializar_tabela_agendamentos", new_callable=AsyncMock), \
         patch("app.services.scheduler_service.scheduler_service.carregar_agendamentos_pendentes", new_callable=AsyncMock):
        with TestClient(app) as c:
            yield c


os.environ.setdefault("ADMIN_API_KEY", "dev-admin-key-insegura-para-teste")

@pytest.fixture
def admin_headers(settings):
    return {"Authorization": f"Bearer {os.environ['ADMIN_API_KEY']}"}

from app.database import async_session_maker

@pytest.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session

from datetime import datetime
from zoneinfo import ZoneInfo

TZ_RECIFE = ZoneInfo("America/Recife")

@pytest.fixture
def agora_fixo():
    return datetime(2026, 9, 17, 10, 34, 0, tzinfo=TZ_RECIFE)

@pytest.fixture
def scheduler_isolado():
    from app.services.scheduler_service import scheduler_service
    scheduler_service._tasks.clear()
    yield scheduler_service
    for task in scheduler_service._tasks.values():
        task.cancel()
    scheduler_service._tasks.clear()



@pytest.fixture(autouse=True)
async def cleanup_scheduler_tasks():
    # Roda antes do teste
    yield
    # Roda depois do teste
    from app.services.scheduler_service import scheduler_service
    import asyncio
    
    tasks_to_await = []
    for task in scheduler_service._tasks.values():
        task.cancel()
        tasks_to_await.append(task)
    
    if tasks_to_await:
        await asyncio.gather(*tasks_to_await, return_exceptions=True)
        
    scheduler_service._tasks.clear()
