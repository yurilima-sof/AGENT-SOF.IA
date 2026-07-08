# =============================================================================
# app/main.py - Ponto de Entrada da API FastAPI
# =============================================================================
# COMO RODAR LOCALMENTE:
#   uvicorn app.main:app --reload --port 8000
#
# SWAGGER UI (documentação interativa):
#   Acesse http://localhost:8000/docs
# =============================================================================


import logging
import secrets
import time
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.config import get_settings
from app.database import async_session_maker
from app.schemas.agent import AgentRequest, AgentResponse, ErrorResponse
from app.services.llm_service import llm_service

# =============================================================================
# CONFIGURAÇÃO DO LOGGER
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# SEGURANÇA: AUTENTICAÇÃO VIA API KEY
# =============================================================================
# O n8n deve enviar no header: Authorization: Bearer <API_KEY>
# A comparação é feita com secrets.compare_digest (timing-safe) para
# prevenir ataques de timing que poderiam adivinhar a chave.
# =============================================================================

_bearer_scheme = HTTPBearer(
    description="Chave de autenticação da API. Envie no formato: Bearer <API_KEY>",
)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    Dependência FastAPI que valida a API Key do header Authorization.

    Retorna a chave validada ou lança HTTP 401 se inválida.
    Usa comparação timing-safe para evitar ataques de side-channel.
    """
    if not secrets.compare_digest(credentials.credentials, settings.api_key):
        logger.warning("🔒 Tentativa de acesso com API Key inválida.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "API Key inválida ou ausente."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


# =============================================================================
# SEGURANÇA: RATE LIMITING
# =============================================================================
# Limita a quantidade de requisições por IP para prevenir abuso e DDoS.
# Padrão: 60 requisições por minuto por IP.
# =============================================================================

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


# =============================================================================
# LÓGICA DE IDENTIFICAÇÃO DE INTENÇÃO (FASE DE TESTES - SEM LLM)
# =============================================================================
# Esta função replica a lógica JS do nó "Identificar Ação e Buscar IFTTT"
# do n8n, mas agora rodando dentro da nossa API Python.
#
# VANTAGEM sobre o JS hardcoded no n8n:
#   - Fácil de expandir e versionar
#   - Testável com pytest
#   - Futuramente substituída pelo pipeline RAG (LangChain) sem mexer no n8n
#
# CONCEITO para o estagiário:
#   Por enquanto usamos "keyword matching" (busca por palavras-chave).
#   É simples mas funciona bem para comandos diretos como
#   "esfriar", "desligar", "opção 1", etc.
#   Quando integrarmos o LLM (Fase 2), ele entenderá frases complexas
#   como "tá muito abafado aqui" automaticamente.
# =============================================================================

# Mapeamento de palavras-chave → ação IFTTT
# Estes são os mesmos padrões do JS do n8n, centralizados aqui.
_KEYWORDS: dict[str, list[str]] = {
    "freezer": [
        "frio", "fria", "gelado", "congelar", "esfriar",
        "freezer", "freeze", "quente demais", "muito quente",
        "calor", "ta quente", "tá quente", "opção 1", "opcao 1",
        "🔥", "opção1", "opcao1", "ação:freezer", "t-low", "baixo", "low",
    ],
    "esquentar": [
        "esquentar", "aquecer", "warm", "high", "t-high",
        "thigh", "frio demais", "muito frio", "gelado demais",
        "ta frio", "tá frio", "opção 2", "opcao 2", "🥶",
        "opção2", "opcao2", "ação:esquentar",
    ],
    "medio": [
        "medio", "médio", "medium", "t-medium", "t-médium",
        "temperatura média", "primeiro calor"
    ],
    "off": [
        "desligar maquinas", "off", "parar", "cancelar",
        "podem desligar todas", "opção 3", "opcao 3", "❌",
        "opção3", "opcao3", "ação:off",
        "revenda fechada hoje", "estamos fechado",
        "por favor desligar maquinas",
    ],
    "ligar": [
        "ligar arcondicionado", "ligar ar-condicionado", "ligar ar condicionado",
        "ligar maquina", "ligar maquinas", "ligar todos", "ligar tudo",
        "ligar ar", "ligar", "ação:ligar",
    ],
}

# Mapeamento de ação → intenção semântica (para o campo `intencao` da resposta)
_ACAO_PARA_INTENCAO: dict[str, str] = {
    "freezer": "ligar_resfriamento",
    "esquentar": "ligar_aquecimento",
    "medio": "ligar_temperatura_media",
    "off": "desligar_dispositivos",
    "ligar": "ligar_dispositivos",
}

# Mensagens de resposta padrão para o WhatsApp
_MENSAGENS_RESPOSTA: dict[str, str] = {
    "freezer": "Entendido! ❄️ Ativando modo resfriamento. Aguarde alguns instantes.",
    "esquentar": "Entendido! 🔆 Ativando aquecimento. Aguarde alguns instantes.",
    "medio": "Entendido! 🌤️ Ajustando para uma temperatura média. Aguarde alguns instantes.",
    "off": "Ok! ✅ Desativando os equipamentos. Qualquer dúvida, estou aqui.",
    "ligar": "Entendido! ⚡ Ligando os equipamentos. Aguarde alguns instantes.",
    "nenhuma": "Olá! 🤖 Sou o Bot SOF. Como posso te ajudar com a temperatura do ambiente hoje?",
}

# Lista de tuplas (keyword, acao) ordenada pelo tamanho da keyword em ordem decrescente.
# Isso evita conflitos de substring (ex: "muito frio" disparar "freezer" por causa de "frio").
_KEYWORDS_ORDENADAS: list[tuple[str, str]] = sorted(
    [(kw, acao) for acao, kws in _KEYWORDS.items() for kw in kws],
    key=lambda item: len(item[0]),
    reverse=True,
)


def identificar_acao(mensagem: str) -> Optional[str]:
    """
    Analisa a mensagem do usuário e identifica a ação IoT correspondente.

    Replica a lógica do nó JavaScript 'Identificar Ação e Buscar IFTTT' do n8n,
    mas agora centralizada e testável em Python.

    Args:
        mensagem: Texto enviado pelo usuário no WhatsApp.

    Returns:
        'freezer', 'esquentar', 'medio', 'off', ou None se nenhuma ação for identificada.
    """
    texto = mensagem.lower().strip()

    # Percorre as palavras-chave ordenadas por tamanho para evitar conflitos de substring
    for keyword, acao in _KEYWORDS_ORDENADAS:
        if keyword in texto:
            logger.info(f"   Keyword detectada: '{keyword}' → ação: '{acao}'")
            return acao

    return None  # Nenhuma ação identificada → só conversa, sem comando IoT


# =============================================================================
# FUNÇÕES DE ACESSO AO BANCO DE DADOS
# =============================================================================

async def buscar_link_ifttt(id_grupo: str, acao: str) -> Optional[str]:
    """
    Consulta a tabela mapa_revendas para obter a URL IFTTT do grupo/ação.

    Em vez de manter links hardcoded no código, buscamos diretamente do
    campo JSONB `credenciais_tuya` no banco de dados.

    Args:
        id_grupo: ID do grupo de WhatsApp.
        acao: Ação identificada ('freezer', 'esquentar', 'medio', 'off').

    Returns:
        URL do webhook IFTTT ou None se não encontrado/grupo inativo.
    """
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                text("""
                    SELECT credenciais_tuya->>:acao AS link_ifttt
                    FROM mapa_revendas
                    WHERE id_grupo_wpp = :id_grupo
                      AND ativo = true
                """),
                {"acao": acao, "id_grupo": id_grupo}
            )
            row = result.fetchone()
            if row and row.link_ifttt:
                logger.info(f"   Link IFTTT encontrado no banco para '{acao}'")
                return row.link_ifttt
            logger.info(f"   Nenhum link IFTTT no banco para grupo '{id_grupo}' / ação '{acao}'")
            return None
        except Exception as e:
            logger.warning(f"⚠️ Erro ao consultar mapa_revendas: {e}")
            return None


async def registrar_log(
    id_grupo: str,
    nome_revenda: str,
    mensagem_original: str,
    intencao: Optional[str],
    status_op: str,
    tempo_resposta_ms: int,
    detalhes: Optional[dict] = None,
) -> None:
    """
    Registra a operação na tabela logs_operacoes para auditoria.

    Args:
        id_grupo: ID do grupo de WhatsApp.
        nome_revenda: Nome da revenda.
        mensagem_original: Texto enviado pelo usuário.
        intencao: Intenção identificada pelo agente.
        status_op: Resultado da operação ('sucesso', 'sem_acao', 'erro').
        tempo_resposta_ms: Latência total em milissegundos.
        detalhes: JSON com dados extras (ação IFTTT, link, etc.).
    """
    async with async_session_maker() as session:
        try:
            await session.execute(
                text("""
                    INSERT INTO logs_operacoes
                        (id_grupo, nome_revenda, mensagem_original, intencao,
                         status, tempo_resposta_ms, detalhes)
                    VALUES
                        (:id_grupo, :nome_revenda, :mensagem_original, :intencao,
                         :status, :tempo_ms, :detalhes)
                """),
                {
                    "id_grupo": id_grupo,
                    "nome_revenda": nome_revenda,
                    "mensagem_original": mensagem_original,
                    "intencao": intencao,
                    "status": status_op,
                    "tempo_ms": tempo_resposta_ms,
                    "detalhes": json.dumps(detalhes or {}),
                }
            )
            await session.commit()
        except Exception as e:
            logger.warning(f"⚠️ Erro ao registrar log: {e}")



# =============================================================================
# LIFESPAN - Eventos de Inicialização e Finalização
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # --- STARTUP ---
    logger.info("=" * 60)
    logger.info(f"🚀 Iniciando: {settings.app_name} v{settings.app_version}")
    logger.info(f"   Ambiente : {settings.app_env.upper()}")
    logger.info(f"   Modo     : IFTTT Bridge (Fase de Testes)")
    logger.info("=" * 60)

    # TODO (Fase 2): Inicializar pool de conexões com o banco
    # TODO (Fase 2): Carregar índice RAG

    yield

    logger.info("🛑 Encerrando a aplicação...")


# =============================================================================
# INSTÂNCIA DA APLICAÇÃO FASTAPI
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API de inteligência para controle de dispositivos IoT via WhatsApp. "
        "**Fase atual:** IFTTT Bridge — identifica intenções e retorna a ação para o n8n acionar o IFTTT. "
        "**Próxima fase:** RAG + Tuya API direta."
    ),
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# Integra o rate limiter ao app
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Retorna HTTP 429 quando o limite de requisições por IP é excedido."""
    logger.warning(f"⚠️ Rate limit excedido para IP: {request.client.host}")
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "rate_limit_exceeded",
            "message": "Muitas requisições. Aguarde um momento e tente novamente.",
        },
    )


