# =============================================================================
# app/config.py - Configurações Centralizadas da Aplicação
# =============================================================================
# Este módulo usa Pydantic Settings para carregar e validar as variáveis
# de ambiente do arquivo .env de forma tipada e segura.
#
# CONCEITO CHAVE para o estagiário:
#   Em vez de chamar os.getenv("DATABASE_URL") espalhado por todo o código,
#   centralizamos TODAS as configurações aqui. Isso tem três vantagens:
#   1. Validação automática: se faltar uma variável obrigatória, a aplicação
#      nem sobe e dá um erro claro dizendo o que está faltando.
#   2. Type hints: cada configuração tem um tipo Python definido.
#   3. Facilidade de teste: é simples substituir as configs em testes.
# =============================================================================

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações globais da aplicação carregadas do arquivo .env.

    O Pydantic Settings lê automaticamente as variáveis de ambiente
    e as mapeia para os atributos desta classe.
    """

    # --- Metadados da Aplicação ---
    app_name: str = Field(default="Agente SOF - API IoT WhatsApp", description="Nome da aplicação.")
    app_version: str = Field(default="0.1.0", description="Versão atual da API.")
    app_env: str = Field(default="development", description="Ambiente de execução: development | staging | production.")
    app_port: int = Field(default=8000, description="Porta onde o Uvicorn vai escutar.")

    # --- Banco de Dados ---
    # A URL completa de conexão é montada a partir das variáveis individuais
    # OU pode ser sobrescrita diretamente com DATABASE_URL no .env.
    database_url: str = Field(
        default="postgresql+asyncpg://agente_user:agente_senha_dev@localhost:5432/agente_sof_db",
        description="URL de conexão com o PostgreSQL para SQLAlchemy assíncrono.",
    )

    # --- API Tuya (IoT) ---
    tuya_base_url: str = Field(
        default="https://openapi.tuyaus.com",
        description="URL base da API da Tuya (default para US).",
    )
    tuya_client_id: str | None = Field(
        default=None,
        description="Client ID gerado no projeto Tuya IoT Platform.",
    )
    tuya_client_secret: str | None = Field(
        default=None,
        description="Client Secret gerado no projeto Tuya IoT Platform.",
    )

    # --- Segurança ---
    secret_key: str = Field(
        default="chave-insegura-apenas-para-desenvolvimento",
        description="Chave secreta para tokens JWT. DEVE ser alterada em produção!",
    )

    api_key: str = Field(
        default="dev-api-key-insegura",
        description=(
            "Chave de autenticação da API. O n8n deve enviar no header "
            "'Authorization: Bearer <api_key>'. DEVE ser alterada em produção!"
        ),
    )

    # --- LLM / IA ---
    # Deixamos o campo opcional para não quebrar a inicialização
    # enquanto não tivermos a chave configurada.
    gemini_api_key: str | None = Field(default=None, description="Chave da API Google Gemini.")
    gemini_model: str = Field(default="gemini-flash-latest", description="Modelo do Google Gemini a ser utilizado.")

    # Configuração do Pydantic Settings:
    # - env_file: lê as variáveis do arquivo .env
    # - env_file_encoding: garante suporte a caracteres especiais no .env
    # - case_sensitive: variáveis de ambiente são case-insensitive (DATABASE_URL == database_url)
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignora variáveis de ambiente que não estão mapeadas aqui.
    )

    @property
    def is_production(self) -> bool:
        """Retorna True se a aplicação está rodando em modo produção."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Retorna True se a aplicação está rodando em modo desenvolvimento."""
        return self.app_env == "development"


# =============================================================================
# PADRÃO SINGLETON COM lru_cache
# =============================================================================
# O @lru_cache garante que o objeto Settings seja criado apenas UMA vez
# durante toda a vida da aplicação (Singleton pattern).
# Isso evita leituras desnecessárias do .env a cada requisição.
#
# Como usar em outros módulos:
#   from app.config import get_settings
#   settings = get_settings()
#   print(settings.database_url)
# =============================================================================

@lru_cache()
def get_settings() -> Settings:
    """
    Retorna a instância única (Singleton) das configurações da aplicação.

    O @lru_cache garante que o arquivo .env seja lido apenas uma vez.
    Use esta função em vez de instanciar Settings() diretamente.
    """
    return Settings()
