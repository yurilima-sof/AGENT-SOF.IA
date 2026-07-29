import asyncio
import logging
from datetime import datetime, timedelta
import re
from typing import Optional, List, Dict, Any

from app.services.tuya_service import tuya_service

logger = logging.getLogger(__name__)

class SchedulerService:
    """
    Serviço para agendamento de tarefas em segundo plano (Background Tasks).
    Gerencia a reativação automática de automações da Tuya e desligamentos programados
    após reuniões prolongadas ou fechamento de mês, sem necessidade de intervenção humana.
    """

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}

    def extrair_horario_termino(self, mensagem: str) -> Optional[datetime]:
        """
        Extrai o horário de término mencionado na mensagem (ex: 'até as 20h', 'até 21:30', 'até 22 horas').
        Retorna um objeto datetime relativo à data atual.
        """
        agora = datetime.now()
        
        # Procura padrões como "20h", "20:30", "20 horas", "20:00"
        match = re.search(r'(\d{1,2})(?:[:h](\d{2}))?\s*(?:h|horas)?', mensagem.lower())
        if match:
            hora = int(match.group(1))
            minuto = int(match.group(2)) if match.group(2) else 0
            
            if 0 <= hora <= 23 and 0 <= minuto <= 59:
                data_alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                # Se a hora já passou hoje (ex: fala 8h da noite às 19h -> 20h), considera hoje.
                # Se for uma hora menor que agora (ex: fala 1h da manhã), considera o próximo dia.
                if data_alvo < agora:
                    data_alvo += timedelta(days=1)
                return data_alvo
                
        # Fallback: Se não especificar a hora, assume 2 horas a partir de agora
        return agora + timedelta(hours=2)

    async def agendar_reativacao_automacao(
        self,
        id_grupo: str,
        nome_revenda: str,
        home_id: str,
        automacao_ids: List[str],
        horario_execucao: datetime
    ):
        """
        Agenda em segundo plano a reativação das automações e o encerramento no horário especificado.
        """
        agora = datetime.now()
        delay_segundos = (horario_execucao - agora).total_seconds()
        
        # Adiciona uma margem de segurança de 5 minutos após o horário da reunião
        delay_segundos += 300
        if delay_segundos < 0:
            delay_segundos = 10

        task_key = f"{id_grupo}_{home_id}"
        
        # Se já houver uma agendada para o mesmo grupo, cancela a anterior e reagenda
        if task_key in self._tasks and not self._tasks[task_key].done():
            logger.info(f"⏳ Reagendando tarefa de reativação para o grupo {id_grupo}...")
            self._tasks[task_key].cancel()

        logger.info(
            f"📅 [Scheduler] Agendada reativação automática da Tuya para '{nome_revenda}' | "
            f"Horário: {horario_execucao.strftime('%H:%M:%S')} (execução em {int(delay_segundos/60)} minutos)"
        )

        async def _run_task():
            try:
                await asyncio.sleep(delay_segundos)
                logger.info(f"⏰ [Scheduler] Horário atingido! Reativando automações da Tuya para {nome_revenda}...")
                
                for auto_id in automacao_ids:
                    try:
                        await tuya_service.set_automation_status(home_id, auto_id, enable=True)
                        logger.info(f"✅ Automação {auto_id} reativada com sucesso para {nome_revenda}.")
                    except Exception as e_auto:
                        logger.error(f"❌ Erro ao reativar automação {auto_id}: {e_auto}")

                logger.info(f"🎉 [Scheduler] Ciclo de exceção temporária concluído para {nome_revenda}.")
            except asyncio.CancelledError:
                logger.info(f"ℹ️ Agendamento cancelado para {nome_revenda}.")
            except Exception as e:
                logger.error(f"❌ Erro na tarefa agendada: {e}")

        # Inicia a task em background no evento do loop asyncio
        self._tasks[task_key] = asyncio.create_task(_run_task())

scheduler_service = SchedulerService()
