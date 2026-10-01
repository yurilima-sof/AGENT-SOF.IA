# tests/unit/test_config.py

import pytest

from app.config import Settings
from app.core.exceptions import ConfigError


def test_config_production_defaults_insecure():
    with pytest.raises(ConfigError) as exc_info:
        Settings(
            app_env="production",
            api_key="dev-api-key-insegura",
            secret_key="chave-insegura-apenas-para-desenvolvimento",
            gemini_api_key=""
        )
    assert "Configuração insegura" in str(exc_info.value)

def test_config_development_defaults_allowed():
    settings = Settings(
        app_env="development",
        api_key="dev-api-key-insegura"
    )
    assert settings.is_development is True

def test_config_production_admin_key_insegura():
    with pytest.raises(ConfigError) as exc_info:
        Settings(
            app_env="production",
            api_key="a" * 32,
            secret_key="b" * 32,
            admin_api_key="dev-admin-key-insegura-para-teste",
            gemini_api_key="alguma-chave-valida",
        )
    assert "Configuração insegura" in str(exc_info.value)


# =============================================================================
# Validacao de seguranca em ambientes nao-produtivos
# =============================================================================
# Antes `_validar_seguranca` comecava com `if app_env != "production": return`.
# Resultado: fora de producao ninguem descobria que a chave era default — e,
# quando o APP_ENV vinha errado por acidente (o incidente do bloco '#test' no
# .env), ninguem descobria em producao tambem. Agora a checagem sempre roda; o
# que varia e a severidade.
# =============================================================================

def test_desenvolvimento_avisa_sobre_chave_insegura(caplog):
    """Nao e fatal, mas tem que aparecer no log — senao o problema so e
    descoberto quando vira producao."""
    with caplog.at_level("WARNING", logger="app.config"):
        settings = Settings(app_env="development", api_key="dev-api-key-insegura")

    assert settings.is_development is True
    assert "API_KEY" in caplog.text
    assert "produção" in caplog.text


def test_desenvolvimento_com_chaves_fortes_nao_avisa(caplog):
    """Contraprova: o aviso nao pode virar ruido constante, senao e ignorado."""
    with caplog.at_level("WARNING", logger="app.config"):
        Settings(
            app_env="development",
            api_key="a" * 32,
            secret_key="b" * 32,
            admin_api_key="c" * 32,
            gemini_api_key="uma-chave",
        )
    assert "API_KEY" not in caplog.text


def test_ambiente_testing_nao_polui_o_log(caplog):
    """A suite roda com chaves default de proposito; avisar a cada teste
    esconderia os avisos que importam."""
    with caplog.at_level("WARNING", logger="app.config"):
        Settings(app_env="testing", api_key="dev-api-key-insegura")
    assert "API_KEY" not in caplog.text


def test_producao_exige_gemini_api_key():
    """Sem chave do Gemini a aplicacao sobe, mas sem LLM, RAG nem escopo
    temporal — degradacao silenciosa que ja aconteceu em producao."""
    with pytest.raises(ConfigError) as exc_info:
        Settings(
            app_env="production",
            api_key="a" * 32,
            secret_key="b" * 32,
            admin_api_key="c" * 32,
            gemini_api_key="",
        )
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_producao_com_tudo_forte_sobe():
    """Contraprova: a trava nao pode impedir uma configuracao legitima."""
    settings = Settings(
        app_env="production",
        api_key="a" * 32,
        secret_key="b" * 32,
        admin_api_key="c" * 32,
        gemini_api_key="uma-chave-real",
    )
    assert settings.is_production is True


def test_chave_de_31_caracteres_e_rejeitada_em_producao():
    """Borda do limite de 32."""
    with pytest.raises(ConfigError):
        Settings(
            app_env="production",
            api_key="a" * 31,
            secret_key="b" * 32,
            admin_api_key="c" * 32,
            gemini_api_key="x",
        )


# =============================================================================
# Validacao dos arquivos .env (chaves duplicadas)
# =============================================================================

