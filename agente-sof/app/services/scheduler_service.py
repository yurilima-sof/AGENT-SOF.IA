# =============================================================================
# app/services/scheduler_service.py - Agendamento de Pausa/Reativação de Automações
# =============================================================================
# O estado autoritativo vive na tabela `agendamentos`; o que existe aqui são
# apenas asyncio.Tasks dormindo até a hora de agir, reconstruídas a partir do
# banco no startup e a cada /scheduler/tick. Qualquer task perdida (restart,
# deploy, crash) é recuperada do banco — mas só se ainda fizer sentido executar,
# ver `carregar_agendamentos_pendentes`.
# =============================================================================

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from app.services.tuya_service import tuya_service

logger = logging.getLogger(__name__)

RECIFE_TZ = ZoneInfo("America/Recife")

# Folga entre o horário informado pela loja e a reativação das automações de OFF.
# A automação de desligamento costuma ser agendada na hora cheia (20:00); religar
# exatamente às 20:00 cairia em cima do próprio gatilho. Os 2 minutos deixam o
# gatilho passar antes de a regra voltar a valer.
GRACA_RESUME_SEGUNDOS = 120

# Até quanto tempo depois do horário previsto ainda faz sentido executar um
# agendamento que foi recuperado do banco. Acima disso a janela já passou e
# executar às cegas é que é perigoso — ver `carregar_agendamentos_pendentes`.
TOLERANCIA_ATRASO_SEGUNDOS = 30 * 60

# Horário (America/Recife) da reconciliação noturna — a rede de proteção que
# garante que nenhuma loja passa a noite ligada por causa de um resume perdido.
# 23:50 deixa 10 minutos de margem antes da virada do dia: o suficiente para a
# varredura terminar sem que a data mude no meio dela.
HORA_RECONCILIACAO = time(23, 50)


def _task_key(id_grupo: str, home_id: str, agendamento_id: Optional[str]) -> str:
    """
    Chave única da task, derivada do ID da linha no banco.

    Correção do achado C1: antes havia DOIS formatos de chave para a mesma linha
    — `{grupo}_{home}_resume_imediata` no momento da pausa e
    `{grupo}_{home}_{agendamento_id}` no tick. Como não batiam, o guard de
    idempotência não enxergava a primeira task e o tick seguinte criava uma
    segunda para o mesmo agendamento: o resume rodava duas vezes e a cena de
    desligamento geral disparava em duplicidade.

    O separador é "|" (e não "_") porque id_grupo e home_id podem conter "_":
    com "_" as chaves eram ambíguas e o `startswith` do cancelamento casava
    homes diferentes ("123" casando com "1234").
    """
    return f"{id_grupo}|{home_id}|{agendamento_id}"


