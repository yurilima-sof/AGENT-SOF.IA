# =============================================================================
# app/domain/policy/escalation.py - Regra Única de Escalonamento de Temperatura
# =============================================================================

from typing import Tuple, Optional
from app.domain.policy.keyword_fallback import FamiliaIntencao

def determinar_acao_e_intencao(
    familia: FamiliaIntencao, 
    chamados_recentes: int = 0
) -> Tuple[Optional[str], Optional[str], str]:
    """
    Única função no sistema autorizada a definir o nível físico de acionamento (medio / freezer / esquentar / off).
    
    Retorna: (ifttt_action, intencao, mensagem_wpp_sugerida)
    """
    if familia == FamiliaIntencao.RESFRIAMENTO:
        if chamados_recentes == 0:
            return (
                "medio",
                "ligar_temperatura_media",
                "Entendido! 🌡️ Iniciando climatização em temperatura média (T-Medium). Se continuar quente nos próximos minutos, me avise!"
            )
        else:
            # L2: só existem dois níveis físicos hoje (medio / freezer) — a partir da 2ª
            # chamada a ação é sempre "freezer". A mensagem não promete um 3º nível
            # intermediário que não existe como ação distinta na Tuya.
            return (
                "freezer",
                "ligar_resfriamento",
                "Entendido! ❄️ Ativando resfriamento no modo máximo (T-Freezer)."
            )

    elif familia == FamiliaIntencao.TEMPERATURA_MEDIA:
        return (
            "medio", 
            "ligar_temperatura_media", 
            "Entendido! 🌡️ Ajustando para temperatura média (T-Medium)."
        )

    elif familia == FamiliaIntencao.AQUECIMENTO:
        return (
            "esquentar", 
            "ligar_aquecimento", 
            "Entendido! 🔥 Ativando aquecimento do ambiente (T-High)."
        )

    elif familia == FamiliaIntencao.DESLIGAR:
        return (
            "off", 
            "desligar_dispositivos", 
            "Entendido! 🌙 Desligando os equipamentos de climatização."
        )

    elif familia == FamiliaIntencao.LIGAR:
        return (
            "ligar", 
            "ligar_dispositivos", 
            "Entendido! ⚡ Ligando os equipamentos."
        )

    elif familia == FamiliaIntencao.PAUSAR_AUTOMACAO:
        return (
            "desativar_automacao", 
            "pausar_automacao", 
            "Compreendido! 🕒 Já pausei as automações de desligamento para sua reunião. Ao final do horário estendido, cuidarei da reativação e desligamento para você! 😊"
        )

    return (None, "sem_acao", "Olá! Como posso te ajudar com a temperatura do ambiente hoje?")
