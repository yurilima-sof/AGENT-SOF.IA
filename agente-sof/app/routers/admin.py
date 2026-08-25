# =============================================================================
# app/routers/admin.py - Painel Administrativo Dinâmico
# =============================================================================
# Todas as rotas /admin/*. Extraído de app/main.py para não sobrecarregar o
# ponto de entrada principal com a superfície de administração, que cresceu
# bastante (revendas, disparo manual de ações, cenas Tuya, logs, RAG, chat).
#
# `/admin/painel` é a ÚNICA rota deste router sem autenticação: ela serve
# apenas o shell HTML estático (nenhum dado sensível embutido). O JavaScript
# da página pede a Admin API Key uma vez (prompt), guarda em localStorage e a
# usa em todas as chamadas fetch() contra as demais rotas — que continuam
# 100% protegidas por verify_admin_api_key, exatamente como antes.
# =============================================================================

import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.database import get_db
from app.schemas.admin import (
    ToggleRequest,
    DispararAcaoRequest,
    AtualizarMapeamentoRequest,
    CenaUpsertRequest,
)
from app.crud.revendas import (
    buscar_revenda_por_grupo,
    atualizar_mapeamento_revenda,
)
from app.crud.logs import registrar_log, obter_logs_recentes
from app.crud.chat_history import obter_historico_completo
from app.crud.rag import listar_memoria_por_grupo, deletar_memoria
from app.crud.tuya import (
    listar_homes,
    listar_cenas_por_home,
    upsert_cena,
    deletar_cena,
)
from app.services.tuya_service import tuya_service
from app.services.tuya_dispatch_service import disparar_acao_fisica

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "admin_painel.html"


# =============================================================================
# SHELL HTML (público — não expõe dados)
# =============================================================================

@router.get(
    "/painel",
    response_class=HTMLResponse,
    summary="Painel Dinâmico de Controle",
)
async def admin_painel() -> HTMLResponse:
    """
    Serve o shell HTML/JS do painel. Sem autenticação de propósito: a página em
    si não contém nenhum dado, apenas pede a Admin API Key via prompt() e a usa
    em localStorage para autenticar as chamadas às rotas de dados abaixo.
    """
    return HTMLResponse(content=_TEMPLATE_PATH.read_text(encoding="utf-8"))


# =============================================================================
# REVENDAS
# =============================================================================

@router.get("/revendas", summary="Listar Revendas")
async def admin_listar_revendas(
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("SELECT id_grupo_wpp, nome_revenda, estado, tuya_home_id, ativo FROM mapa_revendas ORDER BY nome_revenda")
    )
    rows = result.fetchall()
    return [
        {
            "id_grupo_wpp": r.id_grupo_wpp,
            "nome_revenda": r.nome_revenda,
            "estado": r.estado,
            "tuya_home_id": r.tuya_home_id,
            "ativo": r.ativo,
        }
        for r in rows
    ]


@router.post("/revendas/{id_grupo}/toggle", summary="Ativar/Desativar Revenda")
async def admin_toggle_revenda(
    id_grupo: str,
    payload: ToggleRequest,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("UPDATE mapa_revendas SET ativo = :ativo WHERE id_grupo_wpp = :id_grupo RETURNING id_grupo_wpp"),
        {"ativo": payload.ativo, "id_grupo": id_grupo}
    )
    if not result.fetchone():
        await db.rollback()
        raise HTTPException(status_code=404, detail="Revenda não encontrada")
    await db.commit()
    return {"id_grupo_wpp": id_grupo, "ativo": payload.ativo}