class SchedulerService:
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        # Metadados por task viva (grupo, home, data, fase). Permite cancelar com
        # precisão — por grupo + home + DIA — em vez do antigo prefixo de string.
        self._task_meta: Dict[str, dict] = {}
        # Task do laço diário da reconciliação noturna (ver iniciar_reconciliacao_noturna).
        self._reconciliacao_task: Optional[asyncio.Task] = None

    def _registrar_task(self, task_key: str, task: asyncio.Task, meta: dict) -> None:
        self._tasks[task_key] = task
        self._task_meta[task_key] = meta

    def _esquecer_task(self, task_key: str) -> None:
        self._tasks.pop(task_key, None)
        self._task_meta.pop(task_key, None)

    async def _run_task(
        self,
        id_grupo: str,
        nome_revenda: str,
        home_id: str,
        automacao_ids: List[str],
        delay_segundos: float,
        task_key: str,
        agendamento_id: Optional[str] = None,
        fase: str = "resume",
        suprimir_cena_off: bool = False,
    ):
        """
        Dorme até a hora e executa a fase.

        `suprimir_cena_off` existe para o resume que chegou atrasado (recuperado
        do banco depois de um restart): reativar as automações é sempre seguro e
        restaura o comportamento normal da loja, mas disparar a cena de
        desligamento geral num horário arbitrário do expediente não é — foi esse
        o risco apontado no achado C3.
        """
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

                if suprimir_cena_off:
                    logger.warning(
                        f"🌙 [Scheduler] Resume atrasado para {nome_revenda}: automações religadas, "
                        f"mas a cena de desligamento (T-OFF) foi SUPRIMIDA para não desligar a loja fora de hora."
                    )
                else:
                    try:
                        from app.crud.tuya import get_scene_by_ambiente
                        from app.database import async_session_maker
                        async with async_session_maker() as db:
                            scene_off = await get_scene_by_ambiente(db, home_id, "", "off")
                            if scene_off and "scene_id" in scene_off:
                                logger.info(f"🌙 [Scheduler] Executando desligamento final (T-OFF) pós-reunião para {nome_revenda}...")
                                await tuya_service.execute_scene(home_id, scene_off["scene_id"])
                    except Exception as e_off:
                        logger.error(f"⚠️ Erro ao disparar desligamento: {e_off}")

            if agendamento_id:
                from app.crud.agendamentos import marcar_agendamento_executado
                from app.database import async_session_maker
                async with async_session_maker() as db:
                    await marcar_agendamento_executado(db, agendamento_id)

        except asyncio.CancelledError:
            # A linha permanece `executado = FALSE` de propósito: um cancelamento
            # de shutdown precisa ser recuperável no próximo boot. Quem cancela a
            # pedido do usuário (cancelar_reativacao_pendente) encerra a linha no
            # banco explicitamente.
            logger.info(f"ℹ️ Agendamento cancelado para {nome_revenda}.")
        except Exception as e:
            logger.error(f"❌ Erro na tarefa agendada: {e}", extra={"status": "erro"}, exc_info=True)
        finally:
            self._esquecer_task(task_key)

    async def agendar_reativacao_automacao(
        self,
        id_grupo: str,
        nome_revenda: str,
        home_id: str,
        automacao_ids: List[str],
        horario_execucao: datetime
    ):
        """
        Fluxo "hoje": a pausa já foi aplicada, aqui fica agendado o resume.

        `salvar_agendamento` cancela as pendências do mesmo dia antes de inserir
        (achado C2), então uma segunda pausa substitui a primeira no banco. Em
        memória, o equivalente é o `_cancelar_tasks_do_dia` abaixo.
        """
        agora = datetime.now(RECIFE_TZ)
        data_execucao = horario_execucao.date()

        # Cancela as tasks em memória do mesmo grupo/home/dia. Sem isto, o resume
        # antigo (ex.: 20h) continuaria vivo mesmo depois de a loja corrigir para
        # 22h, e desligaria a loja no meio da reunião.
        self._cancelar_tasks_do_dia(id_grupo, home_id, data_execucao)

        from app.crud.agendamentos import salvar_agendamento
        from app.database import async_session_maker
        async with async_session_maker() as db:
            agendamento_id = await salvar_agendamento(db, id_grupo, nome_revenda, home_id, automacao_ids, horario_execucao)

        delay_segundos = (horario_execucao - agora).total_seconds() + GRACA_RESUME_SEGUNDOS
        if delay_segundos < 0:
            delay_segundos = 10

        task_key = _task_key(id_grupo, home_id, agendamento_id)
        self._registrar_task(
            task_key,
            asyncio.create_task(
                self._run_task(id_grupo, nome_revenda, home_id, automacao_ids, delay_segundos, task_key, agendamento_id, "resume")
            ),
            {"id_grupo": id_grupo, "home_id": home_id, "data_execucao": data_execucao, "fase": "resume"},
        )

    def _cancelar_tasks_do_dia(self, id_grupo: str, home_id: str, data_execucao: date) -> int:
        """
        Cancela as tasks vivas de um grupo/home num dia específico.

        Comparação campo a campo via `_task_meta` em vez do antigo
        `k.startswith(f"{id_grupo}_{home_id}")`, que casava homes de prefixo
        comum e, pior, não sabia distinguir o dia (achado A5).
        """
        alvos = [
            k for k, meta in self._task_meta.items()
            if meta.get("id_grupo") == id_grupo
            and meta.get("home_id") == home_id
            and meta.get("data_execucao") == data_execucao
        ]
        cancelados = 0
        for task_key in alvos:
            task = self._tasks.get(task_key)
            if task is not None and not task.done():
                task.cancel()
                cancelados += 1
            self._esquecer_task(task_key)
        return cancelados

    async def carregar_agendamentos_pendentes(self):
        """
        Reconstrói as tasks a partir do banco (startup e /scheduler/tick).

        Correção do achado C3. A versão anterior pegava TODA linha
        `executado = FALSE`, sem recorte de data, e transformava qualquer atraso
        maior que 5 minutos em `delay = 5` — ou seja, a cada restart as linhas de
        dias anteriores disparavam em 5 segundos. Um `resume` velho executava a
        cena de desligamento geral no meio do expediente; um `pause` velho
        desabilitava as automações de OFF no dia errado, que é exatamente a
        classe do incidente de 21/09.

        A regra agora depende da fase, porque os dois erros são assimétricos:

        - `pause` vencido  → descartado. Pausar fora da janela só deixa a loja
          ligada quando não deveria.
        - `resume` vencido → executado assim mesmo, mas SEM a cena de
          desligamento. Deixar de religar as automações é pior: a loja ficaria
          sem desligamento automático indefinidamente.
        """
        from app.crud.agendamentos import marcar_agendamento_executado, obter_agendamentos_pendentes
        from app.database import async_session_maker

        agora = datetime.now(RECIFE_TZ)
        hoje = agora.date()
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
                fase = row[6] if len(row) > 6 and row[6] else "resume"
                data_execucao = row[7] if len(row) > 7 and row[7] else None

                if horario_execucao.tzinfo is None:
                    horario_execucao = horario_execucao.replace(tzinfo=RECIFE_TZ)
                else:
                    # A coluna é TIMESTAMPTZ: o driver devolve em UTC. Converter
                    # para Recife antes de derivar a data evita que um resume das
                    # 22h vire "dia seguinte" só por causa do fuso.
                    horario_execucao = horario_execucao.astimezone(RECIFE_TZ)

                if data_execucao is None:
                    data_execucao = horario_execucao.date()

                atraso_segundos = (agora - horario_execucao).total_seconds()
                vencido = data_execucao < hoje or atraso_segundos > TOLERANCIA_ATRASO_SEGUNDOS

                if vencido and fase == "pause":
                    logger.warning(
                        f"🗑️ [Scheduler] Pause vencido descartado para {nome_revenda} "
                        f"(previsto {horario_execucao.isoformat()}, atraso {int(atraso_segundos)}s). "
                        f"Nenhuma automação será desativada."
                    )
                    await marcar_agendamento_executado(db, agendamento_id)
                    continue

                if vencido:
                    logger.warning(
                        f"⏱️ [Scheduler] Resume vencido para {nome_revenda} "
                        f"(previsto {horario_execucao.isoformat()}, atraso {int(atraso_segundos)}s): "
                        f"religando automações imediatamente, sem cena de desligamento."
                    )
                    delay_segundos = 0.0
                    suprimir_cena_off = True
                else:
                    delay_segundos = max(0.0, -atraso_segundos)
                    suprimir_cena_off = False

                task_key = _task_key(id_grupo_wpp, home_id, agendamento_id)
                # Guard de idempotência: não empilhar tasks se já existe uma viva.
                # Com a chave unificada (_task_key), isto agora também enxerga a
                # task criada por agendar_reativacao_automacao — era o achado C1.
                task_viva = self._tasks.get(task_key)
                if task_viva is not None and not task_viva.done():
                    logger.info(f"♻️ [Scheduler] Task já viva para {task_key}, pulando.")
                    continue

                self._registrar_task(
                    task_key,
                    asyncio.create_task(
                        self._run_task(
                            id_grupo_wpp, nome_revenda, home_id, automacao_ids,
                            delay_segundos, task_key, agendamento_id, fase,
                            suprimir_cena_off,
                        )
                    ),
                    {"id_grupo": id_grupo_wpp, "home_id": home_id, "data_execucao": data_execucao, "fase": fase},
                )

    async def cancelar_reativacao_pendente(
        self,
        id_grupo: str,
        home_id: str,
        data_execucao: Optional[date] = None,
    ) -> bool:
        """
        Cancela a pausa/resume de UM dia (default: hoje) para um grupo/home.

        Usado por "reunião cancelada". O recorte por data é o achado A5: antes o
        cancelamento varria todas as pendências do grupo/home, de modo que
        desmarcar a reunião de hoje apagava junto o evento já agendado para o
        próximo sábado, sem nenhum aviso.
        """
        from app.crud.agendamentos import cancelar_pendentes_do_dia
        from app.database import async_session_maker

        if data_execucao is None:
            data_execucao = datetime.now(RECIFE_TZ).date()

        tasks_canceladas = self._cancelar_tasks_do_dia(id_grupo, home_id, data_execucao)

        async with async_session_maker() as db:
            linhas_canceladas = await cancelar_pendentes_do_dia(db, id_grupo, home_id, data_execucao)

        if tasks_canceladas or linhas_canceladas:
            logger.info(
                f"🚫 [Scheduler] Cancelamento de {data_execucao} para grupo '{id_grupo}' / home '{home_id}': "
                f"{tasks_canceladas} task(s) em memória, {linhas_canceladas} linha(s) no banco."
            )
            return True
        return False

    # =========================================================================
    # RECONCILIAÇÃO NOTURNA — rede de proteção
    # =========================================================================

    async def reconciliar_automacoes_noturnas(self) -> dict:
        """
        Varre todas as revendas ativas e religa qualquer automação de
        desligamento que tenha ficado desativada.

        Existe porque as correções de pausa/resume reduzem a PROBABILIDADE de a
        loja passar a noite ligada, mas não eliminam a classe: se a Tuya estiver
        fora do ar na hora do resume, se o processo morrer entre a pausa e o
        resume, ou se o UPDATE de `executado` se perder, ninguém religa as
        automações e ninguém fica sabendo. Foi o incidente de 21/09.

        A operação é idempotente por construção — religar uma automação já ativa
        não faz nada — e por isso é segura de rodar todo dia, independente de
        qual tenha sido a causa da falha.

        A única home poupada é a que está em janela de pausa legítima que
        atravessa a meia-noite (ex.: "fechamento até 1h"): ver
        `obter_homes_com_janela_ativa`. Sem essa trava a rede de proteção
        causaria o problema que deveria evitar.

        Retorna um resumo para log/endpoint; não lança (erro por revenda é
        isolado, para que uma home quebrada não aborte a varredura das demais).
        """
        from app.crud.agendamentos import obter_homes_com_janela_ativa
        from app.crud.revendas import listar_revendas_ativas_com_home
        from app.database import async_session_maker
        from app.services.tuya_dispatch_service import _eh_automacao_de_desligamento

        agora = datetime.now(RECIFE_TZ)
        logger.info(f"🌙 [Reconciliação] Iniciando varredura noturna ({agora.isoformat()})...")

        resumo = {
            "executado_em": agora.isoformat(),
            "revendas_verificadas": 0,
            "revendas_puladas_janela_ativa": 0,
            "automacoes_religadas": 0,
            "revendas_com_erro": 0,
            "detalhes": [],
        }

        try:
            async with async_session_maker() as db:
                revendas = await listar_revendas_ativas_com_home(db)
                homes_em_janela = await obter_homes_com_janela_ativa(db, agora)
        except Exception as e:
            logger.error(
                f"❌ [Reconciliação] Falha ao carregar revendas/janelas; varredura abortada: {e}",
                extra={"status": "erro"}, exc_info=True,
            )
            resumo["erro"] = str(e)
            return resumo

        for revenda in revendas:
            home_id = revenda["home_id"]
            nome = revenda["nome_revenda"]

            if home_id in homes_em_janela:
                resumo["revendas_puladas_janela_ativa"] += 1
                logger.info(
                    f"⏭️ [Reconciliação] '{nome}' está em janela de pausa ativa "
                    f"(resume ainda no futuro) — automações preservadas."
                )
                continue

            resumo["revendas_verificadas"] += 1
            try:
                automacoes = await tuya_service.get_automations_by_home(home_id)
                religadas = []
                if automacoes and isinstance(automacoes, list):
                    for auto in automacoes:
                        auto_id = auto.get("id") or auto.get("automation_id")
                        if not auto_id or not _eh_automacao_de_desligamento(auto):
                            continue
                        if auto.get("enabled", True):
                            continue
                        logger.warning(
                            f"🔧 [Reconciliação] '{nome}': automação de desligamento "
                            f"'{auto.get('name')}' ({auto_id}) estava DESATIVADA fora de janela. Religando."
                        )
                        await tuya_service.set_automation_status(home_id, auto_id, enable=True)
                        religadas.append(auto_id)

                if religadas:
                    resumo["automacoes_religadas"] += len(religadas)
                    resumo["detalhes"].append({
                        "nome_revenda": nome,
                        "home_id": home_id,
                        "automacoes_religadas": religadas,
                    })
            except Exception as e:
                resumo["revendas_com_erro"] += 1
                logger.error(
                    f"❌ [Reconciliação] Erro ao reconciliar '{nome}' (home {home_id}): {e}",
                    extra={"status": "erro"}, exc_info=True,
                )

        if resumo["automacoes_religadas"]:
            logger.warning(
                f"🌙 [Reconciliação] Concluída: {resumo['automacoes_religadas']} automação(ões) "
                f"religada(s) em {len(resumo['detalhes'])} revenda(s). "
                f"Cada uma representa um resume que NÃO aconteceu — vale investigar."
            )
        else:
            logger.info(
                f"🌙 [Reconciliação] Concluída sem correções: "
                f"{resumo['revendas_verificadas']} revenda(s) verificada(s), "
                f"{resumo['revendas_puladas_janela_ativa']} em janela ativa."
            )
        return resumo

    def _segundos_ate_proxima_reconciliacao(self, agora: Optional[datetime] = None) -> float:
        """Segundos até o próximo HORA_RECONCILIACAO no fuso de Recife."""
        if agora is None:
            agora = datetime.now(RECIFE_TZ)
        alvo = agora.replace(
            hour=HORA_RECONCILIACAO.hour,
            minute=HORA_RECONCILIACAO.minute,
            second=0,
            microsecond=0,
        )
        if alvo <= agora:
            alvo += timedelta(days=1)
        return (alvo - agora).total_seconds()

    async def _loop_reconciliacao_noturna(self):
        """
        Dorme até 23:50 (Recife), reconcilia, repete.

        O horário é recalculado a cada volta em vez de somar 24h: assim o laço
        não acumula desvio e continua ancorado em 23:50 local mesmo que a
        execução demore ou o relógio mude.
        """
        while True:
            try:
                espera = self._segundos_ate_proxima_reconciliacao()
                logger.info(
                    f"🌙 [Reconciliação] Próxima varredura em {espera / 3600:.1f}h "
                    f"(às {HORA_RECONCILIACAO.strftime('%H:%M')} de Recife)."
                )
                await asyncio.sleep(espera)
                await self.reconciliar_automacoes_noturnas()
            except asyncio.CancelledError:
                logger.info("ℹ️ [Reconciliação] Laço noturno encerrado.")
                raise
            except Exception as e:
                # Nunca deixa o laço morrer: ele é a última linha de defesa.
                logger.error(
                    f"❌ [Reconciliação] Erro no laço noturno (segue ativo): {e}",
                    extra={"status": "erro"}, exc_info=True,
                )
                await asyncio.sleep(60)

    def iniciar_reconciliacao_noturna(self) -> None:
        """
        Sobe o laço diário. Chamado no startup (app/main.py:lifespan).

        É um laço interno, e não mais um alvo de cron externo, de propósito: uma
        rede de proteção que depende de alguém ter configurado o cron certo na
        VPS tem o mesmo ponto único de falha que ela existe para cobrir. O
        endpoint POST /scheduler/reconciliacao continua disponível para disparo
        manual e como reforço externo, se quiserem.
        """
        if self._reconciliacao_task is not None and not self._reconciliacao_task.done():
            logger.info("🌙 [Reconciliação] Laço noturno já ativo.")
            return
        self._reconciliacao_task = asyncio.create_task(self._loop_reconciliacao_noturna())

    def parar_reconciliacao_noturna(self) -> None:
        """Cancela o laço diário. Chamado no shutdown."""
        if self._reconciliacao_task is not None and not self._reconciliacao_task.done():
            self._reconciliacao_task.cancel()
        self._reconciliacao_task = None

    async def _tick_manual_para_testes(self):
        """Alias para carregar_agendamentos_pendentes (usado nos testes de T5)."""
        await self.carregar_agendamentos_pendentes()

scheduler_service = SchedulerService()
