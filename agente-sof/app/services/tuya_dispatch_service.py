# =============================================================================
# app/services/tuya_dispatch_service.py - Disparo Físico de Ações Tuya
# =============================================================================
# Extrai o "o que fazer fisicamente numa Home já resolvida" (checar online,
# pausar automação, ou disparar uma cena) para um único lugar. É usado por
# dois chamadores: o fluxo normal do WhatsApp (app/main.py:process_agent_command,
# via LLM ou fallback de palavras-chave) e o disparo manual do painel admin
# (app/routers/admin.py). Ambos precisam do MESMO comportamento de disparo —
# daí a extração, em vez de duas implementações que podem divergir com o tempo.
# =============================================================================

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tuya_service import tuya_service
from app.crud.tuya import get_scene_by_ambiente

logger = logging.getLogger(__name__)

RECIFE_TZ = ZoneInfo("America/Recife")


async def disparar_acao_fisica(
    db: AsyncSession,
    id_grupo: str,
    nome_revenda: str,
    home_id: str,
    acao: Optional[str],
    intencao: Optional[str] = None,
    ambiente: Optional[str] = None,
    horario_fim_pausa: Optional[datetime] = None,
    duracao_pausa_horas: float = 2.0,
) -> dict:
    """
    Dispara fisicamente uma ação Tuya (cena ou pausa de automação) numa Home já
    resolvida (`home_id`). Não decide IFTTT fallback nem grava logs de auditoria
    — isso continua responsabilidade de quem chama, que tem o contexto completo
    da requisição (mensagem original, credenciais IFTTT, etc.).

    Retorna:
        {
            "tuya_success": bool | None,  # None = nenhuma cena/automação encontrada
            "detail": str,                 # descrição legível do resultado
            "device_offline": bool,        # True = dispositivos IR offline, comando abortado
        }
    """
    # VERIFICAÇÃO PRÉVIA: Checa se os dispositivos IR da revenda estão online
    device_status = await tuya_service.check_home_devices_online(home_id)
    if device_status.get("all_offline") is True:
        logger.warning(f"🔌 Dispositivos da revenda '{nome_revenda}' (Home {home_id}) estão OFFLINE. Abortando comando.")
        return {"tuya_success": False, "detail": "dispositivos_offline", "device_offline": True}

    if acao == "desativar_automacao" or intencao == "pausar_automacao":
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
        tuya_success = len(desativadas_ids) > 0

        if desativadas_ids:
            # Import tardio para evitar dependência circular no boot do módulo
            from app.services.scheduler_service import scheduler_service

            horario_fim = horario_fim_pausa
            if horario_fim is None:
                horario_fim = datetime.now(RECIFE_TZ) + timedelta(hours=duracao_pausa_horas)

            await scheduler_service.agendar_reativacao_automacao(
                id_grupo=id_grupo,
                nome_revenda=nome_revenda,
                home_id=home_id,
                automacao_ids=desativadas_ids,
                horario_execucao=horario_fim,
            )
            detail = f"{len(desativadas_ids)} automação(ões) pausada(s) até {horario_fim.strftime('%H:%M')} ({horario_fim.tzinfo})"
        else:
            detail = "nenhuma automação ativa encontrada para pausar"

        return {"tuya_success": tuya_success, "detail": detail, "device_offline": False}

    # Ação normal: resolve e dispara a cena correspondente ao ambiente/ação
    amb = ambiente if ambiente else ""
    scene_data = await get_scene_by_ambiente(db, home_id, amb, acao)
    if scene_data:
        scene_id = scene_data["scene_id"]
        logger.info(f"   [Tuya] Cenário encontrado: {scene_data['nome_cena']} (ID: {scene_id}). Disparando...")
        tuya_success = await tuya_service.execute_scene(home_id, scene_id)
        return {"tuya_success": tuya_success, "detail": scene_data["nome_cena"], "device_offline": False}

    logger.info(f"   [Tuya] Nenhuma cena encontrada para ambiente '{amb}' e ação '{acao}'.")
    return {"tuya_success": None, "detail": "nenhuma cena encontrada", "device_offline": False}
