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
        INSERT INTO mapa_revendas (id_grupo_wpp, nome_revenda, estado, tuya_home_id, credenciais_tuya, ativo)
        VALUES (:id_grupo, 'Revenda Teste Fallback', 'PE', '999997', '{}', true)
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


# =============================================================================
# D1 - Degradado: preserva acao imediata, bloqueia so pausa sem horario
# =============================================================================

@pytest.mark.integration
def test_degradado_resfriar_continua_funcionando(client, auth_headers, revenda_teste, monkeypatch):
    """DECISAO 1: Gemini caiu + 'sala quente' => fallback resfria (NAO bloquear).

    Guarda de regressao explicita: garante que a salvaguarda C2 (pausa sem horario)
    nunca foi ampliada a ponto de invadir acao imediata reversivel. Se este teste
    ficar vermelho, o guard passou a bloquear resfriar/ligar — o que e errado.
    """
    monkeypatch.setattr(main_mod.settings, "gemini_api_key", "fake-key-para-teste")
    monkeypatch.setattr(llm_service, "_client", _mock_client_falho("Gemini indisponível (simulado)"))

    with patch("app.services.llm_service.rag_service.get_relevant_context", new_callable=AsyncMock, return_value=""), \
         patch("app.services.tuya_dispatch_service.tuya_service.check_home_devices_online", new_callable=AsyncMock) as mock_check, \
         patch("app.services.tuya_dispatch_service.get_scene_by_ambiente", new_callable=AsyncMock) as mock_scene, \
         patch("app.services.tuya_dispatch_service.tuya_service.execute_scene", new_callable=AsyncMock) as mock_exec:
        mock_check.return_value = {"all_offline": False, "checked": True}
        mock_scene.return_value = {"scene_id": "scene-fake", "nome_cena": "Cena Fake"}
        mock_exec.return_value = True

        response = client.post("/agent", json={
            "mensagem": "sala quente",
            "id_grupo": revenda_teste,
            "nome_revenda": "Revenda Teste Fallback",
        }, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["intencao"] == "ligar_temperatura_media"
    assert mock_exec.called, "acao imediata reversivel deve continuar executando no degradado"


@pytest.mark.integration
def test_degradado_pausa_sem_horario_nao_dispara_nada_fisico(client, auth_headers, revenda_teste, monkeypatch):
    """DECISAO 2: Gemini caiu + 'reuniao, nao desliga' SEM horario => NADA fisico.

    Cobre as DUAS formas de dano possiveis neste caminho, nao so uma:
      - desativar automacao de OFF sem resume (loja ligada a noite toda);
      - executar a cena de OFF por ler a negacao 'nao desliga' como 'desliga'
        (loja desligada no meio da reuniao).
    Assertar apenas set_automation_status deixaria a segunda passar despercebida.

    SOBRE A VERIFICACAO DE MUTACAO (leia antes de confiar neste teste):
    este e um teste de invariante ponta a ponta, nao um teste de um guard
    especifico. O caminho e protegido em profundidade por QUATRO camadas, e
    cada uma sozinha ja basta para segurar:
      1. main.py  guard C5 'indefinido'  (escopo == "indefinido" -> acao = None)
      2. main.py  guard C5 de escopo     (pausar_automacao e escopo != "hoje")
      3. main.py  salvaguarda C2         (horario_fim_pausa is None -> aborta)
      4. tuya_dispatch_service.py C2     (mesma salvaguarda, 2a linha de defesa)
    Matriz verificada em 21/09/2026: desligar qualquer subconjunto proprio das
    quatro mantem o teste VERDE; so desligando as QUATRO ele fica VERMELHO
    (set_automation_status chamado). Ou seja: ele nao e vazio, mas tambem nao
    serve como mutation test de nenhuma camada isolada. Para provar a
    salvaguarda C2 isoladamente, use
    test_api.py::test_pausa_sem_horario_nao_desativa_automacoes, que na rota
    com Gemini OK depende so do C2.

    Nota sobre o classificador de keywords: 'nao desliga as maquinas' isolado
    em classificar_familia() retorna DESLIGAR (a negacao e ignorada). Isso NAO
    vaza para producao porque llm_service.processar_mensagem tem um override
    deterministico (palavras_pausa) que fixa intencao='pausar_automacao' antes,
    e o fallback de keyword so roda quando `not intencao`. Este teste tranca
    essa propriedade: se o override for removido, mock_exec passa a ser
    chamado e o teste fica vermelho.
    """
    monkeypatch.setattr(main_mod.settings, "gemini_api_key", "fake-key-para-teste")
    monkeypatch.setattr(llm_service, "_client", _mock_client_falho("Gemini indisponível (simulado)"))

    with patch("app.services.llm_service.rag_service.get_relevant_context", new_callable=AsyncMock, return_value=""), \
         patch("app.services.tuya_dispatch_service.tuya_service.check_home_devices_online", new_callable=AsyncMock) as mock_check, \
         patch("app.services.tuya_dispatch_service.get_scene_by_ambiente", new_callable=AsyncMock) as mock_scene, \
         patch("app.services.tuya_dispatch_service.tuya_service.execute_scene", new_callable=AsyncMock) as mock_exec, \
         patch("app.services.tuya_service.tuya_service.get_automations_by_home", new_callable=AsyncMock,
               return_value=[{"id": "a1", "name": "OFF [18:00]", "enabled": True}]), \
         patch("app.services.tuya_service.tuya_service.set_automation_status", new_callable=AsyncMock) as mock_set:
        mock_check.return_value = {"all_offline": False, "checked": True}
        mock_scene.return_value = {"scene_id": "scene-off-fake", "nome_cena": "Cena OFF Fake"}
        mock_exec.return_value = True

        response = client.post("/agent", json={
            "mensagem": "reunião agora, não desliga as máquinas",
            "id_grupo": revenda_teste,
            "nome_revenda": "Revenda Teste Fallback",
        }, headers=auth_headers)

    assert response.status_code == 200
    assert not mock_set.called, "pausa sem horario no degradado NAO pode desativar automacao"
    assert not mock_exec.called, "negacao 'nao desliga' NAO pode virar execucao da cena de OFF"
    assert response.json()["mensagem_wpp"] is not None
