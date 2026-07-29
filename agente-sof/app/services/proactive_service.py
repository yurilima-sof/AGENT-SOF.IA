import logging
from datetime import datetime
import calendar
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ProactiveService:
    """
    Serviço para mensagens proativas da SOF.IA nos grupos de WhatsApp das revendas.
    Verifica se a data atual está no final do mês e gera notificações para confirmar
    se a revenda terá fechamento de mês/horário estendido.
    """

    def is_fim_de_mes(self) -> bool:
        """
        Verifica se a data atual corresponde aos últimos 3 dias do mês vigente.
        """
        hoje = datetime.now()
        ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
        dias_restantes = ultimo_dia - hoje.day
        return 0 <= dias_restantes <= 3

    async def obter_revendas_ativas(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Retorna todas as revendas ativas cadastradas no banco de dados.
        """
        query = text("""
            SELECT id_grupo_wpp, nome_revenda 
            FROM mapa_revendas 
            WHERE ativo = TRUE
        """)
        result = await db.execute(query)
        return [dict(row._mapping) for row in result.fetchall()]

    def gerar_mensagem_fechamento_mes(self, nome_revenda: str) -> str:
        """
        Gera a mensagem amigável e humanizada da SOF.IA perguntando sobre o fechamento de mês.
        """
        return (
            f"Olá equipe da {nome_revenda}! 🏢✨\n\n"
            f"Como estamos nos últimos dias do mês, passei para perguntar: **vocês terão Fechamento de Mês hoje e vão precisar ficar até mais tarde?** 🕒\n\n"
            f"Se sim, me avisem por aqui até que horas vão precisar do ar-condicionado ligado (ex: *'vamos até 21h'* ou *'fechamento até 22h'*) que eu pauso o desligamento automático para vocês! 😊"
        )

proactive_service = ProactiveService()