@router.patch("/revendas/{id_grupo}/mapeamento", summary="Atualizar Home ID da Revenda")
async def admin_atualizar_mapeamento(
    id_grupo: str,
    payload: AtualizarMapeamentoRequest,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    ok = await atualizar_mapeamento_revenda(db, id_grupo, payload.tuya_home_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Revenda não encontrada")
    return {"id_grupo_wpp": id_grupo, "tuya_home_id": payload.tuya_home_id}


@router.post("/revendas/{id_grupo}/disparar", summary="Disparar Ação Tuya Manualmente")
async def admin_disparar_acao(
    id_grupo: str,
    payload: DispararAcaoRequest,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Dispara manualmente a mesma ação física que a Sofia dispararia a partir de
    uma mensagem de WhatsApp, usando o mesmo `disparar_acao_fisica` do fluxo
    normal do agente — garante paridade de comportamento com o `/agent`.
    """
    revenda = await buscar_revenda_por_grupo(db, id_grupo)
    if not revenda:
        raise HTTPException(status_code=404, detail="Revenda não encontrada")
    if not revenda["tuya_home_id"]:
        raise HTTPException(
            status_code=422,
            detail="Revenda sem tuya_home_id cadastrado. Configure o mapeamento antes de disparar ações.",
        )

    inicio = time.monotonic()
    try:
        resultado = await disparar_acao_fisica(
            db=db,
            id_grupo=id_grupo,
            nome_revenda=revenda["nome_revenda"],
            home_id=revenda["tuya_home_id"],
            acao=payload.acao,
            ambiente=payload.ambiente,
            duracao_pausa_horas=payload.duracao_horas,
        )
    except Exception as e:
        logger.error(
            f"❌ [Admin] Erro ao disparar ação manual '{payload.acao}' para '{id_grupo}': {e}",
            extra={"status": "erro"}, exc_info=True,
        )
        resultado = {"tuya_success": False, "detail": str(e), "device_offline": False}

    elapsed_ms = int((time.monotonic() - inicio) * 1000)
    await registrar_log(
        db=db,
        id_grupo=id_grupo,
        nome_revenda=revenda["nome_revenda"],
        mensagem_original=f"[admin] disparo manual: {payload.acao}" + (f" ({payload.ambiente})" if payload.ambiente else ""),
        intencao="admin_disparo_manual",
        status_op="sucesso" if resultado.get("tuya_success") else "sem_cena",
        tempo_resposta_ms=elapsed_ms,
        acao_executada=payload.acao,
        ambiente=payload.ambiente,
    )
    return resultado


@router.get("/revendas/{id_grupo}/status", summary="Status Online/Offline dos Dispositivos")
async def admin_status_dispositivos(
    id_grupo: str,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    revenda = await buscar_revenda_por_grupo(db, id_grupo)
    if not revenda:
        raise HTTPException(status_code=404, detail="Revenda não encontrada")
    if not revenda["tuya_home_id"]:
        return {"checked": False, "reason": "sem_tuya_home_id"}
    return await tuya_service.check_home_devices_online(revenda["tuya_home_id"])


@router.get("/revendas/{id_grupo}/historico", summary="Histórico de Chat Recente")
async def admin_historico(
    id_grupo: str,
    limite: int = Query(default=50, ge=1, le=200),
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await obter_historico_completo(db, id_grupo, limite=limite)


@router.get("/revendas/{id_grupo}/memoria", summary="Memória RAG do Grupo")
async def admin_memoria(
    id_grupo: str,
    limite: int = Query(default=50, ge=1, le=200),
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await listar_memoria_por_grupo(db, id_grupo, limite=limite)


@router.delete("/memoria/{doc_id}", summary="Excluir Entrada de Memória RAG")
async def admin_deletar_memoria(
    doc_id: str,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    ok = await deletar_memoria(db, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entrada de memória não encontrada")
    return {"deleted": True, "id": doc_id}


# =============================================================================
# LOGS DE OPERAÇÃO
# =============================================================================

@router.get("/logs", summary="Logs de Operações Recentes")
async def admin_logs(
    limite: int = Query(default=50, ge=1, le=500),
    id_grupo: Optional[str] = None,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await obter_logs_recentes(db, limite=limite, id_grupo=id_grupo)


# =============================================================================
# CENAS E HOMES TUYA
# =============================================================================

@router.get("/tuya/homes", summary="Listar Homes Tuya Cadastradas")
async def admin_listar_homes(
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await listar_homes(db)


@router.get("/tuya/cenas", summary="Listar Cenas de uma Home")
async def admin_listar_cenas(
    home_id: str = Query(...),
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await listar_cenas_por_home(db, home_id)


@router.post("/tuya/cenas", summary="Criar/Atualizar Cena Tuya")
async def admin_upsert_cena(
    payload: CenaUpsertRequest,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await upsert_cena(
        db,
        sigla_cliente=payload.sigla_cliente,
        home_id=payload.home_id,
        ambiente=payload.ambiente,
        scene_id=payload.scene_id,
        nome_cena=payload.nome_cena,
        acao=payload.acao,
    )


@router.delete("/tuya/cenas/{scene_id}", summary="Excluir Cena Tuya")
async def admin_deletar_cena(
    scene_id: str,
    _admin_key: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    ok = await deletar_cena(db, scene_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Cena não encontrada")
    return {"deleted": True, "scene_id": scene_id}
