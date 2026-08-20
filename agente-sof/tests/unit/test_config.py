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
