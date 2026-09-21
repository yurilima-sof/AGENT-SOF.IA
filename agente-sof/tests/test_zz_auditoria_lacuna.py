"""C5 — Guard de escopo temporal independente da intenção classificada.

Nasceu como teste de auditoria que falhava de propósito (a lacuna do Bug 2) e
agora é a prova do fix: uma data futura na mensagem suprime a ação física
imediata seja qual for a intenção que o Gemini atribuiu.

Os mocks de home_id / cena / hub online existem para que os testes NÃO passem
vacuamente: sem o guard, este cenário chega em execute_scene de verdade
(foi exatamente assim que a lacuna foi provada na auditoria).
"""
import pytest
from unittest.mock import patch, AsyncMock

CENA_FAKE = {"scene_id": "SCENE_FAKE", "nome_cena": "Cena Teste"}


@pytest.fixture
def revenda_teste():
    return "TESTE-API-REV"


@pytest.fixture
def gemini_ativo(monkeypatch):
    """Sem gemini_api_key o bloco do LLM nem roda e os testes passariam à toa."""
    from app.main import settings as main_settings
    monkeypatch.setattr(main_settings, "gemini_api_key", "fake-key")


@pytest.mark.integration
async def test_evento_futuro_classificado_como_desligar_nao_dispara(
    client, auth_headers, revenda_teste, gemini_ativo
):
    """A LACUNA: mesmo se o Gemini classificar a frase do incidente como
    desligar_dispositivos (não pausar_automacao), escopo futuro NÃO pode
    chamar disparar_acao_fisica hoje."""
    fake_llm = {
        "intencao": "desligar_dispositivos",   # <- o Gemini ERRA a intenção
        "escopo_temporal": "futuro", "data_evento": "2026-09-19", "hora_fim": "19:00",
        "ifttt_action": "off", "ambiente": None, "mensagem_wpp": "ok", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.llm_service.processar_mensagem",
               new_callable=AsyncMock, return_value=fake_llm), \
         patch("app.main.resolver_home_id_por_grupo", new_callable=AsyncMock, return_value="HOME123"), \
         patch("app.services.tuya_dispatch_service.get_scene_by_ambiente",
               new_callable=AsyncMock, return_value=CENA_FAKE), \
         patch("app.services.tuya_service.tuya_service.get_automations_by_home",
               new_callable=AsyncMock, return_value=[{"id": "a1", "name": "OFF [18:00]"}]), \
         patch("app.services.tuya_service.tuya_service.check_home_devices_online",
               new_callable=AsyncMock, return_value={"all_offline": False}), \
         patch("app.services.tuya_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set, \
         patch("app.services.tuya_service.tuya_service.execute_scene",
               new_callable=AsyncMock) as mock_scene:
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "Evento no sábado dia 19/09, pode estender o horário para desligar as 19:00",
            "id_grupo": revenda_teste, "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200
        mock_set.assert_not_called()
        mock_scene.assert_not_called()


@pytest.mark.integration
async def test_resfriar_hoje_continua_funcionando(
    client, auth_headers, revenda_teste, gemini_ativo
):
    """Regressão: o guard não pode bloquear ação imediata legítima ('tá quente' = hoje).

    'tá muito quente' não tem data na frase, então o parser devolve INDEFINIDO.
    Como a intenção NÃO é de pausa, indefinido deve deixar a ação passar — senão
    matamos o fluxo principal da Sofia.
    """
    fake_llm = {
        "intencao": "ligar_temperatura_media",
        "escopo_temporal": "indefinido",   # <- sem data na mensagem
        "data_evento": None, "hora_fim": None,
        "ifttt_action": "medio", "ambiente": None,
        "mensagem_wpp": "Liguei a climatização!", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.llm_service.processar_mensagem",
               new_callable=AsyncMock, return_value=fake_llm), \
         patch("app.main.resolver_home_id_por_grupo", new_callable=AsyncMock, return_value="HOME123"), \
         patch("app.services.tuya_dispatch_service.get_scene_by_ambiente",
               new_callable=AsyncMock, return_value=CENA_FAKE), \
         patch("app.services.tuya_service.tuya_service.check_home_devices_online",
               new_callable=AsyncMock, return_value={"all_offline": False}), \
         patch("app.services.tuya_service.tuya_service.execute_scene",
               new_callable=AsyncMock, return_value=True) as mock_scene:
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "tá muito quente aqui na loja",
            "id_grupo": revenda_teste, "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200
        mock_scene.assert_called_once()   # a cena de climatização AINDA dispara


@pytest.mark.integration
async def test_resfriar_com_data_futura_nao_dispara(
    client, auth_headers, revenda_teste, gemini_ativo
):
    """Corolário: a supressão vale para QUALQUER intenção, não só desligar.
    'sábado dia 19/09 deixa gelado' é pedido futuro — não pode gelar agora."""
    fake_llm = {
        "intencao": "ligar_resfriamento",
        "escopo_temporal": "futuro", "data_evento": "2026-09-19", "hora_fim": "19:00",
        "ifttt_action": "freezer", "ambiente": None,
        "mensagem_wpp": "ok", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.llm_service.processar_mensagem",
               new_callable=AsyncMock, return_value=fake_llm), \
         patch("app.main.resolver_home_id_por_grupo", new_callable=AsyncMock, return_value="HOME123"), \
         patch("app.services.tuya_dispatch_service.get_scene_by_ambiente",
               new_callable=AsyncMock, return_value=CENA_FAKE), \
         patch("app.services.tuya_service.tuya_service.check_home_devices_online",
               new_callable=AsyncMock, return_value={"all_offline": False}), \
         patch("app.services.tuya_service.tuya_service.execute_scene",
               new_callable=AsyncMock) as mock_scene:
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "No sábado dia 19/09 deixa a loja bem gelada até as 19:00",
            "id_grupo": revenda_teste, "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200
        mock_scene.assert_not_called()


