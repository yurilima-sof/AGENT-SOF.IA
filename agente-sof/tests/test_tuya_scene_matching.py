import pytest
from sqlalchemy import text

from app.crud.tuya import get_scene_by_ambiente

HOME_FAKE = "TESTE-scene-matching-home"
SCENE_DESLIGAR = "TESTE-scene-desligar-001"
SCENE_LIGAR = "TESTE-scene-ligar-001"


@pytest.fixture
async def cenas_teste(db_session):
    await db_session.execute(text("""
        INSERT INTO tuya_clientes_cenas (sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao)
        VALUES ('teste', :home_id, '', :scene_id, 'Automação sala desligar acima de 15C', 'off')
        ON CONFLICT (scene_id) DO UPDATE SET nome_cena = EXCLUDED.nome_cena, acao = EXCLUDED.acao
    """), {"home_id": HOME_FAKE, "scene_id": SCENE_DESLIGAR})
    await db_session.commit()
    yield
    await db_session.execute(
        text("DELETE FROM tuya_clientes_cenas WHERE scene_id IN (:s1, :s2)"),
        {"s1": SCENE_DESLIGAR, "s2": SCENE_LIGAR},
    )
    await db_session.commit()


@pytest.mark.integration
async def test_ligar_nao_encontra_mais_cena_de_desligar(db_session, cenas_teste):
    """Regressão do bug real de produção: '%ligar%' batia dentro de 'desligar'."""
    resultado = await get_scene_by_ambiente(db_session, HOME_FAKE, "", "ligar")
    assert resultado is None or resultado["scene_id"] != SCENE_DESLIGAR


@pytest.mark.integration
async def test_medio_nao_encontra_mais_cena_de_desligar(db_session, cenas_teste):
    """'medio' tem 'ligar' na lista de sinônimos — mesma colisão observada em produção."""
    resultado = await get_scene_by_ambiente(db_session, HOME_FAKE, "", "medio")
    assert resultado is None or resultado["scene_id"] != SCENE_DESLIGAR


@pytest.mark.integration
async def test_off_continua_encontrando_a_cena_de_desligar(db_session, cenas_teste):
    """A correspondência legítima (off -> cena de desligar) não pode quebrar."""
    resultado = await get_scene_by_ambiente(db_session, HOME_FAKE, "", "off")
    assert resultado is not None
    assert resultado["scene_id"] == SCENE_DESLIGAR


@pytest.mark.integration
async def test_ligar_encontra_a_cena_correta_quando_existe(db_session, cenas_teste):
    """Com uma cena de verdade cadastrada para 'ligar', ela deve ser a encontrada — não a de desligar."""
    await db_session.execute(text("""
        INSERT INTO tuya_clientes_cenas (sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao)
        VALUES ('teste', :home_id, '', :scene_id, 'Cena Ligar Showroom', 'ligar')
        ON CONFLICT (scene_id) DO UPDATE SET nome_cena = EXCLUDED.nome_cena, acao = EXCLUDED.acao
    """), {"home_id": HOME_FAKE, "scene_id": SCENE_LIGAR})
    await db_session.commit()

    resultado = await get_scene_by_ambiente(db_session, HOME_FAKE, "", "ligar")
    assert resultado is not None
    assert resultado["scene_id"] == SCENE_LIGAR
