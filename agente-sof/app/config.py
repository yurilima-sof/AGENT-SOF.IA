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

import logging
import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Arquivos .env procurados, em ordem de precedência (ver model_config abaixo).
ENV_FILES = (".env", "../.env", "../../.env")

_RE_CHAVE_ENV = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def chaves_duplicadas_em_env(caminho) -> dict[str, list[int]]:
    """
    Devolve {CHAVE: [linhas]} para cada chave definida mais de uma vez no arquivo.

    Existe por causa de um incidente real: alguém colou um bloco de configuração
    de teste no fim do .env de produção. Como o dotenv aplica a ÚLTIMA ocorrência,
    a aplicação passou a rodar com `APP_ENV=development`, `API_KEY` no default
    público que está versionado no git e `GEMINI_API_KEY=""` — silenciosamente,
    por semanas.

    O detalhe que torna isso insidioso: a trava que deveria pegar credencial
    insegura (`_validar_seguranca`) só era fatal quando `APP_ENV == production`,
    e `APP_ENV` era justamente uma das chaves sobrescritas. A trava era desarmada
    pela mesma falha que deveria detectar. Por isso esta checagem NÃO olha o
    ambiente: duplicata em arquivo de segredo não tem uso legítimo.

    Comparação case-insensitive porque o Pydantic Settings também é: `API_KEY` e
    `api_key` são a mesma variável e colidem do mesmo jeito.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        return {}

    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        # Não é motivo para derrubar o boot: o Pydantic vai reclamar depois se o
        # arquivo for mesmo ilegível.
        logger.warning(f"⚠️ Não foi possível ler '{caminho}' para checar chaves duplicadas: {e}")
        return {}

    ocorrencias: dict[str, list[int]] = {}
    aspas_abertas = None  # valor multilinha em andamento

    for numero, linha in enumerate(linhas, start=1):
        if aspas_abertas is not None:
            # Dentro de um valor multilinha: nada aqui é definição de chave.
            if aspas_abertas in linha:
                aspas_abertas = None
            continue

        texto = linha.strip()
        if not texto or texto.startswith("#"):
            continue

        match = _RE_CHAVE_ENV.match(texto)
        if not match:
            continue

        valor = texto[match.end():].lstrip()
        if valor[:1] in ('"', "'"):
            aspas = valor[0]
            # Fechou na mesma linha? Precisa de uma segunda aspa depois da primeira.
            if valor.count(aspas) < 2:
                aspas_abertas = aspas

        ocorrencias.setdefault(match.group(1).upper(), []).append(numero)

    return {chave: linhas_ for chave, linhas_ in ocorrencias.items() if len(linhas_) > 1}


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

    admin_api_key: str = Field(
        default="dev-admin-key-insegura-para-teste",
        description="Chave de acesso ao painel de administração.",
    )

    admin_allowed_ips: str = Field(
        default="",
        description=(
            "Lista de IPs (separados por vírgula) autorizados a acessar qualquer rota /admin/*. "
            "Vazio = sem restrição de IP (não recomendado em produção sem proxy/TLS na frente)."
        ),
    )

    # --- LLM / IA ---
    # Deixamos o campo opcional para não quebrar a inicialização
    # enquanto não tivermos a chave configurada.
    gemini_api_key: str | None = Field(default=None, description="Chave da API Google Gemini.")
    gemini_model: str = Field(default="gemini-3.6-flash", description="Modelo do Google Gemini a ser utilizado.")

    # --- Sentry ---
    sentry_dsn: str | None = Field(default=None, description="SENTRY_DSN para monitoramento de erros.")

    # Configuração do Pydantic Settings:
    # - env_file: lê as variáveis do arquivo .env
    # - env_file_encoding: garante suporte a caracteres especiais no .env
    # - case_sensitive: variáveis de ambiente são case-insensitive (DATABASE_URL == database_url)
    model_config = SettingsConfigDict(
        # Mesma tupla usada por validar_arquivos_env(): a checagem de chaves
        # duplicadas precisa olhar exatamente os arquivos que o Pydantic lê. Se
        # as duas listas divergirem, existe um .env que vale e não é conferido.
        env_file=ENV_FILES,
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

    @property
    def admin_allowed_ips_list(self) -> list[str]:
        """Lista de IPs autorizados a acessar /admin/*, já parseada e sem espaços em branco."""
        return [ip.strip() for ip in self.admin_allowed_ips.split(",") if ip.strip()]

    @model_validator(mode="after")
    def _validar_seguranca(self):
        """
        Checa credenciais fracas em TODOS os ambientes.

        Antes a função inteira começava com `if app_env != "production": return`,
        o que significava que em desenvolvimento ninguém descobria que a chave era
        default — e, quando o APP_ENV vinha errado por acidente, ninguém descobria
        em produção também.

        Agora a checagem sempre roda; o que varia é a severidade: fatal em
        produção, WARNING no resto. Assim o problema fica visível no log de
        qualquer ambiente sem impedir o desenvolvimento local de subir.
        """
        defaults_inseguros = {"dev-api-key-insegura", "chave-insegura-apenas-para-desenvolvimento", "dev-admin-key-insegura-para-teste", ""}
        problemas = []
        if self.api_key in defaults_inseguros or len(self.api_key) < 32:
            problemas.append("API_KEY (deve ser alterada e possuir >=32 caracteres)")
        if self.secret_key in defaults_inseguros or len(self.secret_key) < 32:
            problemas.append("SECRET_KEY (deve ser alterada e possuir >=32 caracteres)")
        if self.admin_api_key in defaults_inseguros or len(self.admin_api_key) < 32:
            problemas.append("ADMIN_API_KEY (deve ser alterada e possuir >=32 caracteres)")
        if not self.gemini_api_key:
            problemas.append("GEMINI_API_KEY (obrigatória em produção)")

        if not problemas:
            return self

        if self.app_env == "production":
            from app.core.exceptions import ConfigError
            raise ConfigError(f"Configuração insegura para ambiente de produção: {', '.join(problemas)}")

        if self.app_env != "testing":
            logger.warning(
                f"⚠️ Configuração insegura detectada (ambiente '{self.app_env}', por isso não é fatal): "
                f"{', '.join(problemas)}. Em produção isto impediria o boot."
            )
        return self


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

def validar_arquivos_env() -> None:
    """
    Recusa o boot se algum .env definir a mesma chave duas vezes.

    Mora aqui, e não num `model_validator`, porque é uma checagem do ARQUIVO e
    não desta instância de `Settings` — testes que constroem `Settings(...)` com
    valores explícitos não deveriam depender do .env que existe no disco.
    Chamada de `get_settings()`, que é por onde a aplicação inteira passa.

    O desvio de ambiente lê `os.environ` diretamente, em vez de `settings.app_env`:
    o incidente que originou esta checagem sobrescreveu justamente o `APP_ENV` via
    arquivo, desarmando as validações que dependiam dele. Variável de processo não
    tem esse problema — é o que a suíte de testes usa (ver tests/conftest.py).
    """
    if os.environ.get("APP_ENV") == "testing":
        return

    achados = []
    for nome_arquivo in ENV_FILES:
        duplicadas = chaves_duplicadas_em_env(nome_arquivo)
        for chave, linhas in sorted(duplicadas.items()):
            achados.append(
                f"{chave} em '{nome_arquivo}' (linhas {', '.join(str(n) for n in linhas)})"
            )

    if achados:
        from app.core.exceptions import ConfigError
        raise ConfigError(
            "Chave(s) definida(s) mais de uma vez no .env. O dotenv aplica a ÚLTIMA "
            "ocorrência, então o valor efetivo pode não ser o que você espera — foi "
            "assim que a aplicação rodou em produção com a API_KEY default. "
            "Deixe uma definição por chave: " + "; ".join(achados)
        )


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna a instância única (Singleton) das configurações da aplicação.

    O @lru_cache garante que o arquivo .env seja lido apenas uma vez.
    Use esta função em vez de instanciar Settings() diretamente.
    """
    validar_arquivos_env()
    return Settings()
