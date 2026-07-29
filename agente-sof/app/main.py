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
from app.schemas.rag import RagIngestRequest, RagIngestResponse
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service

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

limiter = Limiter(key_func=get_remote_address, default_limits=["600/minute"])


# Importações para o banco de dados (injeção de dependência)
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

# Importações dos novos serviços e CRUDs
from app.crud.revendas import buscar_credenciais_revenda
from app.crud.logs import registrar_log
from app.services.fallback_service import identificar_acao, get_intencao_and_message
from app.crud.tuya import get_home_by_nome, get_scene_by_ambiente
from app.services.tuya_service import tuya_service

async def buscar_link_ifttt(credenciais: dict, acao: str, ambiente: Optional[str] = None) -> Optional[str]:
    """
    Busca a URL IFTTT dentro das credenciais_tuya da revenda.
    Se 'ambiente' for fornecido, tenta buscar a chave 'acao_ambiente'.
    Se não encontrar, ou se não houver ambiente, busca a chave 'acao'.
    """
    if not credenciais:
        return None
        
    if ambiente:
        chave_ambiente = f"{acao}_{ambiente}"
        if chave_ambiente in credenciais:
            logger.info(f"   Link IFTTT específico encontrado para ambiente: '{chave_ambiente}'")
            return credenciais[chave_ambiente]
        logger.info(f"   Link IFTTT para '{chave_ambiente}' não encontrado. Tentando fallback para geral.")
        
    if acao in credenciais:
        logger.info(f"   Link IFTTT geral encontrado para '{acao}'")
        return credenciais[acao]
        
    logger.info(f"   Nenhum link IFTTT encontrado para '{acao}'")
    return None




# =============================================================================
# LIFESPAN - Eventos de Inicialização e Finalização
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # --- STARTUP ---
    logger.info("=" * 60)
    logger.info(f"🚀 Iniciando: {settings.app_name} v{settings.app_version}")
    logger.info(f"   Ambiente : {settings.app_env.upper()}")
    logger.info(f"   Modo     : Tuya API Direta + IFTTT Fallback")
    logger.info("=" * 60)

    # TODO (Fase 2): Inicializar pool de conexões com o banco
    # TODO (Fase 2): Carregar índice RAG

    yield

    logger.info("🛑 Encerrando a aplicação...")


# =============================================================================
# INSTÂNCIA DA APLICAÇÃO FASTAPI
# =============================================================================

def create_app() -> FastAPI:
    """
    Factory function para criação do app FastAPI.
    """
    app_instance = FastAPI(
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
    app_instance.state.limiter = limiter

    @app_instance.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        logger.warning(f"⚠️ Rate limit excedido para IP: {request.client.host}")
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Muitas requisições. Aguarde um momento e tente novamente.",
            },
        )

    # CORS
    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app_instance.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            f"{request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Tempo: {elapsed_ms}ms"
        )
        return response

    return app_instance

