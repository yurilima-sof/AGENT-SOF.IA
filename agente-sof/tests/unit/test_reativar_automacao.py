import asyncio
from unittest.mock import patch, AsyncMock

import pytest

import app.services.llm_service as llm_mod
from app.services.llm_service import llm_service
from app.services.tuya_dispatch_service import disparar_acao_fisica


@pytest.mark.parametrize("mensagem", [
    "reunião cancelada",
    "a reunião já acabou",
    "acabou a reunião",
    "pode tirar a pausa",
    "reativa as automações",
    "religa a automação",
])
async def test_deteccao_cancelamento_pausa(mensagem):
    resultado = await llm_service.processar_mensagem(mensagem, id_grupo="teste-grupo")
    assert resultado["intencao"] == "reativar_automacao_agora"
    assert resultado["ifttt_action"] == "reativar_automacao"
    assert resultado["salvar_memoria"] is False


async def test_deteccao_nao_confunde_pausa_normal_com_cancelamento():
    """Uma mensagem de pausa normal (sem sinal de cancelamento) continua pausando, não reativando."""
    resultado = await llm_service.processar_mensagem("vamos ter reunião até as 20h", id_grupo="teste-grupo")
    assert resultado["intencao"] == "pausar_automacao"
    assert resultado["ifttt_action"] == "desativar_automacao"


async def test_disparar_acao_fisica_reativar_automacao_reativa_apenas_desabilitadas():
    automacoes_falsas = [
        {"id": "auto-1", "name": "Ligas às 8h", "enabled": False},
        {"id": "auto-2", "name": "Ja ligada", "enabled": True},
        {"id": "auto-3", "name": "OFF 17h", "enabled": False},
    ]
    with patch("app.services.scheduler_service.scheduler_service.cancelar_reativacao_pendente", new_callable=AsyncMock) as mock_cancelar, \
         patch("app.services.tuya_service.tuya_service.get_automations_by_home", new_callable=AsyncMock) as mock_get_autom, \
         patch("app.services.tuya_service.tuya_service.set_automation_status", new_callable=AsyncMock) as mock_set_status:
        mock_get_autom.return_value = automacoes_falsas

        resultado = await disparar_acao_fisica(
            db=None,
            id_grupo="teste-grupo",
            nome_revenda="Teste",
            home_id="home-123",
            acao="reativar_automacao",
        )

    mock_cancelar.assert_awaited_once_with("teste-grupo", "home-123")
    assert mock_set_status.await_count == 2  # só as duas desabilitadas
    mock_set_status.assert_any_await("home-123", "auto-1", enable=True)
    mock_set_status.assert_any_await("home-123", "auto-3", enable=True)
    assert resultado["tuya_success"] is True
    assert resultado["device_offline"] is False
    assert "2 automação" in resultado["detail"]


async def test_disparar_acao_fisica_reativar_automacao_nao_checa_dispositivo_offline():
    """Reativar automação é operação na nuvem — não deve depender do status do transmissor IR."""
    with patch("app.services.scheduler_service.scheduler_service.cancelar_reativacao_pendente", new_callable=AsyncMock), \
         patch("app.services.tuya_service.tuya_service.get_automations_by_home", new_callable=AsyncMock, return_value=[]), \
         patch("app.services.tuya_service.tuya_service.check_home_devices_online", new_callable=AsyncMock) as mock_check:
        resultado = await disparar_acao_fisica(
            db=None, id_grupo="g", nome_revenda="Teste", home_id="home-123", acao="reativar_automacao",
        )

    mock_check.assert_not_called()
    assert resultado["device_offline"] is False


async def test_gemini_timeout_cai_no_fallback_rapido(monkeypatch):
    """Se o Gemini demorar mais que o timeout configurado, o fallback de segurança responde rápido."""
    monkeypatch.setattr(llm_mod, "GEMINI_TIMEOUT_SEGUNDOS", 0.05)

    class ModeloLento:
        async def generate_content_async(self, *args, **kwargs):
            await asyncio.sleep(2)
            raise AssertionError("não deveria chegar aqui — o timeout deveria ter cortado antes")

    with patch("app.services.llm_service.rag_service.get_relevant_context", new_callable=AsyncMock, return_value=""), \
         patch("app.services.llm_service.genai.GenerativeModel", side_effect=lambda *a, **kw: ModeloLento()):
        resultado = await asyncio.wait_for(
            llm_service.processar_mensagem("tá muito quente aqui na loja", id_grupo="teste-grupo"),
            timeout=5.0,  # teto de segurança do próprio teste
        )

    # intencao=None (não "sem_acao") de propósito: permite que o fallback de
    # palavras-chave em app/main.py assuma quando o Gemini falha de verdade
    # (ver tests/test_gemini_fallback.py para a cobertura desse comportamento).
    assert resultado["intencao"] is None
    assert "instabilidade técnica" in resultado["mensagem_wpp"]
