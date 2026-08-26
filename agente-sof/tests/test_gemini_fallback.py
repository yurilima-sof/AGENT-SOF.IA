from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy import text

import app.main as main_mod
from app.services.llm_service import llm_service


def _mock_client_falho(mensagem_erro: str) -> MagicMock:
    """Cliente genai mockado cujo generate_content sempre levanta uma exceção."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError(mensagem_erro))
    return mock_client

ID_GRUPO_TESTE = "TESTE-gemini-fallback-001"


@pytest.fixture
async def revenda_teste(db_session):
    await db_session.execute(text("""
        INSERT INTO mapa_revendas (id_grupo_wpp, nome_revenda, tuya_home_id, credenciais_tuya, ativo)
        VALUES (:id_grupo, 'Revenda Teste Fallback', '999997', '{}', true)
        ON CONFLICT (id_grupo_wpp) DO UPDATE SET ativo = true
    """), {"id_grupo": ID_GRUPO_TESTE})
    await db_session.commit()
    yield ID_GRUPO_TESTE
    await db_session.execute(
        text("DELETE FROM mapa_revendas WHERE id_grupo_wpp = :id_grupo"),
        {"id_grupo": ID_GRUPO_TESTE},
    )
    await db_session.commit()


@pytest.mark.integration
def test_fallback_keyword_executa_quando_gemini_falha_totalmente(client, auth_headers, revenda_teste, monkeypatch):
    """
    Regressão do achado em produção: quando o Gemini falha (timeout/exceção nas
    duas tentativas), o fallback de palavras-chave deve assumir e executar a ação
    — não pode mais cair silenciosamente na mensagem genérica de "instabilidade
    técnica" para uma mensagem que o fallback claramente reconhece (ex: calor).
    """
    # Força o caminho do Gemini a ser tentado, independente do GEMINI_API_KEY
    # efetivo no .env local (evita depender de qual das linhas duplicadas do
    # .env "vence" na leitura do pydantic-settings).
    monkeypatch.setattr(main_mod.settings, "gemini_api_key", "fake-key-para-teste")
    monkeypatch.setattr(llm_service, "_client", _mock_client_falho("Gemini indisponível (simulado)"))

    with patch("app.services.llm_service.rag_service.get_relevant_context", new_callable=AsyncMock, return_value=""), \
         patch("app.services.tuya_dispatch_service.tuya_service.check_home_devices_online", new_callable=AsyncMock) as mock_check, \
         patch("app.services.tuya_dispatch_service.get_scene_by_ambiente", new_callable=AsyncMock) as mock_scene, \
         patch("app.services.tuya_dispatch_service.tuya_service.execute_scene", new_callable=AsyncMock) as mock_exec:
        mock_check.return_value = {"all_offline": False, "checked": True}
        mock_scene.return_value = {"scene_id": "scene-fallback-fake", "nome_cena": "Cena Fallback Fake"}
        mock_exec.return_value = True

        payload = {
            "mensagem": "sala quente",
            "id_grupo": revenda_teste,
            "nome_revenda": "Revenda Teste Fallback",
        }
        response = client.post("/agent", json=payload, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["intencao"] == "ligar_temperatura_media"
    assert body["ifttt_action"] == "medio"
    assert "instabilidade técnica" not in (body["mensagem_wpp"] or "").lower()


@pytest.mark.integration
def test_mensagem_generica_ainda_aparece_quando_gemini_e_fallback_falham(client, auth_headers, revenda_teste, monkeypatch):
    """
    Se o Gemini falha E o fallback de palavras-chave não reconhece nada na
    mensagem, o comportamento de hoje (mensagem de instabilidade técnica) deve
    ser preservado — não pode virar uma resposta genérica de saudação sem avisar
    que algo deu errado.
    """
    monkeypatch.setattr(main_mod.settings, "gemini_api_key", "fake-key-para-teste")
    monkeypatch.setattr(llm_service, "_client", _mock_client_falho("Gemini indisponível (simulado)"))

    with patch("app.services.llm_service.rag_service.get_relevant_context", new_callable=AsyncMock, return_value=""):
        payload = {
            "mensagem": "blablabla sem sentido nenhum aqui",
            "id_grupo": revenda_teste,
            "nome_revenda": "Revenda Teste Fallback",
        }
        response = client.post("/agent", json=payload, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["ifttt_action"] is None
    assert "instabilidade técnica" in (body["mensagem_wpp"] or "").lower()