def test_validar_arquivos_env_derruba_boot_com_duplicata(tmp_path, monkeypatch):
    """O caminho real de boot: get_settings() -> validar_arquivos_env()."""
    from app import config as config_mod

    env = tmp_path / ".env"
    env.write_text("APP_ENV=production\nAPP_ENV=development\n", encoding="utf-8")

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(config_mod, "ENV_FILES", (str(env),))

    with pytest.raises(ConfigError) as exc_info:
        config_mod.validar_arquivos_env()

    mensagem = str(exc_info.value)
    assert "APP_ENV" in mensagem
    assert "1, 2" in mensagem, "a mensagem precisa apontar as linhas para o fix ser obvio"


def test_validar_arquivos_env_passa_com_env_limpo(tmp_path, monkeypatch):
    from app import config as config_mod

    env = tmp_path / ".env"
    env.write_text("APP_ENV=production\nAPI_KEY=abc\n", encoding="utf-8")

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(config_mod, "ENV_FILES", (str(env),))

    config_mod.validar_arquivos_env()  # nao levanta


def test_validacao_de_env_e_independente_do_app_env(tmp_path, monkeypatch):
    """O ponto central: o incidente sobrescreveu o proprio APP_ENV. Se a trava
    dependesse dele, seria desarmada pela falha que deveria detectar.

    Aqui o .env diz 'development' duas vezes — e mesmo assim tem que derrubar.
    """
    from app import config as config_mod

    env = tmp_path / ".env"
    env.write_text('API_KEY=real\nAPP_ENV=development\nAPI_KEY="dev-api-key-insegura"\n', encoding="utf-8")

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(config_mod, "ENV_FILES", (str(env),))

    with pytest.raises(ConfigError):
        config_mod.validar_arquivos_env()


def test_suite_de_testes_nao_e_derrubada_pelo_env_do_repo(tmp_path, monkeypatch):
    """APP_ENV=testing vem de os.environ (tests/conftest.py), nao do arquivo —
    por isso nao pode ser forjado por um .env duplicado."""
    from app import config as config_mod

    env = tmp_path / ".env"
    env.write_text("API_KEY=um\nAPI_KEY=dois\n", encoding="utf-8")

    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setattr(config_mod, "ENV_FILES", (str(env),))

    config_mod.validar_arquivos_env()  # nao levanta


def test_get_settings_chama_a_validacao_de_env(tmp_path, monkeypatch):
    """A trava so protege se estiver LIGADA no caminho de boot.

    Sem este teste, remover a chamada de `validar_arquivos_env()` dentro de
    `get_settings()` passa despercebido: toda a logica continua correta e
    testada, mas ninguem a executa. Verificado por mutacao — era o unico
    buraco da bateria.
    """
    from app import config as config_mod

    env = tmp_path / ".env"
    env.write_text("API_KEY=um\nAPI_KEY=dois\n", encoding="utf-8")

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(config_mod, "ENV_FILES", (str(env),))

    config_mod.get_settings.cache_clear()
    try:
        with pytest.raises(ConfigError):
            config_mod.get_settings()
    finally:
        # Devolve o singleton ao estado da suite (conftest define APP_ENV=testing).
        config_mod.get_settings.cache_clear()


def test_env_files_do_pydantic_e_da_validacao_sao_os_mesmos():
    """Se as duas listas divergirem, existe um .env que o Pydantic le e a
    checagem de duplicatas nao confere — exatamente o ponto cego que a trava
    deveria cobrir."""
    from app import config as config_mod

    assert config_mod.Settings.model_config["env_file"] == config_mod.ENV_FILES


def test_env_inexistente_nao_derruba_boot(monkeypatch):
    """ENV_FILES tem tres caminhos e normalmente so um existe."""
    from app import config as config_mod

    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(config_mod, "ENV_FILES", ("nao/existe/.env", "tambem/nao/.env"))

    config_mod.validar_arquivos_env()  # nao levanta
