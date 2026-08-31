import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Testa o endpoint /health"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data
    assert data["mode"] == "ifttt_bridge"

def test_agent_unauthorized_missing_token():
    """Testa se o endpoint /agent rejeita chamadas sem token (HTTP 403 do HTTPBearer)"""
    payload = {
        "mensagem": "tá muito quente aqui",
        "id_grupo": "120363422455765261-group",
        "nome_revenda": "Grupo Thiago (Teste)",
    }
    response = client.post("/agent", json=payload)
    assert response.status_code == 403

def test_agent_unauthorized_invalid_token():
    """Testa se o endpoint /agent rejeita chamadas com token inválido (HTTP 401 do verify_api_key)"""
    payload = {
        "mensagem": "tá muito quente aqui",
        "id_grupo": "120363422455765261-group",
        "nome_revenda": "Grupo Thiago (Teste)",
    }
    headers = {"Authorization": "Bearer token-invalido-123"}
    response = client.post("/agent", json=payload, headers=headers)
    assert response.status_code == 401

def test_agent_valid_keyword_fallback(client, auth_headers, monkeypatch):
    """Testa se o endpoint /agent aceita o token correto e processa mensagens via Fallback de palavras-chave harmonizado"""
    from unittest.mock import patch, AsyncMock
    from app.main import settings as main_settings
    from app.services.llm_service import settings as llm_settings
    monkeypatch.setattr(main_settings, "gemini_api_key", None)
    monkeypatch.setattr(llm_settings, "gemini_api_key", None)
    with patch("app.main.buscar_link_ifttt", new_callable=AsyncMock, return_value="https://maker.ifttt.com/trigger/medio/with/key/fake"):
        payload = {
            "mensagem": "tá muito quente aqui",
            "id_grupo": "120363422455765261-group",
            "nome_revenda": "Grupo Thiago (Teste)",
        }
        response = client.post("/agent", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["intencao"] == "ligar_temperatura_media"
        assert data["ifttt_action"] == "medio"
        assert "mensagem_wpp" in data

def test_rag_aprender_unauthorized():
    """Testa segurança do endpoint RAG /rag/aprender sem token"""
    payload = {
        "id_grupo": "120363422455765261-group",
        "mensagem": "regra de teste",
    }
    response = client.post("/rag/aprender", json=payload)
    assert response.status_code == 403

def test_proactive_fechamento_unauthorized():
    """Testa segurança do endpoint proativo /proactive/fechamento sem token"""
    response = client.post("/proactive/fechamento")
    assert response.status_code == 403
