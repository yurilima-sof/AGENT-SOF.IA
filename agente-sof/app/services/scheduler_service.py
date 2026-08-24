import asyncio
import logging
import json
from datetime import datetime, timedelta
import re
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

from app.services.tuya_service import tuya_service

logger = logging.getLogger(__name__)

RECIFE_TZ = ZoneInfo("America/Recife")

class SchedulerService:
    """
    Serviço para agendamento de tarefas em segundo plano (Background Tasks).
    Gerencia a reativação automática de automações da Tuya e desligamentos programados
    após reuniões prolongadas ou fechamento de mês, no fuso horário de Recife (America/Recife).
    """

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}

    async def _run_task(self, id_grupo: str, nome_revenda: str, home_id: str, automacao_ids: List[str], delay_segundos: float, task_key: str, agendamento_id: Optional[str] = None):
        try:
            await asyncio.sleep(delay_segundos)
            logger.info(f"⏰ [Scheduler] Horário de encerramento da reunião atingido para {nome_revenda}!")
            
            # 1. Reativa as automações na Tuya Cloud para que a rotina normal volte a funcionar
            for auto_id in automacao_ids:
                try:
                    await tuya_service.set_automation_status(home_id, auto_id, enable=True)
                    logger.info(f"✅ Automação {auto_id} reativada com sucesso para {nome_revenda}.")
                except Exception as e_auto:
                    logger.error(f"❌ Erro ao reativar automação {auto_id}: {e_auto}", extra={"status": "erro"}, exc_info=True)

            # 2. Executa a cena de desligamento final (T-OFF) para desligar os aparelhos da reunião
            try:
                from app.database import async_session_maker
                from app.crud.tuya import get_scene_by_ambiente
                async with async_session_maker() as db:
                    scene_off = await get_scene_by_ambiente(db, home_id, "", "off")
                    if scene_off and "scene_id" in scene_off:
                        logger.info(f"🌙 [Scheduler] Executando desligamento final (T-OFF) pós-reunião para {nome_revenda}...")
                        await tuya_service.execute_scene(home_id, scene_off["scene_id"])
                    
                    if agendamento_id:
                        from app.crud.agendamentos import marcar_agendamento_executado
                        await marcar_agendamento_executado(db, agendamento_id)
            except Exception as e_off:
                logger.error(f"⚠️ Erro ao disparar desligamento final ou marcar executado: {e_off}", extra={"status": "erro"}, exc_info=True)

            logger.info(f"🎉 [Scheduler] Ciclo de reunião concluído e equipamentos desligados para {nome_revenda}.")
        except asyncio.CancelledError:
            logger.info(f"ℹ️ Agendamento cancelado para {nome_revenda}.")
        except Exception as e:
            logger.error(f"❌ Erro na tarefa agendada: {e}", extra={"status": "erro"}, exc_info=True)
        finally:
            if task_key in self._tasks:
                del self._tasks[task_key]

    async def agendar_reativacao_automacao(
        self,
        id_grupo: str,
        nome_revenda: str,
        home_id: str,
        automacao_ids: List[str],
        horario_execucao: datetime
    ):
        """
        Agenda em segundo plano a reativação das automações e o desligamento final dos aparelhos no fuso de Recife.
        """
        agora = datetime.now(RECIFE_TZ)
        delay_segundos = (horario_execucao - agora).total_seconds()
        
        # Adiciona uma margem de segurança de 2 minutos após o término da reunião
        delay_segundos += 120
        if delay_segundos < 0:
            delay_segundos = 10

        task_key = f"{id_grupo}_{home_id}"
        
        # Se já houver uma agendada para o mesmo grupo, cancela a anterior e reagenda
        if task_key in self._tasks and not self._tasks[task_key].done():
            logger.info(f"⏳ Reagendando tarefa de reativação para o grupo {id_grupo}...")
            self._tasks[task_key].cancel()

        logger.info(
            f"📅 [Scheduler] Agendada reativação/desligamento para '{nome_revenda}' | "
            f"Horário Recife: {horario_execucao.strftime('%H:%M:%S')} (execução em {int(delay_segundos/60)} minutos)"
        )

        from app.crud.agendamentos import salvar_agendamento
        from app.database import async_session_maker
        async with async_session_maker() as db:
            agendamento_id = await salvar_agendamento(db, id_grupo, nome_revenda, home_id, automacao_ids, horario_execucao)

        # Inicia a task em background no evento do loop asyncio
        self._tasks[task_key] = asyncio.create_task(self._run_task(id_grupo, nome_revenda, home_id, automacao_ids, delay_segundos, task_key, agendamento_id))

    async def carregar_agendamentos_pendentes(self):
        """
        Carrega agendamentos não executados do banco de dados no boot da aplicação.
        """
        from app.database import async_session_maker
        from app.crud.agendamentos import obter_agendamentos_pendentes, marcar_agendamento_executado
        import json
        
        agora = datetime.now(RECIFE_TZ)
        logger.info("♻️ [Scheduler] Buscando agendamentos pendentes...")
        
        async with async_session_maker() as db:
            pendentes = await obter_agendamentos_pendentes(db)
            for row in pendentes:
                agendamento_id = str(row[0])
                id_grupo_wpp = row[1]
                nome_revenda = row[2]
                home_id = row[3]
                automacao_ids = row[4]
                horario_execucao = row[5]
                
                # Certifica que o fuso horário está correto
                if horario_execucao.tzinfo is None:
                    horario_execucao = horario_execucao.replace(tzinfo=RECIFE_TZ)
                
                delay_segundos = (horario_execucao - agora).total_seconds()
                delay_segundos += 120 # Margem original
                
                if delay_segundos < -300: # Se já passou de 5 minutos do horário, executa agora com um pequeno delay
                    delay_segundos = 5
                elif delay_segundos < 0:
                    delay_segundos = 10
                    
                task_key = f"{id_grupo_wpp}_{home_id}"
                logger.info(f"♻️ [Scheduler] Reagendando {task_key} para execução em {int(delay_segundos)}s")
                self._tasks[task_key] = asyncio.create_task(
                    self._run_task(id_grupo_wpp, nome_revenda, home_id, automacao_ids, delay_segundos, task_key, agendamento_id)
                )

scheduler_service = SchedulerService()