app = create_app()


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
@limiter.limit("600/minute")
async def process_agent_command(
    request: Request,
    payload: AgentRequest = Body(...),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """
    Endpoint principal. Recebe o comando e retorna a ação a executar.

    ## Fluxo atual:
    1. Recebe e valida o payload JSON com Pydantic.
    2. Identifica a intenção usando RAG + Google Gemini.
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
        ambiente = None
        mensagem_wpp = None

        if settings.gemini_api_key:
            try:
                logger.info("   [Banco] Buscando credenciais e ambientes cadastrados...")
                
                # NOVO FLUXO: Busca ambientes cadastrados diretamente das Cenas Tuya
                from app.crud.tuya import get_ambientes_by_cliente
                ambientes_disponiveis = await get_ambientes_by_cliente(db, payload.nome_revenda)
                
                # Retém a busca de credenciais antigas caso precise para logs
                credenciais = await buscar_credenciais_revenda(db, payload.id_grupo)
                
                # Fallback: se não tiver ambientes na Tuya, tenta extrair das credenciais antigas (retrocompatibilidade temporária)
                if not ambientes_disponiveis and credenciais:
                    for chave in credenciais.keys():
                        if "_" in chave and chave.split("_", 1)[1] not in ambientes_disponiveis:
                            ambientes_disponiveis.append(chave.split("_", 1)[1])

                logger.info("   [LLM] Processando mensagem com Google Gemini-2.5-Flash...")
                resultado = await llm_service.processar_mensagem(payload.mensagem, payload.id_grupo, ambientes_disponiveis)
                intencao = resultado.get("intencao")
                acao = resultado.get("ifttt_action")
                ambiente = resultado.get("ambiente")
                mensagem_wpp = resultado.get("mensagem_wpp")

                # --- Filtro de Memória Orgânica ---
                if resultado.get("salvar_memoria") is True:
                    try:
                        logger.info("   [RAG] Memória orgânica útil detectada! Salvando regra no banco vetorial.")
                        await rag_service.ingest_message(payload.id_grupo, payload.mensagem)
                    except Exception as e_rag:
                        logger.warning(f"⚠️ Falha ao auto-salvar memória orgânica: {e_rag}")

                # Normalização de nulos vindos da resposta JSON do LLM
                if acao == "null" or acao == "None" or not acao:
                    acao = None
            except Exception as e:
                logger.warning(f"⚠️ Falha no processamento com LLM/Gemini (aplicando Fallback): {e}")
                acao = None
                intencao = None
                ambiente = None
                mensagem_wpp = None
                credenciais = await buscar_credenciais_revenda(db, payload.id_grupo)

        # Fallback de Palavras-Chave (Keyword Matching)
        if not intencao or intencao == "sem_acao":
            logger.info("   [Fallback] Identificando ação via Keyword Matching...")
            acao_fallback = identificar_acao(payload.mensagem)
            if acao_fallback:
                acao = acao_fallback
                intencao, mensagem_wpp = get_intencao_and_message(acao)

        # -----------------------------------------------------------------
        # PASSO 2: Montar a resposta com base na ação identificada
        # -----------------------------------------------------------------
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if acao:
            # 1. TENTA EXECUTAR NATIVAMENTE NA TUYA
            tuya_success = None
            try:
                # Busca a revenda (home) pelo nome exato vindo do WhatsApp
                home_data = await get_home_by_nome(db, payload.nome_revenda)
                if home_data:
                    home_id = home_data["home_id"]
                    
                    if acao == "desativar_automacao" or intencao == "pausar_automacao":
                        # Busca automações ativas na Tuya Cloud e desativa regras de desligamento/timer
                        logger.info(f"   [Tuya] Buscando automações da residência {home_id} para pausar automações para reunião/fechamento...")
                        automacoes = await tuya_service.get_automations_by_home(home_id)
                        desativadas_ids = []
                        if automacoes and isinstance(automacoes, list):
                            for auto in automacoes:
                                auto_id = auto.get("id") or auto.get("automation_id")
                                is_enabled = auto.get("enabled", True)
                                if auto_id and is_enabled:
                                    logger.info(f"   [Tuya] Desativando automação temporariamente: '{auto.get('name')}' (ID: {auto_id})")
                                    await tuya_service.set_automation_status(home_id, auto_id, enable=False)
                                    desativadas_ids.append(auto_id)
                        tuya_success = (len(desativadas_ids) > 0)

                        # Agenda a REATIVAÇÃO AUTOMÁTICA em segundo plano no horário solicitado
                        if desativadas_ids:
                            from app.services.scheduler_service import scheduler_service
                            horario_fim = scheduler_service.extrair_horario_termino(payload.mensagem)
                            await scheduler_service.agendar_reativacao_automacao(
                                id_grupo=payload.id_grupo,
                                nome_revenda=payload.nome_revenda,
                                home_id=home_id,
                                automacao_ids=desativadas_ids,
                                horario_execucao=horario_fim
                            )
                    else:
                        # O ambiente pode vir nulo. Se for nulo, procuramos por cenas sem ambiente ou ignoramos
                        amb = ambiente if ambiente else ""
                        scene_data = await get_scene_by_ambiente(db, home_id, amb, acao)
                        if scene_data:
                            scene_id = scene_data["scene_id"]
                            logger.info(f"   [Tuya] Cenário encontrado: {scene_data['nome_cena']} (ID: {scene_id}). Disparando...")
                            result_tuya = await tuya_service.execute_scene(home_id, scene_id)
                            tuya_success = result_tuya
                        else:
                            logger.info(f"   [Tuya] Nenhuma cena encontrada para ambiente '{amb}' e ação '{acao}'.")
                else:
                    logger.info(f"   [Tuya] Revenda '{payload.nome_revenda}' não encontrada na base Tuya.")
            except Exception as e_tuya:
                logger.error(f"   [Tuya] Erro ao tentar disparar cena: {e_tuya}")
                tuya_success = False

            # 2. BUSCA O IFTTT COMO PLANO B (Fallback)
            link_ifttt = await buscar_link_ifttt(credenciais, acao, ambiente)

            logger.info(
                f"✅ Ação identificada: '{acao}' | "
                f"Ambiente: '{ambiente}' | "
                f"Intenção: '{intencao}' | "
                f"Tuya Success: {tuya_success} | "
                f"Link IFTTT (Fallback): '{link_ifttt}'"
            )

            await registrar_log(
                db=db,
                id_grupo=payload.id_grupo,
                nome_revenda=payload.nome_revenda,
                mensagem_original=payload.mensagem,
                intencao=intencao,
                status_op="sucesso",
                tempo_resposta_ms=elapsed_ms,
                acao_executada=acao,
                ambiente=ambiente
            )

            return AgentResponse(
                intencao=intencao,
                ambiente=ambiente,
                dispositivo_id=None,
                ifttt_action=acao,
                link_ifttt=link_ifttt,
                tuya_success=tuya_success,
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

            await registrar_log(
                db=db,
                id_grupo=payload.id_grupo,
                nome_revenda=payload.nome_revenda,
                mensagem_original=payload.mensagem,
                intencao=intencao or "sem_acao",
                status_op="sem_acao",
                tempo_resposta_ms=elapsed_ms,
                acao_executada=None,
                ambiente=None
            )

            return AgentResponse(
                intencao=intencao or "sem_acao",
                ambiente=ambiente if 'ambiente' in locals() else None,
                dispositivo_id=None,
                ifttt_action=None,         # ← n8n NÃO dispara o IFTTT
                parametros={},
                mensagem_wpp=mensagem_wpp or "Olá! Como posso te ajudar com a temperatura do ambiente hoje?",
            )

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Tenta registrar o erro no log mesmo em caso de falha
        await registrar_log(
            db=db,
            id_grupo=payload.id_grupo,
            nome_revenda=payload.nome_revenda,
            mensagem_original=payload.mensagem,
            intencao=None,
            status_op="erro",
            tempo_resposta_ms=elapsed_ms,
            acao_executada=None,
            ambiente=None,
        )

        logger.exception(f"❌ Erro ao processar requisição: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "Erro interno ao processar o comando. Tente novamente.",
            },
        ) from exc


@app.post(
    "/rag/aprender",
    response_model=RagIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingerir novo conhecimento no RAG",
    tags=["RAG"],
)
async def aprender_conhecimento(
    payload: RagIngestRequest = Body(...),
    _api_key: str = Depends(verify_api_key),
) -> RagIngestResponse:
    """
    Recebe uma nova mensagem/regra e a salva no banco vetorial para a revenda específica (ou para GLOBAL_MANUAL).
    """
    try:
        await rag_service.ingest_message(payload.id_grupo, payload.mensagem)
        return RagIngestResponse(
            status="sucesso",
            mensagem=f"Conhecimento ingerido com sucesso para o grupo {payload.id_grupo}."
        )
    except Exception as exc:
        logger.exception(f"Erro ao ingerir conhecimento: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "message": "Erro ao ingerir conhecimento no banco vetorial.",
            },
        ) from exc


from app.services.proactive_service import proactive_service

@app.post(
    "/proactive/fechamento",
    summary="Perguntar proativamente sobre Fechamento de Mês",
    tags=["Proativo"],
)
async def checar_fechamento_proativo(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Endpoint invocado pelo n8n ou cron nos finais de tarde para que a SOF.IA pergunte 
    proativamente nos grupos das revendas ativas se haverá Fechamento de Mês hoje.
    """
    is_fim = proactive_service.is_fim_de_mes()
    revendas = await proactive_service.obter_revendas_ativas(db)
    
    mensagens_geradas = []
    for rev in revendas:
        msg = proactive_service.gerar_mensagem_fechamento_mes(rev["nome_revenda"])
        mensagens_geradas.append({
            "id_grupo": rev["id_grupo_wpp"],
            "nome_revenda": rev["nome_revenda"],
            "mensagem_wpp": msg,
            "is_fim_de_mes": is_fim
        })
        
    return {
        "status": "ok",
        "is_fim_de_mes": is_fim,
        "total_revendas": len(mensagens_geradas),
        "mensagens": mensagens_geradas
    }
