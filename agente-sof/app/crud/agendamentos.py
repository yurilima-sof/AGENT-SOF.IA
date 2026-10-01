import json
import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def inicializar_tabela_agendamentos(db: AsyncSession) -> None:
    """
    Garante que a tabela agendamentos existe no PostgreSQL e atualiza schema
    com colunas fase e data_execucao se necessário.
    """
    try:
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS agendamentos (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                id_grupo_wpp VARCHAR(100) NOT NULL,
                nome_revenda VARCHAR(100) NOT NULL,
                home_id VARCHAR(100) NOT NULL,
                automacao_ids JSONB NOT NULL,
                horario_execucao TIMESTAMP WITH TIME ZONE NOT NULL,
                executado BOOLEAN DEFAULT FALSE,
                criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
        """))

        # Add new columns IF NOT EXISTS
        await db.execute(text("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS data_execucao DATE;"))
        await db.execute(text("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS fase VARCHAR(10);"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS idx_agendamentos_exec_fase ON agendamentos (executado, data_execucao, fase);"))

        # Backfill de linhas legadas (fase/data_execucao NULL). Sem isto, o recorte
        # por data em carregar_agendamentos_pendentes não consegue decidir se a
        # linha é de hoje ou de um dia que já passou, e ela ficaria pendente para
        # sempre, re-disparando a cada restart (achado C3).
        await db.execute(text("""
            UPDATE agendamentos
            SET fase = COALESCE(fase, 'resume'),
                data_execucao = COALESCE(data_execucao, horario_execucao::date)
            WHERE executado = FALSE AND (fase IS NULL OR data_execucao IS NULL)
        """))

        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"⚠️ Não foi possível inicializar a tabela agendamentos: {e}", extra={"status": "erro"}, exc_info=True)

async def cancelar_pendentes_do_dia(
    db: AsyncSession,
    id_grupo_wpp: str,
    home_id: str,
    data_execucao: date,
) -> int:
    """
    Marca como executadas as pendências de UM dia específico de um grupo/home.
    Retorna quantas linhas foram afetadas.

    O recorte por `data_execucao` é a correção do achado A5: antes, cancelar a
    pausa de hoje ("reunião cancelada") varria todas as pendências daquele
    grupo/home, apagando junto o evento já agendado para o próximo sábado.

    Também é o que fecha o achado C2: `salvar_agendamento` chama isto antes de
    inserir, para que uma segunda pausa no mesmo dia ("na verdade até 22h")
    substitua a primeira. Duas linhas pendentes significavam dois resumes, e o
    das 20h desligava a loja com a reunião ainda acontecendo.
    """
    try:
        result = await db.execute(text("""
            UPDATE agendamentos
            SET executado = TRUE
            WHERE id_grupo_wpp = :id_g
              AND home_id = :h_id
              AND executado = FALSE
              AND (data_execucao = :d_exec
                   OR (data_execucao IS NULL AND horario_execucao::date = :d_exec))
        """), {"id_g": id_grupo_wpp, "h_id": home_id, "d_exec": data_execucao})
        await db.commit()
        return result.rowcount or 0
    except Exception as e:
        await db.rollback()
        logger.error(
            f"❌ Erro ao cancelar pendências de {data_execucao} para grupo "
            f"'{id_grupo_wpp}' / home '{home_id}': {e}",
            extra={"status": "erro"}, exc_info=True,
        )
        return 0

async def salvar_agendamento(
    db: AsyncSession,
    id_grupo_wpp: str,
    nome_revenda: str,
    home_id: str,
    automacao_ids: list,
    horario_execucao: datetime
) -> Optional[str]:
    # Legacy wrapper — usado pelo fluxo de pausa de "hoje"
    # (scheduler_service.agendar_reativacao_automacao).
    #
    # Antes de inserir, cancela as pendências do MESMO dia (achado C2). O caminho
    # "futuro" (salvar_agendamento_evento) sempre fez isso via DELETE; o "hoje"
    # não fazia, então cada nova pausa empilhava mais um resume sobre o anterior.
    #
    # O commit fica AQUI, e não em _salvar_linha, porque _salvar_linha é
    # compartilhada com salvar_agendamento_evento, que precisa inserir as duas
    # fases (pause + resume) na MESMA transação e commita uma vez só no fim.
    # Cada função pública é responsável pelo próprio commit.
    #
    # Sem este commit o INSERT era revertido ao fechar a sessão
    # (async_session_maker) e o resume do "hoje" nunca chegava ao banco —
    # bug de produção de 21/09, em que a consulta de agendamentos voltava vazia.
    data_execucao = horario_execucao.date()
    await cancelar_pendentes_do_dia(db, id_grupo_wpp, home_id, data_execucao)

    agendamento_id = await _salvar_linha(
        db, id_grupo_wpp, nome_revenda, home_id, automacao_ids,
        horario_execucao, "resume", data_execucao,
    )
    await db.commit()
    return agendamento_id

async def _salvar_linha(db, id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao, fase, data_execucao):
    try:
        result = await db.execute(
            text("""
                INSERT INTO agendamentos (id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao, fase, data_execucao)
                VALUES (:id_grupo_wpp, :nome_revenda, :home_id, :automacao_ids, :horario_execucao, :fase, :data_execucao)
                RETURNING id
            """),
            {
                "id_grupo_wpp": id_grupo_wpp,
                "nome_revenda": nome_revenda,
                "home_id": home_id,
                "automacao_ids": json.dumps(automacao_ids),
                "horario_execucao": horario_execucao,
                "fase": fase,
                "data_execucao": data_execucao
            }
        )
        row = result.fetchone()
        return str(row[0]) if row else None
    except Exception as e:
        logger.error(f"❌ Erro ao salvar agendamento no banco: {e}")
        raise

async def salvar_agendamento_evento(
    db: AsyncSession,
    id_grupo_wpp: str,
    nome_revenda: str,
    home_id: str,
    automacao_ids: list,
    data_execucao: date,
    hora_pause: datetime,
    hora_resume: datetime
) -> list[str]:
    """
    Salva duas fases (pause e resume) deletando qualquer pendência futura no mesmo dia para a home.
    """
    try:
        # Delete old pending items for same home and date
        await db.execute(text("""
            DELETE FROM agendamentos
            WHERE id_grupo_wpp = :id_g AND home_id = :h_id
              AND data_execucao = :d_exec AND executado = FALSE
        """), {"id_g": id_grupo_wpp, "h_id": home_id, "d_exec": data_execucao})

        id1 = await _salvar_linha(db, id_grupo_wpp, nome_revenda, home_id, automacao_ids, hora_pause, "pause", data_execucao)
        id2 = await _salvar_linha(db, id_grupo_wpp, nome_revenda, home_id, automacao_ids, hora_resume, "resume", data_execucao)
        await db.commit()
        return [id1, id2]
    except Exception as e:
        await db.rollback()
        logger.error(f"Erro ao salvar evento futuro: {e}")
        return []

async def obter_agendamentos_pendentes(db: AsyncSession) -> list:
    """
    Pendências ainda não executadas, da mais antiga para a mais nova.

    A ordenação importa para o scheduler decidir o que já venceu. Quem aplica o
    recorte temporal (achado C3) é `carregar_agendamentos_pendentes`, porque a
    decisão depende da fase: um `pause` vencido deve ser descartado, enquanto um
    `resume` vencido ainda precisa religar as automações — regra que não cabe em
    um WHERE.
    """
    try:
        query = text("""
            SELECT id, id_grupo_wpp, nome_revenda, home_id, automacao_ids, horario_execucao, fase, data_execucao
            FROM agendamentos
            WHERE executado = FALSE
            ORDER BY horario_execucao
        """)
        result = await db.execute(query)
        return result.fetchall()
    except Exception as e:
        await db.rollback()
        logger.error(
            f"❌ Erro ao consultar agendamentos pendentes (o tick vira no-op): {e}",
            extra={"status": "erro"}, exc_info=True,
        )
        return []

async def obter_homes_com_janela_ativa(db: AsyncSession, agora: datetime) -> set:
    """
    Homes cuja pausa ainda não terminou: existe um `resume` pendente com horário
    no futuro.

    É a trava da reconciliação noturna. Sem ela, um "fechamento até 1h" — que o
    parser resolve como resume no dia seguinte — teria as automações de OFF
    religadas às 23:50, desligando a loja no meio do fechamento. Ou seja: a rede
    de proteção viraria exatamente o incidente que ela existe para evitar.
    """
    try:
        result = await db.execute(text("""
            SELECT DISTINCT home_id
            FROM agendamentos
            WHERE executado = FALSE
              AND fase = 'resume'
              AND horario_execucao > :agora
        """), {"agora": agora})
        return {r[0] for r in result.fetchall()}
    except Exception as e:
        await db.rollback()
        logger.error(
            f"❌ Erro ao consultar janelas de pausa ativas: {e}",
            extra={"status": "erro"}, exc_info=True,
        )
        # Falha fechada: sem saber quem está em janela ativa, a reconciliação
        # não deve religar nada — religar por engano desliga uma loja ocupada.
        raise

async def marcar_agendamento_executado(db: AsyncSession, agendamento_id: str) -> bool:
    """
    Marca a linha como executada. Retorna True se deu certo.

    O retorno existe porque a falha aqui não é inofensiva: se o UPDATE não passa,
    a linha volta no próximo tick e a ação é re-executada. Antes a exceção era
    engolida sem log nenhum (achado A7) e isso ficava invisível.
    """
    try:
        await db.execute(
            text("""
                UPDATE agendamentos
                SET executado = TRUE
                WHERE id = :id
            """),
            {"id": agendamento_id}
        )
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        logger.error(
            f"❌ Erro ao marcar agendamento {agendamento_id} como executado "
            f"(a linha seguirá pendente e pode re-executar): {e}",
            extra={"status": "erro"}, exc_info=True,
        )
        return False
