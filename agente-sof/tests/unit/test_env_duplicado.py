# =============================================================================
# tests/unit/test_env_duplicado.py
# =============================================================================
# `chaves_duplicadas_em_env` DERRUBA O BOOT quando acha duplicata. Isso inverte
# o peso dos erros: um falso negativo deixa passar credencial errada (ruim), mas
# um falso POSITIVO impede a aplicacao de subir (pior, e na hora do deploy).
#
# Por isso a maior parte destes testes cobre o que NAO pode ser confundido com
# duplicata: comentarios, valores multilinha, chaves parecidas, `export`, linhas
# malformadas.
# =============================================================================

import pytest

from app.config import chaves_duplicadas_em_env


@pytest.fixture
def env_file(tmp_path):
    """Escreve um .env temporario e devolve o caminho."""
    def _escrever(conteudo: str, nome: str = ".env"):
        caminho = tmp_path / nome
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho
    return _escrever


# =============================================================================
# Deteccao — o caso que originou a checagem
# =============================================================================

def test_detecta_o_incidente_real(env_file):
    """Reproduz a forma exata do bug: um bloco '#test' colado no fim do .env de
    producao, redefinindo as chaves que ja existiam acima."""
    caminho = env_file(
        "APP_ENV=production\n"
        "API_KEY=chave-real-de-producao\n"
        "GEMINI_API_KEY=AQ.realmente-uma-chave\n"
        "\n"
        "#test\n"
        'APP_ENV="development"\n'
        'API_KEY="dev-api-key-insegura"\n'
        'GEMINI_API_KEY=""\n'
    )
    duplicadas = chaves_duplicadas_em_env(caminho)

    assert set(duplicadas) == {"APP_ENV", "API_KEY", "GEMINI_API_KEY"}
    assert duplicadas["APP_ENV"] == [1, 6]
    assert duplicadas["API_KEY"] == [2, 7]


def test_reporta_todas_as_linhas_de_uma_chave_repetida_3x(env_file):
    caminho = env_file("A=1\nA=2\nA=3\n")
    assert chaves_duplicadas_em_env(caminho) == {"A": [1, 2, 3]}


def test_deteccao_e_case_insensitive(env_file):
    """O Pydantic Settings e case-insensitive: API_KEY e api_key sao a MESMA
    variavel e colidem. Tratar como chaves distintas deixaria o bug passar."""
    caminho = env_file("API_KEY=um\napi_key=dois\n")
    assert chaves_duplicadas_em_env(caminho) == {"API_KEY": [1, 2]}


def test_detecta_duplicata_com_export(env_file):
    caminho = env_file("export API_KEY=um\nAPI_KEY=dois\n")
    assert chaves_duplicadas_em_env(caminho) == {"API_KEY": [1, 2]}


def test_detecta_duplicata_com_espaco_antes_do_igual(env_file):
    caminho = env_file("API_KEY = um\nAPI_KEY=dois\n")
    assert chaves_duplicadas_em_env(caminho) == {"API_KEY": [1, 2]}


# =============================================================================
# Falso positivo — o erro caro, porque impede o boot
# =============================================================================

def test_env_limpo_nao_acusa_nada(env_file):
    caminho = env_file(
        "# Comentario\n"
        "APP_ENV=production\n"
        "API_KEY=abc\n"
        "\n"
        "SECRET_KEY=def\n"
    )
    assert chaves_duplicadas_em_env(caminho) == {}


def test_chave_repetida_apenas_em_comentario_nao_conta(env_file):
    """Exemplo comentado e documentacao, nao definicao."""
    caminho = env_file(
        "API_KEY=real\n"
        "# API_KEY=exemplo-antigo\n"
        "#API_KEY=outro-exemplo\n"
        "   # API_KEY=indentado\n"
    )
    assert chaves_duplicadas_em_env(caminho) == {}


def test_valor_multilinha_nao_vira_definicao_de_chave(env_file):
    """Chave privada em PEM dentro de aspas: as linhas internas nao sao
    definicoes. Sem a maquina de estado de aspas, 'KEY=' apareceria duas vezes
    e o boot cairia por engano."""
    caminho = env_file(
        'CERT="-----BEGIN KEY-----\n'
        "linha1\n"
        "CERT=isto-esta-dentro-do-valor\n"
        '-----END KEY-----"\n'
        "API_KEY=real\n"
    )
    assert chaves_duplicadas_em_env(caminho) == {}


def test_valor_multilinha_com_aspas_simples(env_file):
    caminho = env_file(
        "PROMPT='linha um\n"
        "PROMPT=dentro do valor\n"
        "fim'\n"
        "API_KEY=real\n"
    )
    assert chaves_duplicadas_em_env(caminho) == {}


def test_aspas_fechadas_na_mesma_linha_nao_abrem_bloco(env_file):
    """Regressao: se o parser achasse que "um" deixa aspas abertas, ele engoliria
    as linhas seguintes e PERDERIA a duplicata real abaixo."""
    caminho = env_file('A="um"\nB="dois"\nA="tres"\n')
    assert chaves_duplicadas_em_env(caminho) == {"A": [1, 3]}


def test_chaves_com_prefixo_comum_sao_distintas(env_file):
    """API_KEY, API_KEY_OLD e ADMIN_API_KEY sao tres variaveis diferentes."""
    caminho = env_file("API_KEY=1\nAPI_KEY_OLD=2\nADMIN_API_KEY=3\n")
    assert chaves_duplicadas_em_env(caminho) == {}


def test_valor_contendo_igual_nao_confunde(env_file):
    """URL de banco e DSN tem '=' no meio do valor."""
    caminho = env_file(
        "DATABASE_URL=postgresql://u:p@h/db?sslmode=require&a=b\n"
        "SENTRY_DSN=https://x@y.ingest.sentry.io/1?z=1\n"
    )
    assert chaves_duplicadas_em_env(caminho) == {}


def test_linhas_malformadas_sao_ignoradas(env_file):
    """Lixo no arquivo nao pode virar 'chave duplicada'."""
    caminho = env_file(
        "isto nao tem igual\n"
        "=valor-sem-chave\n"
        "9INVALIDA=x\n"
        "   \n"
        "API_KEY=real\n"
    )
    assert chaves_duplicadas_em_env(caminho) == {}


# =============================================================================
# Robustez de E/S — nao pode explodir no boot por causa do arquivo
# =============================================================================

def test_arquivo_inexistente_devolve_vazio():
    """Os tres caminhos de ENV_FILES sao testados sempre; dois normalmente nao
    existem. Isso nao pode levantar excecao."""
    assert chaves_duplicadas_em_env("nao/existe/.env") == {}


def test_diretorio_no_lugar_do_arquivo_devolve_vazio(tmp_path):
    assert chaves_duplicadas_em_env(tmp_path) == {}


def test_arquivo_vazio_devolve_vazio(env_file):
    assert chaves_duplicadas_em_env(env_file("")) == {}


def test_arquivo_binario_nao_derruba_o_boot(tmp_path, caplog):
    """UnicodeDecodeError vira warning, nao excecao: o Pydantic reclama depois
    se o arquivo for mesmo inutilizavel."""
    caminho = tmp_path / ".env"
    caminho.write_bytes(b"\xff\xfe\x00\x00binario")
    with caplog.at_level("WARNING"):
        assert chaves_duplicadas_em_env(caminho) == {}


def test_aceita_str_e_path(env_file):
    caminho = env_file("A=1\nA=2\n")
    assert chaves_duplicadas_em_env(str(caminho)) == {"A": [1, 2]}
    assert chaves_duplicadas_em_env(caminho) == {"A": [1, 2]}
