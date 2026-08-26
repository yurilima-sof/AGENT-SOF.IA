import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

def _to_dict(row):
    if row is None:
        return None
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    if isinstance(row, dict):
        return row
    return dict(row)

async def get_home_by_nome(db: AsyncSession, nome_revenda: str) -> dict:
    """
    Busca a Home (residência) da Tuya baseando-se no nome da revenda recebido pelo WhatsApp/n8n.
    Suporta busca exata, busca por código numérico de revenda (ex: 0019), ILIKE e palavras-chave.

    ATENÇÃO (achado L7): busca fuzzy por texto livre — duas revendas com nomes parecidos
    podem colidir na mesma home. NÃO usar no caminho de comando (produção); mantido só
    como utilitário administrativo/diagnóstico (ex.: script de backfill de tuya_home_id).
    A resolução em produção é `app.crud.revendas.resolver_home_id_por_grupo`, que usa
    exclusivamente `id_grupo_wpp`.
    """
    if not nome_revenda:
        return None

    # 1. Tenta correspondência exata insensível a maiúsculas/minúsculas
    query = text("SELECT * FROM tuya_clientes_homes WHERE nome_home ILIKE :nome LIMIT 1")
    result = await db.execute(query, {"nome": nome_revenda})
    row = result.fetchone()
    if row:
        return _to_dict(row)

    # 2. Tenta extrair dígitos de código de revenda (ex: 'Revenda 0019' -> '0019' ou '019')
    import re
    numeros = re.findall(r'\d+', nome_revenda)
    if numeros:
        for num in numeros:
            num_pattern = f"%{num.zfill(4)}%"
            num_simple = f"%{num}%"
            query_num = text("""
                SELECT h.* FROM tuya_clientes_homes h
                JOIN tuya_clientes_cenas c ON h.home_id = c.home_id
                WHERE h.nome_home ILIKE :num_p OR h.nome_home ILIKE :num_s 
                   OR c.ambiente ILIKE :num_p OR c.nome_cena ILIKE :num_p
                LIMIT 1
            """)
            result_num = await db.execute(query_num, {"num_p": num_pattern, "num_s": num_simple})
            row_num = result_num.fetchone()
            if row_num:
                return _to_dict(row_num)

    # 3. Tenta busca por palavras relevantes (ex: 'Teste sof' -> '%teste%' AND '%sof%')
    palavras = [p.strip() for p in nome_revenda.replace("[", " ").replace("]", " ").replace("/", " ").split() if len(p.strip()) >= 3]
    if palavras:
        condicoes = " AND ".join([f"nome_home ILIKE :p{i}" for i in range(len(palavras))])
        query_flexible = text(f"SELECT * FROM tuya_clientes_homes WHERE {condicoes} LIMIT 1")
        params = {f"p{i}": f"%{palavras[i]}%" for i in range(len(palavras))}
        result = await db.execute(query_flexible, params)
        row = result.fetchone()
        if row:
            return _to_dict(row)

    # 4. Fallback: busca por substring no nome
    query_any = text("SELECT * FROM tuya_clientes_homes WHERE nome_home ILIKE :contains LIMIT 1")
    result = await db.execute(query_any, {"contains": f"%{nome_revenda}%"})
    row = result.fetchone()
    if row:
        return _to_dict(row)

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
        WHERE (h.nome_home ILIKE :nome_revenda OR h.nome_home ILIKE :contains OR c.sigla_cliente ILIKE :nome_revenda)
          AND c.ambiente != '' AND c.ambiente IS NOT NULL
    """)
    result = await db.execute(query, {"nome_revenda": nome_revenda, "contains": f"%{nome_revenda}%"})
    return [row[0] for row in result.fetchall()]

# Mapeamento de sinônimos de ação
ACTION_SYNONYMS: dict[str, list[str]] = {
    "freezer": ["freezer", "esfriar", "t-low", "tlow", "low", "freeze"],
    "esquentar": ["esquentar", "aquecer", "t-high", "thigh", "high", "warm"],
    "medio": ["medio", "médio", "medium", "t-medium", "tmedium", "ligar"],
    "off": ["off", "desligar", "t-off", "toff", "cancelar"],
    "ligar": ["ligar", "on", "t-on", "ton"],
}

# Mapeamento estendido de sinônimos de ambiente (ex: "primeiro_andar" -> 1º andar / [1])
AMBIENTE_SYNONYMS: dict[str, list[str]] = {
    "primeiro_andar": ["%1%", "%[1]%", "%primeiro%", "%p1%", "%andar 1%"],
    "primeiro": ["%1%", "%[1]%", "%primeiro%", "%p1%"],
    "terreo": ["%shnv%", "%terreo%", "%térreo%", "%showroom%", "%piso 0%", "%t%"],
    "térreo": ["%shnv%", "%terreo%", "%térreo%", "%showroom%"],
    "shnv": ["%shnv%", "%terreo%", "%térreo%"],
    "diretoria": ["%diretoria%", "%dir%"],
    "reuniao": ["%reuniao%", "%reunião%"],
}

async def get_scene_by_ambiente(db: AsyncSession, home_id: str, ambiente: str, acao: str) -> dict:
    """
    Busca a Cena (scene_id) da Tuya baseando-se no home_id, ambiente e ação solicitada.
    Suporta mapeamento flexível de sinônimos de ambiente e de ação.
    """
    sinonimos_acao = ACTION_SYNONYMS.get(acao.lower() if acao else "", [acao])
    
    # Prepara padrões flexíveis de ambiente
    amb_patterns = []
    if ambiente:
        amb_clean = ambiente.lower().strip().replace(" ", "_")
        if amb_clean in AMBIENTE_SYNONYMS:
            amb_patterns = AMBIENTE_SYNONYMS[amb_clean]
        elif "primeiro" in amb_clean or "1" in amb_clean:
            amb_patterns = ["%1%", "%[1]%", "%primeiro%"]
        elif "terreo" in amb_clean or "térreo" in amb_clean or "shnv" in amb_clean:
            amb_patterns = ["%shnv%", "%terreo%", "%térreo%"]
        else:
            amb_patterns = [f"%{ambiente}%"]

    # Correspondência de AÇÃO com fronteira de palavra (\y = \b no Postgres), não
    # substring puro: "%ligar%" batia dentro de "desligar" (achado real em produção
    # — "medio" e "ligar" disparavam a mesma cena de desligamento por conterem
    # "ligar" como substring). ~* já é case-insensitive, dispensa LOWER().
    patterns_acao = [fr"\y{s}\y" for s in sinonimos_acao]

    # 1. Tenta buscar combinando ambiente (se fornecido) e ação
    if amb_patterns:
        query = text("""
            SELECT * FROM tuya_clientes_cenas
            WHERE home_id = :home_id
              AND (
                LOWER(ambiente) LIKE ANY(:amb_patterns) OR
                LOWER(nome_cena) LIKE ANY(:amb_patterns)
              )
              AND (
                LOWER(acao) = ANY(:sinonimos_acao) OR
                nome_cena ~* ANY(:patterns_acao) OR
                ambiente ~* ANY(:patterns_acao)
              )
            LIMIT 1
        """)
        result = await db.execute(query, {
            "home_id": home_id,
            "amb_patterns": amb_patterns,
            "sinonimos_acao": sinonimos_acao,
            "patterns_acao": patterns_acao
        })
        row = result.fetchone()
        if row:
            return _to_dict(row)

    # 2. Fallback sem filtro de ambiente (ou se ambiente não foi especificado)
    query_fallback = text("""
        SELECT * FROM tuya_clientes_cenas
        WHERE home_id = :home_id
          AND (
            LOWER(acao) = ANY(:sinonimos_acao) OR
            nome_cena ~* ANY(:patterns_acao) OR
            ambiente ~* ANY(:patterns_acao)
          )
        LIMIT 1
    """)
    result_fb = await db.execute(query_fallback, {
        "home_id": home_id,
        "sinonimos_acao": sinonimos_acao,
        "patterns_acao": patterns_acao
    })
    row_fb = result_fb.fetchone()
    if row_fb:
        return _to_dict(row_fb)

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


# =============================================================================
# CRUD administrativo (painel admin): listagem/edição de homes e cenas
# =============================================================================

async def listar_homes(db: AsyncSession) -> list[dict]:
    """Lista todas as Homes Tuya cadastradas, para popular seletores no painel admin."""
    try:
        result = await db.execute(
            text("""
                SELECT id, sigla_cliente, tuya_uid, home_id, nome_home
                FROM tuya_clientes_homes
                ORDER BY sigla_cliente, nome_home
            """)
        )
        return [dict(row._mapping) for row in result.fetchall()]
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Erro ao listar homes Tuya: {e}", extra={"status": "erro"}, exc_info=True)
        return []


async def listar_cenas_por_home(db: AsyncSession, home_id: str) -> list[dict]:
    """Lista todas as cenas cadastradas para uma Home específica, para edição no painel admin."""
    try:
        result = await db.execute(
            text("""
                SELECT id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao
                FROM tuya_clientes_cenas
                WHERE home_id = :home_id
                ORDER BY ambiente, nome_cena
            """),
            {"home_id": home_id}
        )
        return [dict(row._mapping) for row in result.fetchall()]
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Erro ao listar cenas da home '{home_id}': {e}", extra={"status": "erro"}, exc_info=True)
        return []


async def upsert_cena(db: AsyncSession, sigla_cliente: str, home_id: str, ambiente: str, scene_id: str, nome_cena: str, acao: str) -> dict:
    """
    Cria ou atualiza (por scene_id, que é UNIQUE) o mapeamento de uma cena Tuya.
    Usada pelo formulário de gestão de cenas do painel admin.
    """
    result = await db.execute(
        text("""
            INSERT INTO tuya_clientes_cenas (sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao)
            VALUES (:sigla_cliente, :home_id, :ambiente, :scene_id, :nome_cena, :acao)
            ON CONFLICT (scene_id) DO UPDATE SET
                sigla_cliente = EXCLUDED.sigla_cliente,
                home_id = EXCLUDED.home_id,
                ambiente = EXCLUDED.ambiente,
                nome_cena = EXCLUDED.nome_cena,
                acao = EXCLUDED.acao
            RETURNING id, sigla_cliente, home_id, ambiente, scene_id, nome_cena, acao
        """),
        {
            "sigla_cliente": sigla_cliente,
            "home_id": home_id,
            "ambiente": ambiente,
            "scene_id": scene_id,
            "nome_cena": nome_cena,
            "acao": acao,
        }
    )
    row = result.fetchone()
    await db.commit()
    logger.info(f"✅ Cena {scene_id} ('{nome_cena}') gravada via painel admin (Home: {home_id}).")
    return dict(row._mapping)


async def deletar_cena(db: AsyncSession, scene_id: str) -> bool:
    """Remove uma cena Tuya pelo scene_id. Retorna True se algo foi de fato removido."""
    try:
        result = await db.execute(
            text("DELETE FROM tuya_clientes_cenas WHERE scene_id = :scene_id RETURNING id"),
            {"scene_id": scene_id}
        )
        removido = result.fetchone() is not None
        await db.commit()
        return removido
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Erro ao deletar cena '{scene_id}': {e}", extra={"status": "erro"}, exc_info=True)
        return False
