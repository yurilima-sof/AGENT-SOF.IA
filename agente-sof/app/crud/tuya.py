import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

async def get_home_by_nome(db: AsyncSession, nome_revenda: str) -> dict:
    """
    Busca a Home (residência) da Tuya baseando-se no nome da revenda recebido pelo WhatsApp/n8n.
    Exemplo de nome_revenda: '[SOF] Testes' ou '[Recife/PE] Audi BV'
    """
    query = text("SELECT * FROM tuya_clientes_homes WHERE nome_home = :nome_revenda LIMIT 1")
    result = await db.execute(query, {"nome_revenda": nome_revenda})
    row = result.fetchone()
    if row:
        return dict(row._mapping)
    return None

async def get_ambientes_by_cliente(db: AsyncSession, nome_revenda: str) -> list[str]:
    """
    Busca os ambientes distintos cadastrados para uma revenda na tabela de cenas.
    Pode receber o nome completo da revenda (ex: '[SOF] Testes') ou a sigla (ex: 'pe').
    """
    query = text("""
        SELECT DISTINCT c.ambiente 
        FROM tuya_clientes_cenas c
        LEFT JOIN tuya_clientes_homes h ON c.home_id = h.home_id
        WHERE (h.nome_home = :nome_revenda OR c.sigla_cliente = :nome_revenda)
          AND c.ambiente != '' AND c.ambiente IS NOT NULL
    """)
    result = await db.execute(query, {"nome_revenda": nome_revenda})
    return [row[0] for row in result.fetchall()]

# Mapeamento de sinônimos de ação
ACTION_SYNONYMS: dict[str, list[str]] = {
    "freezer": ["freezer", "esfriar", "t-low", "tlow", "low", "freeze"],
    "esquentar": ["esquentar", "aquecer", "t-high", "thigh", "high", "warm"],
    "medio": ["medio", "médio", "medium", "t-medium", "tmedium", "ligar"],
    "off": ["off", "desligar", "t-off", "toff", "cancelar"],
    "ligar": ["ligar", "on", "t-on", "ton"],
}

async def get_scene_by_ambiente(db: AsyncSession, home_id: str, ambiente: str, acao: str) -> dict:
    """
    Busca a Cena (scene_id) da Tuya baseando-se no home_id, ambiente e ação solicitada.
    """
    sinonimos = ACTION_SYNONYMS.get(acao.lower() if acao else "", [acao])
    
    # 1. Tenta buscar por equivalência exata de ação ou sinônimos
    query = text("""
        SELECT * FROM tuya_clientes_cenas 
        WHERE home_id = :home_id
          AND (ambiente ILIKE :ambiente OR :ambiente_vazio = TRUE)
          AND (LOWER(acao) = ANY(:sinonimos))
        LIMIT 1
    """)
    result = await db.execute(query, {
        "home_id": home_id,
        "ambiente": f"%{ambiente}%" if ambiente else "",
        "ambiente_vazio": not bool(ambiente),
        "sinonimos": sinonimos
    })
    row = result.fetchone()
    if row:
        return dict(row._mapping)

    # 2. Fallback: Se não encontrou pela coluna 'acao', busca no 'nome_cena' ou 'ambiente' pelas palavras-chave da ação
    query_fallback = text("""
        SELECT * FROM tuya_clientes_cenas 
        WHERE home_id = :home_id
          AND (ambiente ILIKE :ambiente OR :ambiente_vazio = TRUE)
          AND (
            LOWER(nome_cena) LIKE ANY(:patterns) OR
            LOWER(ambiente) LIKE ANY(:patterns)
          )
        LIMIT 1
    """)
    patterns = [f"%{s}%" for s in sinonimos]
    result_fb = await db.execute(query_fallback, {
        "home_id": home_id,
        "ambiente": f"%{ambiente}%" if ambiente else "",
        "ambiente_vazio": not bool(ambiente),
        "patterns": patterns
    })
    row_fb = result_fb.fetchone()
    if row_fb:
        return dict(row_fb._mapping)

    return None

async def save_tuya_home(db: AsyncSession, sigla_cliente: str, tuya_uid: str, home_id: str, nome_home: str):
    check_query = text("SELECT id FROM tuya_clientes_homes WHERE sigla_cliente = :sigla AND home_id = :home")
    existing = await db.execute(check_query, {"sigla": sigla_cliente, "home": home_id})
    
    if not existing.fetchone():
        query = text("""
            INSERT INTO tuya_clientes_homes (sigla_cliente, tuya_uid, home_id, nome_home)
            VALUES (:sigla_cliente, :tuya_uid, :home_id, :nome_home)
        """)
        await db.execute(query, {
            "sigla_cliente": sigla_cliente,
            "tuya_uid": tuya_uid,
            "home_id": home_id,
            "nome_home": nome_home
        })
        await db.commit()
        logger.info(f"✅ Home {home_id} salvo para cliente '{sigla_cliente}'.")

async def save_tuya_scene(db: AsyncSession, sigla_cliente: str, home_id: str, ambiente: str, scene_id: str, nome_cena: str, acao: str):
    check_query = text("SELECT id FROM tuya_clientes_cenas WHERE scene_id = :scene_id")
    existing = await db.execute(check_query, {"scene_id": scene_id})
    
    if not existing.fetchone():
        query = text("""
            INSERT INTO tuya_clientes_cenas (sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao)
            VALUES (:sigla_cliente, :home_id, :ambiente, :scene_id, :nome_cena, :acao)
        """)
        await db.execute(query, {
            "sigla_cliente": sigla_cliente,
            "home_id": home_id,
            "ambiente": ambiente,
            "scene_id": scene_id,
            "nome_cena": nome_cena,
            "acao": acao
        })
        await db.commit()
        logger.info(f"✅ Cena {scene_id} ('{nome_cena}') salva no ambiente '{ambiente}' (Home: {home_id}) para o cliente '{sigla_cliente}'.")
