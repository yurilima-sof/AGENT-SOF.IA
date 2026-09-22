# =============================================================================
# app/domain/policy/broadcast_filter.py - Filtro de Auto-Ingestão no RAG
# =============================================================================
# Impede que a Sofia ingira o PRÓPRIO broadcast ("~Equipe SOF") como se fosse
# conhecimento vindo de um cliente.
#
# Por que por conteúdo e não pelo remetente: o payload do /agent
# (app/schemas/agent.py) tem apenas `mensagem`, `id_grupo` e `nome_revenda` —
# nenhum campo identifica quem enviou. Enquanto o n8n não passar algo como
# `from_me`, a API é estruturalmente incapaz de distinguir o broadcast de uma
# mensagem de loja, e o conteúdo é o único sinal disponível.
#
# O risco desta abordagem é o FALSO POSITIVO: barrar uma resposta legítima de
# revenda. Por isso as regras abaixo são deliberadamente estreitas — exigem a
# assinatura da SOF ou o template não preenchido, não apenas palavras que um
# cliente também usaria. Os testes em tests/unit/test_broadcast_filter.py
# travam os dois lados (barra broadcast / não barra cliente).
# =============================================================================

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Assinatura da própria SOF: "~Equipe SOF", tolerando espaço e caixa.
_RE_ASSINATURA_SOF = re.compile(r"~\s*equipe\s+sof", re.IGNORECASE)

# Template de solicitação não preenchido: o literal "Ex:" logo após o campo
# denuncia que ninguém substituiu o exemplo — é a SOF perguntando, não a loja
# respondendo. Uma loja que responde escreve a data real no lugar do "Ex:".
_RE_TEMPLATE_NAO_PREENCHIDO = re.compile(
    r"data\s+para\s+o\s+evento\s*:?\s*ex\s*:", re.IGNORECASE
)

# Combinação do corpo do broadcast: pedir a data do evento E encerrar com a
# fórmula de aguardo. Isolados, qualquer um dos dois pode vir de um cliente —
# juntos, é o texto do comunicado.
_RE_DATA_EVENTO = re.compile(r"data\s+para\s+o\s+evento", re.IGNORECASE)
_RE_AGUARDO = re.compile(r"ficamos\s+no\s+aguardo", re.IGNORECASE)


def eh_broadcast_sof(mensagem: Optional[str]) -> bool:
    """True se a mensagem parece ser o broadcast enviado pela própria SOF."""
    if not mensagem:
        return False

    if _RE_ASSINATURA_SOF.search(mensagem):
        return True

    if _RE_TEMPLATE_NAO_PREENCHIDO.search(mensagem):
        return True

    if _RE_DATA_EVENTO.search(mensagem) and _RE_AGUARDO.search(mensagem):
        return True

    return False


def deve_ingerir(mensagem: Optional[str]) -> bool:
    """
    Decide se a mensagem pode virar memória no RAG.

    Retorna False para o broadcast da própria SOF e para mensagem vazia;
    True para qualquer outra coisa — inclusive respostas de loja que citem
    a data do evento, que são justamente o conteúdo que queremos guardar.
    """
    if not mensagem:
        return False

    if eh_broadcast_sof(mensagem):
        logger.info("   [RAG] Mensagem identificada como broadcast SOF — ingestão ignorada.")
        return False

    return True
