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
import time
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status, Body
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.config import get_settings
from app.core.security import verify_api_key, verify_admin_api_key
from app.database import async_session_maker
from app.schemas.agent import AgentRequest, AgentResponse, ErrorResponse
from app.schemas.rag import RagIngestRequest, RagIngestResponse
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service
from app.services.tuya_dispatch_service import disparar_acao_fisica
from app.routers.admin import router as admin_router

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

if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        environment=settings.app_env
    )
    logger.info("✅ Sentry SDK inicializado.")


# =============================================================================
# SEGURANÇA: AUTENTICAÇÃO VIA API KEY
# =============================================================================
# `verify_api_key` e `verify_admin_api_key` moraram em app/core/security.py
# (compartilhadas com app/routers/admin.py, evitando import circular).
# O n8n deve enviar no header: Authorization: Bearer <API_KEY>
# =============================================================================


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
from app.crud.revendas import buscar_credenciais_revenda, verificar_revenda_ativa, resolver_home_id_por_grupo
from app.crud.logs import registrar_log
from app.crud.chat_history import salvar_mensagem_historico, obter_historico_recente
from app.services.tuya_service import tuya_service

async def buscar_link_ifttt(credenciais: dict, acao: str, ambiente: Optional[str] = None) -> Optional[str]:
    """
    Busca a URL IFTTT dentro das credenciais_tuya da revenda.
    Se 'ambiente' for fornecido, tenta buscar a chave 'acao_ambiente'.
    Se não encontrar, ou se não houver ambiente, busca a chave 'acao'.
    """
    if not credenciais:
        return None
        
    link_encontrado = None
    
    if ambiente:
        chave_ambiente = f"{acao}_{ambiente}"
        if chave_ambiente in credenciais:
            logger.info(f"   Link IFTTT específico encontrado para ambiente: '{chave_ambiente}'")
            link_encontrado = credenciais[chave_ambiente]
        else:
            logger.info(f"   Link IFTTT para '{chave_ambiente}' não encontrado. Tentando fallback para geral.")
        
    if not link_encontrado and acao in credenciais:
        logger.info(f"   Link IFTTT geral encontrado para '{acao}'")
        link_encontrado = credenciais[acao]
        
    if link_encontrado:
        if "SUA_CHAVE" in link_encontrado:
            logger.warning(f"🚨 AVISO: Link IFTTT para '{acao}' contém placeholder 'SUA_CHAVE'. Cadastro inválido! Ignorando fallback IFTTT.")
            return None
        return link_encontrado

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

    # Auto-Migration: Garante tabelas e colunas necessárias no banco ao iniciar a aplicação
    try:
        from app.database import async_session_maker
        from app.crud.chat_history import inicializar_tabela_historico
        from app.crud.revendas import inicializar_colunas_revendas
        from app.crud.agendamentos import inicializar_tabela_agendamentos
        async with async_session_maker() as session:
            await inicializar_tabela_historico(session)
            await inicializar_colunas_revendas(session)
            await inicializar_tabela_agendamentos(session)
            logger.info("✅ Estrutura do banco de dados (tabelas e colunas) verificada/inicializada com sucesso.")
            
        from app.services.scheduler_service import scheduler_service
        await scheduler_service.carregar_agendamentos_pendentes()
    except Exception as e:
        logger.error(f"⚠️ Aviso no startup ao checar estrutura do banco ou agendamentos: {e}", extra={"status": "erro"}, exc_info=True)

    yield

    logger.info("🛑 Encerrando a aplicação...")
    try:
        from app.services.tuya_service import tuya_service
        await tuya_service.close()
        logger.info("✅ Conexões Tuya (httpx) encerradas.")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao encerrar tuya_service: {e}")


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

    # Painel administrativo dinâmico (/admin/*) — ver app/routers/admin.py
    app_instance.include_router(admin_router)

    from fastapi.responses import JSONResponse

    @app_instance.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        logger.warning(f"⚠️ Rate limit excedido para IP: {request.client.host}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": {
                    "error": "rate_limit_exceeded",
                    "message": "Muitas requisições. Aguarde um momento e tente novamente.",
                }
            },
        )

    # CORS: middleware removido (S5). O único consumidor é o n8n, servidor-a-servidor,
    # sem navegador no fluxo — CORS aberto não protege nada aqui, só amplia superfície.

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
        # Busca o histórico recente de conversas dos últimos 15 minutos (ANTERIOR à mensagem atual)
        historico_recente = await obter_historico_recente(db, payload.id_grupo, limite=6, minutos=15)

        # Grava a mensagem recebida do usuário na memória de curto prazo
        await salvar_mensagem_historico(db, payload.id_grupo, "usuario", payload.mensagem)

        # -----------------------------------------------------------------
        # PASSO 1: Identificar a ação e intenção (LLM com RAG ou Fallback)
        # -----------------------------------------------------------------
        # Verifica se a revenda está ativa
        is_ativa = await verificar_revenda_ativa(db, payload.id_grupo)
        if not is_ativa:
            logger.info(f"   Revenda {payload.id_grupo} está INATIVA. Ignorando processamento de IA/Tuya.")
            return AgentResponse(
                intencao="sem_acao",
                ambiente=None,
                dispositivo_id=None,
                ifttt_action=None,
                parametros={},
                mensagem_wpp=None,
            )

        # Pré-inicializa variáveis de ação e busca credenciais do grupo no banco
        credenciais = await buscar_credenciais_revenda(db, payload.id_grupo)
        acao = None
        intencao = None
        ambiente = None
        mensagem_wpp = None

        if settings.gemini_api_key:
            try:
                logger.info("   [Banco] Buscando ambientes cadastrados para a revenda...")
                
                # NOVO FLUXO: Busca ambientes cadastrados diretamente das Cenas Tuya
                from app.crud.tuya import get_ambientes_by_cliente
                ambientes_disponiveis = await get_ambientes_by_cliente(db, payload.nome_revenda)
                
                # Fallback: se não tiver ambientes na Tuya, tenta extrair das credenciais antigas
                if not ambientes_disponiveis and credenciais:
                    for chave in credenciais.keys():
                        if "_" in chave and chave.split("_", 1)[1] not in ambientes_disponiveis:
                            ambientes_disponiveis.append(chave.split("_", 1)[1])

                logger.info(f"   [LLM] Processando mensagem com Google {settings.gemini_model}...")
                resultado = await llm_service.processar_mensagem(
                    payload.mensagem, 
                    payload.id_grupo, 
                    ambientes_disponiveis,
                    historico_recente
                )
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
                        logger.error(f"⚠️ Falha ao auto-salvar memória orgânica: {e_rag}", extra={"status": "erro"}, exc_info=True)

                # Normalização de nulos vindos da resposta JSON do LLM
                if acao == "null" or acao == "None" or not acao:
                    acao = None
            except Exception as e:
                logger.error(f"⚠️ Falha no processamento com LLM/Gemini (aplicando Fallback): {e}", extra={"status": "erro"}, exc_info=True)
                acao = None
                intencao = None
                ambiente = None
                mensagem_wpp = None

        # Fallback de Palavras-Chave (Keyword Matching) - Executado APENAS se a IA falhar totalmente (intencao is None)
        if not intencao:
            logger.info("   [Fallback] Identificando ação via Keyword Matching e Políticas de Domínio...")
            from app.domain.policy.keyword_fallback import classificar_familia
            from app.domain.policy.escalation import determinar_acao_e_intencao

            familia_fallback = classificar_familia(payload.mensagem)
            if familia_fallback:
                acao, intencao, mensagem_wpp = determinar_acao_e_intencao(familia_fallback, chamados_recentes=0)

        # -----------------------------------------------------------------
        # PASSO 2: Montar a resposta com base na ação identificada
        # -----------------------------------------------------------------
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if acao:
            # 1. TENTA EXECUTAR NATIVAMENTE NA TUYA
            tuya_success = None
            try:
                # RESOLUÇÃO MULTI-TENANT SEGURA (U-07): Resolve home_id via id_grupo_wpp
                home_id = await resolver_home_id_por_grupo(db, payload.id_grupo, payload.nome_revenda)
                if home_id:
                    # Se for pedido de pausa de automação, tenta extrair o horário de término da mensagem
                    horario_fim_pausa = None
                    if acao == "desativar_automacao" or intencao == "pausar_automacao":
                        from app.domain.policy.time_parser import extrair_horario_termino
                        from zoneinfo import ZoneInfo
                        from datetime import datetime

                        agora_recife = datetime.now(ZoneInfo("America/Recife"))
                        horario_fim_pausa = extrair_horario_termino(payload.mensagem, agora=agora_recife)
                        # Sem horário explícito na mensagem: disparar_acao_fisica aplica o fallback de +2h
                        # (decisão explícita (a): não interromper o fluxo com perguntas ao usuário agora).

                    # DISPARO FÍSICO: mesma função usada pelo disparo manual do painel admin
                    # (app/routers/admin.py), garantindo paridade de comportamento entre os dois.
                    resultado_disparo = await disparar_acao_fisica(
                        db=db,
                        id_grupo=payload.id_grupo,
                        nome_revenda=payload.nome_revenda,
                        home_id=home_id,
                        acao=acao,
                        intencao=intencao,
                        ambiente=ambiente,
                        horario_fim_pausa=horario_fim_pausa,
                    )

                    if resultado_disparo.get("device_offline"):
                        elapsed_ms = int((time.monotonic() - start_time) * 1000)
                        logger.warning(f"🔌 Dispositivos da revenda '{payload.nome_revenda}' (Home {home_id}) estão OFFLINE. Abortando comando.")

                        msg_offline = (
                            "Ops! Verifiquei aqui e os dispositivos da revenda estão offline no momento. 🔌 "
                            "Por favor, verifique a conexão com a internet/energia e tente novamente em alguns minutos!"
                        )

                        await registrar_log(
                            db=db,
                            id_grupo=payload.id_grupo,
                            nome_revenda=payload.nome_revenda,
                            mensagem_original=payload.mensagem,
                            intencao=intencao,
                            status_op="dispositivo_offline",
                            tempo_resposta_ms=elapsed_ms,
                            acao_executada=acao,
                            ambiente=ambiente
                        )

                        return AgentResponse(
                            intencao=intencao,
                            ambiente=ambiente,
                            dispositivo_id=None,
                            ifttt_action=None,      # Cancela o disparo do IFTTT
                            link_ifttt=None,        # Cancela o webhook
                            tuya_success=False,
                            parametros={},
                            mensagem_wpp=msg_offline,
                        )

                    tuya_success = resultado_disparo.get("tuya_success")
                else:
                    logger.info(f"   [Tuya] Revenda '{payload.nome_revenda}' não encontrada na base Tuya.")
            except Exception as e_tuya:
                logger.error(f"   [Tuya] Erro ao tentar disparar cena: {e_tuya}", extra={"status": "erro"}, exc_info=True)
                tuya_success = False

            # 2. BUSCA O IFTTT COMO PLANO B (Fallback)
            link_ifttt = await buscar_link_ifttt(credenciais, acao, ambiente)

            if tuya_success in (None, False) and not link_ifttt:
                logger.warning(f"⚠️ Ação '{acao}' solicitada no ambiente '{ambiente or 'geral'}', mas NENHUMA cena Tuya ou link IFTTT foi encontrado. Avisando usuário.")
                mensagem_wpp = (
                    f"Desculpe, eu entendi que você quer executar a ação '{acao}' no ambiente '{ambiente or 'geral'}', "
                    "mas ainda não tenho essa configuração cadastrada para esta revenda. "
                    "Por favor, solicite o cadastro dessa cena/ação à equipe técnica."
                )
                acao = None # Cancela a intenção de disparar algo que não existe

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
                status_op="sucesso" if (tuya_success or link_ifttt) else "sem_cena",
                tempo_resposta_ms=elapsed_ms,
                acao_executada=acao,
                ambiente=ambiente
            )

            resp_wpp_final = mensagem_wpp
            if resp_wpp_final:
                await salvar_mensagem_historico(db, payload.id_grupo, "sofia", resp_wpp_final)

            return AgentResponse(
                intencao=intencao,
                ambiente=ambiente,
                dispositivo_id=None,
                ifttt_action=acao,
                link_ifttt=link_ifttt,
                tuya_success=tuya_success,
                parametros={},
                mensagem_wpp=resp_wpp_final,
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

            resp_wpp_final = mensagem_wpp or "Olá! Como posso te ajudar com a temperatura do ambiente hoje?"
            await salvar_mensagem_historico(db, payload.id_grupo, "sofia", resp_wpp_final)

            return AgentResponse(
                intencao=intencao or "sem_acao",
                ambiente=ambiente if 'ambiente' in locals() else None,
                dispositivo_id=None,
                ifttt_action=None,         # ← n8n NÃO dispara o IFTTT
                parametros={},
                mensagem_wpp=resp_wpp_final,
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

        logger.exception(f"❌ Erro ao processar requisição: {exc}", extra={"status": "erro"})
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
        logger.exception(f"Erro ao ingerir conhecimento: {exc}", extra={"status": "erro"})
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

# =============================================================================
# ADMIN
# =============================================================================
# Todas as rotas /admin/* (incluindo o painel dinâmico) vivem em
# app/routers/admin.py e são registradas via app_instance.include_router()
# em create_app(), acima.
