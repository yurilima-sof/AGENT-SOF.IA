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

@pytest.fixture
def revenda_teste():
    return "TESTE-API-REV"

from unittest.mock import patch, AsyncMock

@pytest.mark.integration
async def test_agent_futuro_agenda_e_nao_pausa_hoje(client, auth_headers, revenda_teste):
    with patch("app.services.tuya_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "Evento no sábado dia 19/09, pode estender o horário para desligar as 19:00",
            "id_grupo": revenda_teste, "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200
        mock_set.assert_not_called()

@pytest.mark.integration
def test_agent_indefinido_pede_esclarecimento(client, auth_headers, revenda_teste):
    r = client.post("/agent", headers=auth_headers, json={
        "mensagem": "Deixa programado", "id_grupo": revenda_teste,
        "nome_revenda": "Revenda Teste Admin"})
    assert r.status_code == 200 and r.json()["mensagem_wpp"] is not None
    # Assuming escopo=indefinido -> ifttt_action is None or something

@pytest.mark.integration
async def test_agent_hoje_continua_pausando(client, auth_headers, revenda_teste, monkeypatch):
    from app.main import settings as main_settings
    monkeypatch.setattr(main_settings, "gemini_api_key", "fake-key")
    with patch("app.services.tuya_service.tuya_service.set_automation_status", new_callable=AsyncMock) as mock_set, \
         patch("app.main.resolver_home_id_por_grupo", new_callable=AsyncMock, return_value="HOME123") as mock_home, \
         patch("app.services.llm_service.llm_service.processar_mensagem", new_callable=AsyncMock) as mock_llm, \
         patch("app.services.tuya_service.tuya_service.get_automations_by_home", new_callable=AsyncMock, return_value=[{"id": "auto1", "name": "OFF 19h", "enabled": True}]):
        mock_llm.return_value = {
            "intencao": "pausar_automacao", "ifttt_action": "desativar_automacao",
            "escopo_temporal": "hoje", "mensagem_wpp": "Pausado"
        }
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "E hoje até 19:30 ligado", "id_grupo": revenda_teste,
            "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200 and mock_set.called

@pytest.mark.integration
async def test_pausar_futuro_nunca_desativa_hoje_mesmo_com_acao(client, auth_headers, revenda_teste):
    """Bug 2: escopo futuro/indefinido + intenção de pausa NÃO pode tocar automação hoje,
    mesmo se o LLM devolver um ifttt_action junto."""
    fake_llm = {
        "intencao": "pausar_automacao", "escopo_temporal": "futuro",
        "data_evento": "2026-09-19", "hora_fim": "19:00",
        "ifttt_action": "off",  # <- o gatilho do bug: ação preenchida junto
        "ambiente": None, "mensagem_wpp": "ok", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.llm_service.processar_mensagem",
               new_callable=AsyncMock, return_value=fake_llm), \
         patch("app.services.tuya_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set, \
         patch("app.services.tuya_service.tuya_service.execute_scene",
               new_callable=AsyncMock) as mock_scene:
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "Evento no sábado dia 19/09, pode estender o horário para desligar as 19:00",
            "id_grupo": revenda_teste, "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200
        mock_set.assert_not_called()      # nenhuma automação desativada hoje
        mock_scene.assert_not_called()    # nenhuma cena disparada hoje

@pytest.mark.integration
async def test_pausar_hoje_continua_desativando(client, auth_headers, revenda_teste, monkeypatch):
    """Regressão: escopo hoje AINDA pausa (não pode ter regredido junto com o fix)."""
    from app.main import settings as main_settings
    monkeypatch.setattr(main_settings, "gemini_api_key", "fake-key")
    fake_llm = {
        "intencao": "pausar_automacao", "escopo_temporal": "hoje",
        "data_evento": None, "hora_fim": "19:30",
        "ifttt_action": "desativar_automacao", "ambiente": None, "mensagem_wpp": "Pausado até 19:30", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.llm_service.processar_mensagem",
               new_callable=AsyncMock, return_value=fake_llm), \
         patch("app.main.resolver_home_id_por_grupo", new_callable=AsyncMock, return_value="HOME123"), \
         patch("app.services.tuya_service.tuya_service.get_automations_by_home",
               new_callable=AsyncMock, return_value=[{"id": "a1", "name": "OFF [18:00]"}]), \
         patch("app.services.tuya_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set, \
         patch("app.services.tuya_service.tuya_service.check_home_devices_online",
               new_callable=AsyncMock, return_value={"all_offline": False}), \
         patch("app.services.scheduler_service.scheduler_service.agendar_reativacao_automacao",
               new_callable=AsyncMock):
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "E hoje até 19:30 ligado",
            "id_grupo": revenda_teste, "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200
        assert mock_set.called  # hoje continua desativando