# ---------------------------------------------------------------------------
# C5 Parte A: o escopo é calculado SEMPRE, não só para pausar_automacao.
# Os testes acima mockam processar_mensagem inteiro, então não exercitam o
# llm_service. Estes chamam o serviço de verdade, mockando só a ida ao Gemini.
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_parser_roda_para_intencao_nao_pausa(agora_fixo):
    """Gemini devolve desligar_dispositivos sem escopo nenhum; o parser tem que
    preencher escopo_temporal='futuro' a partir da data na mensagem."""
    from app.services.llm_service import llm_service
    resposta_gemini = {
        "intencao": "desligar_dispositivos", "ifttt_action": "off",
        "ambiente": None, "mensagem_wpp": "ok", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.LLMService._chamar_gemini",
               new_callable=AsyncMock, return_value=resposta_gemini), \
         patch("app.services.rag_service.rag_service.get_relevant_context",
               new_callable=AsyncMock, return_value=""):
        r = await llm_service.processar_mensagem(
            "Evento no sábado dia 19/09, pode estender o horário para desligar as 19:00",
            "TESTE-API-REV", [], None, agora=agora_fixo)
    assert r["escopo_temporal"] == "futuro", r
    assert r["data_evento"] == "2026-09-19", r


@pytest.mark.integration
async def test_comando_imediato_sem_data_fica_indefinido(agora_fixo):
    """Sem data na frase o escopo é indefinido — e indefinido NÃO pode zerar
    ação de intenção imediata (é o caminho do 'tá muito quente')."""
    from app.services.llm_service import llm_service
    resposta_gemini = {
        "intencao": "ligar_temperatura_media", "ifttt_action": "medio",
        "ambiente": None, "mensagem_wpp": "ok", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.LLMService._chamar_gemini",
               new_callable=AsyncMock, return_value=resposta_gemini), \
         patch("app.services.rag_service.rag_service.get_relevant_context",
               new_callable=AsyncMock, return_value=""):
        r = await llm_service.processar_mensagem(
            "tá muito quente aqui na loja", "TESTE-API-REV", [], None, agora=agora_fixo)
    assert r["escopo_temporal"] == "indefinido", r
    assert r["ifttt_action"] == "medio", r  # ação preservada


@pytest.mark.integration
async def test_pausa_sem_escopo_nao_desativa_no_degradado(
    client, auth_headers, revenda_teste, gemini_ativo
):
    """DECISÃO SUBSTITUÍDA em 21/09/2026 (antes: C5 mandava desativar no degradado).

    Regra anterior (test_pausa_sem_escopo_nao_e_bloqueada): pausa sem escopo_temporal
    (None) NÃO podia ser bloqueada, sob o argumento de que bloquear faria a automação
    desligar a loja no horário.

    Nova regra: pausa sem escopo/horário NO DEGRADADO NÃO desativa automação.
    Trade-off aceito conscientemente pelo responsável: é preferível a loja desligar no
    horário normal durante uma reunião (visível na hora, recuperável com um comando)
    do que ficar ligada a noite toda sem controle — que foi o incidente real de
    21/09, quando o resume nunca chegou a ser agendado. O comportamento antigo
    (desativar às cegas) produzia justamente o pior caso sempre que o horário não
    era extraído, que é exatamente o caso que este teste cobre.

    A mensagem de entrada é a ORIGINAL do teste antigo, de propósito: a mudança é de
    comportamento e está documentada aqui, não maquiada acrescentando 'até as 20h'.
    """
    fake_llm = {
        "intencao": "pausar_automacao",
        "escopo_temporal": None,          # <- sem informação temporal
        "data_evento": None, "hora_fim": None,
        "ifttt_action": "desativar_automacao", "ambiente": None,
        "mensagem_wpp": "ok", "salvar_memoria": False,
    }
    with patch("app.services.llm_service.llm_service.processar_mensagem",
               new_callable=AsyncMock, return_value=fake_llm), \
         patch("app.main.resolver_home_id_por_grupo", new_callable=AsyncMock, return_value="HOME123"), \
         patch("app.services.tuya_service.tuya_service.get_automations_by_home",
               new_callable=AsyncMock,
               return_value=[{"id": "a1", "name": "OFF [18:00]", "enabled": True}]), \
         patch("app.services.tuya_service.tuya_service.check_home_devices_online",
               new_callable=AsyncMock, return_value={"all_offline": False}), \
         patch("app.services.scheduler_service.scheduler_service.agendar_reativacao_automacao",
               new_callable=AsyncMock), \
         patch("app.services.tuya_service.tuya_service.set_automation_status",
               new_callable=AsyncMock) as mock_set:
        r = client.post("/agent", headers=auth_headers, json={
            "mensagem": "reunião agora, não desliga as máquinas",
            "id_grupo": revenda_teste, "nome_revenda": "Revenda Teste Admin"})
        assert r.status_code == 200
        assert not mock_set.called, (
            "pausa sem horario NAO deve desativar no degradado (decisao nova de 21/09/2026)")
        assert r.json()["mensagem_wpp"] is not None  # pede horario / avisa
