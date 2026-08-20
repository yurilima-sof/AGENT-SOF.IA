import os
import pytest
from typing import Generator

# Define variáveis de ambiente de teste ANTES de importar a aplicação
os.environ["APP_ENV"] = "testing"
os.environ["API_KEY"] = "dev-api-key-insegura"
os.environ["SECRET_KEY"] = "chave-insegura-apenas-para-desenvolvimento"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://agente_user:agente_pass@localhost:5432/agente_sof_db"

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

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c
