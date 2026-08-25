import pytest
from sqlalchemy import text
from unittest.mock import ANY, patch, AsyncMock

ID_GRUPO_TESTE = "TESTE-admin-001"

@pytest.fixture
async def revenda_teste(db_session):
    await db_session.execute(text("""
        INSERT INTO mapa_revendas (id_grupo_wpp, nome_revenda, tuya_home_id, credenciais_tuya, ativo)
        VALUES (:id_grupo, 'Revenda Teste Admin', '999999', '{}', true)
        ON CONFLICT (id_grupo_wpp) DO UPDATE SET ativo = true
    """), {"id_grupo": ID_GRUPO_TESTE})
    await db_session.commit()
    yield ID_GRUPO_TESTE
    await db_session.execute(
        text("DELETE FROM mapa_revendas WHERE id_grupo_wpp = :id_grupo"),
        {"id_grupo": ID_GRUPO_TESTE}
    )
    await db_session.commit()

# --- T1 ---
@pytest.mark.integration
def test_listar_revendas_sem_autenticacao_rejeitado(client):
    response = client.get("/admin/revendas")
    assert response.status_code in (401, 403)

@pytest.mark.integration
def test_listar_revendas_autenticado_retorna_revenda_teste(client, admin_headers, revenda_teste):
    response = client.get("/admin/revendas", headers=admin_headers)
    assert response.status_code == 200
    dados = response.json()
    revenda = next((r for r in dados if r["id_grupo_wpp"] == revenda_teste), None)
    assert revenda is not None
    assert revenda["nome_revenda"] == "Revenda Teste Admin"
    assert revenda["ativo"] is True

# --- T2 ---
@pytest.mark.integration
def test_toggle_sem_autenticacao_rejeitado(client, revenda_teste):
    response = client.post(f"/admin/revendas/{revenda_teste}/toggle", json={"ativo": False})
    assert response.status_code in (401, 403)

@pytest.mark.integration
async def test_toggle_desativa_revenda_no_banco(client, admin_headers, revenda_teste, db_session):
    response = client.post(
        f"/admin/revendas/{revenda_teste}/toggle",
        headers=admin_headers,
        json={"ativo": False},
    )
    assert response.status_code == 200
    assert response.json()["ativo"] is False

    resultado = await db_session.execute(
        text("SELECT ativo FROM mapa_revendas WHERE id_grupo_wpp = :id_grupo"),
        {"id_grupo": revenda_teste},
    )
    assert resultado.scalar() is False

@pytest.mark.integration
def test_toggle_revenda_inexistente_retorna_404(client, admin_headers):
    response = client.post(
        "/admin/revendas/nao-existe-999/toggle",
        headers=admin_headers,
        json={"ativo": False},
    )
    assert response.status_code == 404

# --- T3 ---
@pytest.mark.integration
async def test_revenda_desativada_nao_processa_mensagem(client, auth_headers, revenda_teste, db_session):
    await db_session.execute(
        text("UPDATE mapa_revendas SET ativo = false WHERE id_grupo_wpp = :id_grupo"),
        {"id_grupo": revenda_teste},
    )
    await db_session.commit()

    with patch("app.services.llm_service.llm_service.processar_mensagem", new_callable=AsyncMock) as mock_llm, \
         patch("app.services.tuya_service.tuya_service.execute_scene", new_callable=AsyncMock) as mock_tuya:

        payload = {
            "mensagem": "sala quente",
            "id_grupo": revenda_teste,
            "nome_revenda": "Revenda Teste Admin",
        }
        response = client.post("/agent", json=payload, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["mensagem_wpp"] is None
        mock_llm.assert_not_called()
        mock_tuya.assert_not_called()

@pytest.mark.integration
def test_revenda_ativa_continua_funcionando_normalmente(client, auth_headers, revenda_teste):
    """Guarda de regressão: o corte do T3 não pode vazar pra revenda ativa."""
    payload = {
        "mensagem": "tá muito quente aqui",
        "id_grupo": revenda_teste,
        "nome_revenda": "Revenda Teste Admin",
    }
    response = client.post("/agent", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["mensagem_wpp"] is not None

# --- T4 ---
@pytest.mark.integration
def test_admin_sem_header_retorna_401_ou_403(client):
    response = client.get("/admin/revendas")
    assert response.status_code in (401, 403)

@pytest.mark.integration
def test_admin_rejeita_api_key_do_webhook(client, auth_headers):
    """A ADMIN_API_KEY não pode ser a mesma API_KEY que o n8n usa."""
    response = client.get("/admin/revendas", headers=auth_headers)
    assert response.status_code in (401, 403)

@pytest.mark.integration
def test_admin_aceita_admin_key_correta(client, admin_headers):
    response = client.get("/admin/revendas", headers=admin_headers)
    assert response.status_code == 200

# --- T5 (painel dinâmico: shell HTML público + dados carregados via fetch) ---
# O painel deixou de ser server-rendered (era isso que exigia Admin Key só pra
# ABRIR a página, o problema original). Agora /admin/painel serve só o shell
# estático — sem nenhum dado embutido — e o JavaScript da página é quem busca
# tudo via fetch() contra as rotas JSON abaixo, que continuam 100% protegidas.

@pytest.mark.integration
def test_painel_e_publico_e_carrega_sem_autenticacao(client):
    """
    O shell HTML não expõe dado nenhum por si só, então não precisa mais de
    Admin Key só para abrir a página no navegador digitando a URL.
    """
    response = client.get("/admin/painel")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.integration
def test_painel_nao_embute_dados_de_revendas_no_html(client, revenda_teste):
    """Regressão de arquitetura: dado de revenda não pode mais vir embutido no HTML do servidor."""
    response = client.get("/admin/painel")
    assert "Revenda Teste Admin" not in response.text


@pytest.mark.integration
def test_painel_define_escape_client_side(client):
    """A defesa contra XSS migrou para o cliente, já que os dados não são mais renderizados no servidor."""
    response = client.get("/admin/painel")
    assert "escapeHtml" in response.text


@pytest.mark.integration
async def test_admin_revendas_json_expoe_nome_cru_para_o_cliente_escapar(client, admin_headers, db_session):
    """
    /admin/revendas é JSON puro — não deve fazer HTML-escaping (isso é
    responsabilidade do JS ao inserir no DOM via escapeHtml(), evitando
    double-escaping). Substitui o antigo teste de XSS no HTML server-rendered.
    """
    id_grupo_malicioso = "TESTE-xss-002"
    await db_session.execute(text("""
        INSERT INTO mapa_revendas (id_grupo_wpp, nome_revenda, tuya_home_id, credenciais_tuya, ativo)
        VALUES (:id_grupo, '<script>alert(1)</script>', '999998', '{}', true)
        ON CONFLICT (id_grupo_wpp) DO UPDATE SET nome_revenda = EXCLUDED.nome_revenda
    """), {"id_grupo": id_grupo_malicioso})
    await db_session.commit()

    response = client.get("/admin/revendas", headers=admin_headers)
    dados = response.json()
    revenda = next((r for r in dados if r["id_grupo_wpp"] == id_grupo_malicioso), None)
    assert revenda is not None
    assert revenda["nome_revenda"] == "<script>alert(1)</script>"

    await db_session.execute(
        text("DELETE FROM mapa_revendas WHERE id_grupo_wpp = :id_grupo"),
        {"id_grupo": id_grupo_malicioso},
    )
    await db_session.commit()
