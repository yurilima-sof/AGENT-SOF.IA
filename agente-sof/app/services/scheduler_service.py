import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from zoneinfo import ZoneInfo

from app.services.tuya_service import tuya_service

logger = logging.getLogger(__name__)

RECIFE_TZ = ZoneInfo("America/Recife")

class SchedulerService:
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}

    async def _run_task(self, id_grupo: str, nome_revenda: str, home_id: str, automacao_ids: List[str], delay_segundos: float, task_key: str, agendamento_id: Optional[str] = None, fase: str = "resume"):
        try:
            await asyncio.sleep(delay_segundos)
            
            if fase == "pause":
                logger.info(f"⏰ [Scheduler] Horário de INÍCIO da pausa atingido para {nome_revenda}!")
                for auto_id in automacao_ids:
                    try:
                        await tuya_service.set_automation_status(home_id, auto_id, enable=False)
                        logger.info(f"⏸️ Automação {auto_id} desativada para {nome_revenda}.")
                    except Exception as e_auto:
                        logger.error(f"❌ Erro ao desativar {auto_id}: {e_auto}")
                
            elif fase == "resume":
                logger.info(f"⏰ [Scheduler] Horário de encerramento da reunião atingido para {nome_revenda}!")
                for auto_id in automacao_ids:
                    try:
                        await tuya_service.set_automation_status(home_id, auto_id, enable=True)
                        logger.info(f"✅ Automação {auto_id} reativada para {nome_revenda}.")
                    except Exception as e_auto:
                        logger.error(f"❌ Erro ao reativar automação {auto_id}: {e_auto}")

                try:
                    from app.database import async_session_maker
                    from app.crud.tuya import get_scene_by_ambiente
                    async with async_session_maker() as db:
                        scene_off = await get_scene_by_ambiente(db, home_id, "", "off")
                        if scene_off and "scene_id" in scene_off:
                            logger.info(f"🌙 [Scheduler] Executando desligamento final (T-OFF) pós-reunião para {nome_revenda}...")
                            await tuya_service.execute_scene(home_id, scene_off["scene_id"])
                except Exception as e_off:
                    logger.error(f"⚠️ Erro ao disparar desligamento: {e_off}")
                    
            if agendamento_id:
                from app.database import async_session_maker
                from app.crud.agendamentos import marcar_agendamento_executado
                async with async_session_maker() as db:
                    await marcar_agendamento_executado(db, agendamento_id)

        except asyncio.CancelledError:
            logger.info(f"ℹ️ Agendamento cancelado para {nome_revenda}.")
        except Exception as e:
            logger.error(f"❌ Erro na tarefa agendada: {e}")
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
        agora = datetime.now(RECIFE_TZ)
        delay_segundos = (horario_execucao - agora).total_seconds()
        delay_segundos += 120
        if delay_segundos < 0:
            delay_segundos = 10

        task_key = f"{id_grupo}_{home_id}_resume_imediata"
        if task_key in self._tasks and not self._tasks[task_key].done():
            self._tasks[task_key].cancel()

        from app.crud.agendamentos import salvar_agendamento
        from app.database import async_session_maker
        async with async_session_maker() as db:
            agendamento_id = await salvar_agendamento(db, id_grupo, nome_revenda, home_id, automacao_ids, horario_execucao)

        self._tasks[task_key] = asyncio.create_task(
            self._run_task(id_grupo, nome_revenda, home_id, automacao_ids, delay_segundos, task_key, agendamento_id, "resume")
        )

    async def carregar_agendamentos_pendentes(self):
        from app.database import async_session_maker
        from app.crud.agendamentos import obter_agendamentos_pendentes
        
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
                # row[6] is fase, if it exists
                fase = row[6] if len(row) > 6 and row[6] else "resume"
                
                if horario_execucao.tzinfo is None:
                    horario_execucao = horario_execucao.replace(tzinfo=RECIFE_TZ)
                
                delay_segundos = (horario_execucao - agora).total_seconds()
                
                if delay_segundos < -300: 
                    delay_segundos = 5
                elif delay_segundos < 0:
                    delay_segundos = 10
                    
                task_key = f"{id_grupo_wpp}_{home_id}_{agendamento_id}"
                # Guard de idempotência (Bug 3): não empilhar tasks se já existe uma viva
                if task_key in self._tasks and not self._tasks[task_key].done():
                    logger.info(f"♻️ [Scheduler] Task já viva para {task_key}, pulando.")
                    continue
                self._tasks[task_key] = asyncio.create_task(
                    self._run_task(id_grupo_wpp, nome_revenda, home_id, automacao_ids, delay_segundos, task_key, agendamento_id, fase)
                )

    async def cancelar_reativacao_pendente(self, id_grupo: str, home_id: str) -> bool:
        from app.database import async_session_maker
        from app.crud.agendamentos import obter_agendamentos_pendentes, marcar_agendamento_executado

        cancelou_algo = False
        
        to_cancel = [k for k in self._tasks.keys() if k.startswith(f"{id_grupo}_{home_id}")]
        for task_key in to_cancel:
            if not self._tasks[task_key].done():
                self._tasks[task_key].cancel()
                cancelou_algo = True

        async with async_session_maker() as db:
            pendentes = await obter_agendamentos_pendentes(db)
            for row in pendentes:
                agendamento_id, id_grupo_wpp, _nome_revenda, h_id = row[0], row[1], row[2], row[3]
                if id_grupo_wpp == id_grupo and h_id == home_id:
                    await marcar_agendamento_executado(db, str(agendamento_id))
                    cancelou_algo = True

        return cancelou_algo

    async def _tick_manual_para_testes(self):
        """Alias para carregar_agendamentos_pendentes (usado nos testes de T5)."""
        await self.carregar_agendamentos_pendentes()

scheduler_service = SchedulerService()
