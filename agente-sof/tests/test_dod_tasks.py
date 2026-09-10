import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.crud.tuya import (
    get_ambientes_by_home_id,
    get_scene_by_ambiente,
    ACTION_SYNONYMS
)
from app.domain.policy.keyword_fallback import classificar_familia, FamiliaIntencao
from app.domain.policy.escalation import determinar_acao_e_intencao
from app.services.tuya_dispatch_service import disparar_acao_fisica


# Helper para criar resultado mockado do SQLAlchemy execute
def create_query_result(rows=None, row=None):
    mock_res = MagicMock()
    if rows is not None:
        mock_res.fetchall.return_value = rows
    if row is not None:
        mock_res.fetchone.return_value = row
    return mock_res


# =============================================================================
# TASK 1: Correção do Isolamento de Ambientes por Tenant (home_id)
# =============================================================================

@pytest.mark.asyncio
async def test_get_ambientes_by_home_id_isolamento():
    """Garante que get_ambientes_by_home_id retorna apenas ambientes da home_id especificada."""
    db_mock = AsyncMock()
    db_mock.execute.return_value = create_query_result(rows=[("Financeiro",), ("Showroom",)])

    ambientes = await get_ambientes_by_home_id(db_mock, "home_loja_123")
    
    assert ambientes == ["Financeiro", "Showroom"]
    assert db_mock.execute.called
    query_text = str(db_mock.execute.call_args[0][0])
    assert "WHERE home_id = :home_id" in query_text

@pytest.mark.asyncio
async def test_get_ambientes_by_home_id_vazio():
    """Garante que home_id vazio retorna lista vazia imediatamente sem consulta."""
    db_mock = AsyncMock()
    ambientes = await get_ambientes_by_home_id(db_mock, "")
    assert ambientes == []
    assert not db_mock.execute.called


# =============================================================================
# TASK 2: Sinônimos da Ação 'ligar' para Mapear Cenas T-MEDIUM
# =============================================================================

def test_action_synonyms_ligar_contem_medio():
    """Garante que ACTION_SYNONYMS['ligar'] contém termos de temperatura média."""
    synonyms_ligar = ACTION_SYNONYMS.get("ligar", [])
    for termo in ["medio", "médio", "medium", "t-medium", "tmedium"]:
        assert termo in synonyms_ligar, f"Termo '{termo}' ausente em ACTION_SYNONYMS['ligar']"

@pytest.mark.asyncio
async def test_get_scene_by_ambiente_ligar_mapeia_tmedium():
    """Garante que buscar a ação 'ligar' para revenda com apenas cena T-MEDIUM retorna o scene_id com sucesso."""
    db_mock = AsyncMock()
    row_data = {
        "id": 1,
        "sigla_cliente": "loja1",
        "home_id": "home_loja_1",
        "ambiente": "",
        "scene_id": "scene_t_medium_123",
        "nome_cena": "T-MEDIUM",
        "acao": "medio"
    }
    db_mock.execute.return_value = create_query_result(row=row_data)

    resultado = await get_scene_by_ambiente(db_mock, "home_loja_1", "", "ligar")
    
    assert resultado is not None
    assert resultado["scene_id"] == "scene_t_medium_123"


# =============================================================================
# TASK 3: Fallback Automático de Ambiente Inexistente para Cena Geral
# =============================================================================

@pytest.mark.asyncio
async def test_fallback_ambiente_inexistente_para_cena_geral():
    """
    Quando get_scene_by_ambiente retorna None para um ambiente específico (ex: '0009'),
    disparar_acao_fisica deve tentar amb = "" e acionar a cena geral T-MEDIUM.
    """
    db_mock = AsyncMock()
    
    with patch("app.services.tuya_dispatch_service.tuya_service") as tuya_service_mock, \
         patch("app.services.tuya_dispatch_service.get_scene_by_ambiente", new_callable=AsyncMock) as get_scene_mock:
        
        tuya_service_mock.check_home_devices_online = AsyncMock(return_value={"all_offline": False})
        tuya_service_mock.execute_scene = AsyncMock(return_value=True)

        cena_geral = {
            "scene_id": "scene_geral_medium",
            "nome_cena": "T-MEDIUM Geral",
            "ambiente": "",
            "acao": "medio"
        }
        get_scene_mock.side_effect = [None, cena_geral]

        resultado = await disparar_acao_fisica(
            db=db_mock,
            id_grupo="grupo123@g.us",
            nome_revenda="Loja Teste",
            home_id="home_teste_123",
            acao="ligar",
            ambiente="0009"
        )

        assert get_scene_mock.call_count == 2
        assert get_scene_mock.call_args_list[0][0][2] == "0009"
        assert get_scene_mock.call_args_list[1][0][2] == ""

        assert resultado["tuya_success"] is True
        assert resultado["detail"] == "T-MEDIUM Geral"


# =============================================================================
# TASK 4: Ajuste Semântico de Prompt e Fallback: Frases Passivas de Reclamação
# =============================================================================

@pytest.mark.parametrize("mensagem", [
    "Máquinas desligadas",
    "Ar condicionados da loja desligados",
    "Máquinas continuam desligadas",
    "Ar condicionado está desligado",
    "Tudo desligado",
])
def test_frases_passivas_desligadas_classificam_como_ligar(mensagem):
    """Mensagens indicando equipamentos desligados no particípio DEVEM ser classificadas como LIGAR."""
    familia = classificar_familia(mensagem)
    assert familia == FamiliaIntencao.LIGAR
    
    acao, intencao, _ = determinar_acao_e_intencao(familia)
    assert acao in ("ligar", "medio")
    assert intencao == "ligar_dispositivos"

def test_frase_loja_quente_classifica_como_resfriamento():
    """Mensagem 'Loja quente' DEVE ser classificada como resfriamento/médio."""
    familia = classificar_familia("Loja quente")
    assert familia == FamiliaIntencao.RESFRIAMENTO

    acao, intencao, _ = determinar_acao_e_intencao(familia, chamados_recentes=0)
    assert acao == "medio"
    assert intencao == "ligar_temperatura_media"

def test_frase_imperativa_desligar_continua_desligando():
    """Garante que frases imperativas explícitas ('desligar', 'desliga') continuam classificadas como DESLIGAR."""
    familia = classificar_familia("Favor desligar o ar da sala")
    assert familia == FamiliaIntencao.DESLIGAR

    acao, intencao, _ = determinar_acao_e_intencao(familia)
    assert acao == "off"
    assert intencao == "desligar_dispositivos"