# =============================================================================
# MIDDLEWARES
# =============================================================================

# CORS: Em produção, desabilitamos origens externas pois a API é server-to-server.
# Em desenvolvimento, permitimos todas para facilitar testes locais.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"] if settings.is_development else ["POST", "GET"],
    allow_headers=["*"] if settings.is_development else ["Authorization", "Content-Type"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Loga método, URL e tempo de resposta de cada requisição."""
    start_time = time.monotonic()
    response = await call_next(request)
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    logger.info(
        f"{request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Tempo: {elapsed_ms}ms"
    )
    return response


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get(
    "/health",
    summary="Verificação de Saúde",
    tags=["Utilitários"],
)
async def health_check() -> dict:
    """Verifica se a API está no ar. Usado pelo Docker e ferramentas de monitoramento."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.app_env,
        "mode": "ifttt_bridge",
    }


@app.post(
    "/agent",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Processar Comando do WhatsApp",
    description=(
        "Recebe uma mensagem do WhatsApp (via n8n), identifica a intenção "
        "e retorna o JSON estruturado. **Na fase de testes**, o campo `ifttt_action` "
        "indica ao n8n qual webhook IFTTT disparar (freezer / esquentar / medio / off). "
        "**Requer autenticação** via header `Authorization: Bearer <API_KEY>`."
    ),
    responses={
        200: {"description": "Comando processado.", "model": AgentResponse},
        401: {"description": "API Key inválida ou ausente."},
        422: {"description": "Payload inválido."},
        429: {"description": "Rate limit excedido."},
        500: {"description": "Erro interno.", "model": ErrorResponse},
    },
    tags=["Agente IA"],
)
@limiter.limit("60/minute")
async def process_agent_command(
    request: Request,
    payload: AgentRequest = Body(...),
    _api_key: str = Depends(verify_api_key),
) -> AgentResponse:
    """
    Endpoint principal. Recebe o comando e retorna a ação a executar.

    ## Fluxo atual:
    1. Recebe e valida o payload JSON com Pydantic.
    2. Identifica a intenção usando RAG + OpenAI (GPT-4o-mini).
    3. Se o LLM falhar ou não houver chave no .env, aplica o fallback por palavras-chave.
    4. Retorna a ação IFTTT e a mensagem de resposta correspondente.
    """
    start_time = time.monotonic()

    # Logs sanitizados: trunca mensagem e mascara id_grupo para segurança
    _msg_truncada = payload.mensagem[:50] + ("..." if len(payload.mensagem) > 50 else "")
    _grupo_masked = f"***{payload.id_grupo[-8:]}" if len(payload.id_grupo) > 8 else payload.id_grupo
    logger.info(
        f"📩 Nova requisição | "
        f"Revenda: '{payload.nome_revenda}' | "
        f"Grupo: {_grupo_masked} | "
        f"Mensagem: '{_msg_truncada}'"
    )

    try:
        # -----------------------------------------------------------------
        # PASSO 1: Identificar a ação e intenção (LLM com RAG ou Fallback)
        # -----------------------------------------------------------------
        acao = None
        intencao = None
        mensagem_wpp = None

        if settings.gemini_api_key:
            try:
                logger.info("   [LLM] Processando mensagem com Google Gemini-2.5-Flash...")
                resultado = await llm_service.processar_mensagem(payload.mensagem, payload.id_grupo)
                intencao = resultado.get("intencao")
                acao = resultado.get("ifttt_action")
                mensagem_wpp = resultado.get("mensagem_wpp")

                # Normalização de nulos vindos da resposta JSON do LLM
                if acao == "null" or acao == "None" or not acao:
                    acao = None
            except Exception as e:
                logger.warning(f"⚠️ Falha no processamento com LLM/Gemini (aplicando Fallback): {e}")
                acao = None
                intencao = None
                mensagem_wpp = None

        # Fallback de Palavras-Chave (Keyword Matching)
        if not intencao:
            logger.info("   [Fallback] Identificando ação via Keyword Matching...")
            acao = identificar_acao(payload.mensagem)
            if acao:
                intencao = _ACAO_PARA_INTENCAO[acao]
                mensagem_wpp = _MENSAGENS_RESPOSTA[acao]
            else:
                intencao = "sem_acao"
                mensagem_wpp = _MENSAGENS_RESPOSTA["nenhuma"]

        # -----------------------------------------------------------------
        # PASSO 2: Montar a resposta com base na ação identificada
        # -----------------------------------------------------------------
        if acao:
            # Ação encontrada → vamos comandar o dispositivo via IFTTT
            intencao = _ACAO_PARA_INTENCAO.get(acao, intencao)
            
            # Busca o link IFTTT do banco de dados (mapa_revendas.credenciais_tuya)
            link_ifttt = await buscar_link_ifttt(payload.id_grupo, acao)

            logger.info(
                f"✅ Ação identificada: '{acao}' | "
                f"Intenção: '{intencao}' | "
                f"Link IFTTT: '{link_ifttt}' | "
                f"Revenda: '{payload.nome_revenda}'"
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # Registra a operação no log de auditoria
            await registrar_log(
                id_grupo=payload.id_grupo,
                nome_revenda=payload.nome_revenda,
                mensagem_original=payload.mensagem,
                intencao=intencao,
                status_op="sucesso",
                tempo_resposta_ms=elapsed_ms,
                detalhes={"acao_ifttt": acao, "link_ifttt": link_ifttt},
            )

            return AgentResponse(
                intencao=intencao,
                dispositivo_id=None,       # Será preenchido na Fase 2 (Tuya)
                ifttt_action=acao,         # ← n8n usa este campo para chamar IFTTT
                link_ifttt=link_ifttt,     # URL do webhook buscada do banco
                parametros={},
                mensagem_wpp=mensagem_wpp,
            )

        else:
            # Nenhuma ação → conversa normal, sem comando IoT
            logger.info(
                f"💬 Sem ação IoT detectada | "
                f"Mensagem: '{payload.mensagem}' | "
                f"Revenda: '{payload.nome_revenda}'"
            )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # Registra mesmo as mensagens sem ação (para métricas)
            await registrar_log(
                id_grupo=payload.id_grupo,
                nome_revenda=payload.nome_revenda,
                mensagem_original=payload.mensagem,
                intencao=intencao or "sem_acao",
                status_op="sem_acao",
                tempo_resposta_ms=elapsed_ms,
            )

            return AgentResponse(
                intencao=intencao or "sem_acao",
                dispositivo_id=None,
                ifttt_action=None,         # ← n8n NÃO dispara o IFTTT
                parametros={},
                mensagem_wpp=mensagem_wpp,
            )

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Tenta registrar o erro no log mesmo em caso de falha
        await registrar_log(
            id_grupo=payload.id_grupo,
            nome_revenda=payload.nome_revenda,
            mensagem_original=payload.mensagem,
            intencao=None,
            status_op="erro",
            tempo_resposta_ms=elapsed_ms,
            detalhes={"erro": str(exc)},
        )

        logger.exception(f"❌ Erro ao processar requisição: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "Erro interno ao processar o comando. Tente novamente.",
            },
        ) from exc
