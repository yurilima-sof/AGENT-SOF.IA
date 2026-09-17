# =============================================================================
# app/services/llm_service.py - Classificação Semântica e IA (RAG) com Gemini
# =============================================================================

import asyncio
import json
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime

from google import genai
from google.genai import types
from app.config import get_settings
from app.services.rag_service import rag_service
from app.domain.policy.datetime_parser import extrair_janela_evento, EscopoTemporal


logger = logging.getLogger(__name__)
settings = get_settings()

GEMINI_TIMEOUT_SEGUNDOS = 20.0

# Detecta que o usuário quer CANCELAR uma pausa de automação já em andamento
# (reunião acabou/foi cancelada) e reativar tudo agora — distinto do bloco de
# pausa abaixo, que só sabe PAUSAR. Baseado em regex (em vez de frases exatas)
# pra tolerar palavras intercaladas, ex: "a reunião JÁ acabou". Ver
# app/services/tuya_dispatch_service.py (acao == "reativar_automacao") para o
# que acontece fisicamente na Tuya.
_RE_MENCIONA_REUNIAO = re.compile(r"reuni[ãa]o|fechamento\s+de\s+m[êe]s")
_RE_FIM_OU_CANCELAMENTO = re.compile(r"acabou|terminou|cancel\w*")
_RE_PEDIDO_DIRETO_DE_REATIVACAO = re.compile(
    r"tir\w*\s+a[s]?\s+pausa[s]?"
    r"|remov\w*\s+a\s+pausa"
    r"|reativ\w*\s+a[s]?\s+automa[çc]\w*"
    r"|pode\s+reativar"
    r"|(?:liga|religa)\w*\s+(?:de\s+novo\s+)?a[s]?\s+automa[çc]\w*"
)


def _mensagem_indica_cancelamento_pausa(mensagem_lower: str) -> bool:
    if _RE_PEDIDO_DIRETO_DE_REATIVACAO.search(mensagem_lower):
        return True
    return bool(_RE_MENCIONA_REUNIAO.search(mensagem_lower) and _RE_FIM_OU_CANCELAMENTO.search(mensagem_lower))


def _remover_cerca_markdown(texto: str) -> str:
    """Remove blocos de código markdown (```json ... ``` ou ``` ... ```) ao redor do JSON."""
    texto = texto.strip()
    if not texto.startswith("```"):
        return texto
    linhas = texto.splitlines()
    if linhas and linhas[0].startswith("```"):
        linhas = linhas[1:]
    if linhas and linhas[-1].startswith("```"):
        linhas = linhas[:-1]
    return "\n".join(linhas).strip()


def _escapar_aspas_soltas(texto: str) -> str:
    """
    Escapa aspas duplas que aparecem DENTRO de valores de string do JSON sem terem
    sido escapadas pelo Gemini (ex: 'mensagem_wpp': 'ele disse "oi"'). Considera uma
    aspa "estrutural" (abre/fecha string de verdade) só se o caractere imediatamente
    antes for um dos delimitadores '{[:,' (ignorando espaços) ou o imediatamente
    depois for um dos delimitadores ':,}]' (ignorando espaços); qualquer outra aspa
    é tratada como solta dentro do valor e escapada.
    """
    resultado = []
    n = len(texto)
    for i, ch in enumerate(texto):
        if ch == '"' and (i == 0 or texto[i - 1] != '\\'):
            antes = texto[:i].rstrip()
            depois = texto[i + 1:].lstrip()
            eh_estrutural = (not antes or antes[-1] in '{[:,') or (not depois or depois[0] in ':,}]')
            if not eh_estrutural:
                resultado.append('\\"')
                continue
        resultado.append(ch)
    return "".join(resultado)


def _escapar_quebras_de_linha_em_strings(texto: str) -> str:
    """
    Troca quebras de linha literais (\\n / \\r reais) por suas versões escapadas
    quando aparecem DENTRO de um valor de string JSON — o Gemini às vezes gera a
    quebra de linha de verdade em vez do escape '\\\\n', o que quebra o parser.
    """
    resultado = []
    dentro_de_string = False
    escapando = False
    for ch in texto:
        if dentro_de_string:
            if escapando:
                resultado.append(ch)
                escapando = False
                continue
            if ch == "\\":
                resultado.append(ch)
                escapando = True
                continue
            if ch == '"':
                dentro_de_string = False
                resultado.append(ch)
                continue
            if ch == "\n":
                resultado.append("\\n")
                continue
            if ch == "\r":
                resultado.append("\\r")
                continue
            resultado.append(ch)
        else:
            if ch == '"':
                dentro_de_string = True
            resultado.append(ch)
    return "".join(resultado)


def _reparar_json_truncado(texto: str) -> Optional[dict]:
    """
    Repara, de forma best-effort, um JSON cortado no meio (comum quando a resposta
    do Gemini é truncada por max_output_tokens): fecha uma string não terminada e
    fecha chaves/colchetes pendentes na ordem inversa de abertura. Retorna None se
    mesmo após o reparo o texto continuar inválido.
    """
    reparado = texto.rstrip()
    if not reparado:
        return None

    aspas_abertas = 0
    escapando = False
    for ch in reparado:
        if escapando:
            escapando = False
            continue
        if ch == "\\":
            escapando = True
            continue
        if ch == '"':
            aspas_abertas += 1
    if aspas_abertas % 2 == 1:
        reparado += '"'

    # Corte logo após uma vírgula (ex: '..."ambiente": null,') ou logo após uma chave
    # sem valor (ex: '..."ambiente": null, "mensagem_wpp"') deixa uma cauda inválida
    # que fechar chaves sozinho não resolve — remove essa cauda pendurada.
    reparado = re.sub(r',\s*"[^"]*"\s*:?\s*$', "", reparado)
    reparado = re.sub(r'[,:]\s*$', "", reparado)

    pilha = []
    dentro_de_string = False
    escapando = False
    for ch in reparado:
        if dentro_de_string:
            if escapando:
                escapando = False
            elif ch == "\\":
                escapando = True
            elif ch == '"':
                dentro_de_string = False
            continue
        if ch == '"':
            dentro_de_string = True
        elif ch in "{[":
            pilha.append(ch)
        elif ch in "}]":
            if pilha:
                pilha.pop()

    fechamentos = {"{": "}", "[": "]"}
    while pilha:
        reparado += fechamentos[pilha.pop()]

    try:
        return json.loads(reparado)
    except json.JSONDecodeError:
        return None


def _parse_and_repair_json(raw_text: str) -> dict:
    """
    Interpreta a resposta em texto do Gemini como JSON, aplicando reparos
    progressivos para os padrões de malformação mais comuns observados em
    produção: bloco de código markdown ao redor, caracteres de controle,
    aspas não escapadas dentro de strings, quebras de linha literais dentro
    de strings, e JSON truncado por limite de tokens.

    Lança json.JSONDecodeError se nenhuma tentativa de reparo funcionar.
    """
    texto = _remover_cerca_markdown(raw_text)

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    sem_controle = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", texto)
    try:
        return json.loads(sem_controle)
    except json.JSONDecodeError:
        pass

    aspas_corrigidas = _escapar_aspas_soltas(sem_controle)
    try:
        return json.loads(aspas_corrigidas)
    except json.JSONDecodeError:
        pass

    quebras_corrigidas = _escapar_quebras_de_linha_em_strings(aspas_corrigidas)
    try:
        return json.loads(quebras_corrigidas)
    except json.JSONDecodeError:
        pass

    reparado = _reparar_json_truncado(quebras_corrigidas)
    if reparado is not None:
        return reparado

    raise json.JSONDecodeError("Não foi possível interpretar/reparar o JSON do Gemini", texto, 0)


class LLMService:
    """
    Serviço para gerenciar chamadas ao Google Gemini (gemini-2.5-flash) para classificação
    semântica de comandos de temperatura/IoT e conversação amigável.
    """

    def __init__(self):
        self._client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None

    async def _chamar_gemini(self, system_prompt: str, user_content: str) -> dict:
        m_name = getattr(settings, 'gemini_model', 'gemini-3.6-flash')
        logger.info(f"   [Gemini] Iniciando requisição direta ao modelo {m_name}...")
        try:
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=m_name,
                        contents=user_content,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            temperature=0.0,
                            max_output_tokens=2048,
                        ),
                    ),
                    timeout=GEMINI_TIMEOUT_SEGUNDOS,
                )
            except Exception as e_sys:
                logger.warning(f"⚠️ Chamada com system_instruction falhou ({e_sys}). Tentando modo de prompt unificado...")
                full_prompt = f"{system_prompt}\n\n{user_content}"
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=m_name,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0,
                            max_output_tokens=2048,
                        ),
                    ),
                    timeout=GEMINI_TIMEOUT_SEGUNDOS,
                )
            if not response or not response.text:
                raise ValueError("Resposta vazia da API do Gemini.")
            logger.info(f"✅ Resposta do Gemini obtida com sucesso usando {m_name}.")
            try:
                return _parse_and_repair_json(response.text)
            except json.JSONDecodeError:
                logger.error(
                    f"⚠️ JSON do Gemini não pôde ser interpretado nem após reparo. "
                    f"Resposta bruta (truncada): {response.text.strip()[:500]!r}",
                    extra={"status": "erro"},
                )
                raise
        except Exception as e:
            logger.error(f"⚠️ Erro Crítico ao chamar o Gemini ({m_name}): {e}", extra={"status": "erro"}, exc_info=True)
            return {
                "intencao": None,
                "ifttt_action": None,
                "ambiente": None,
                "mensagem_wpp": "Puxa, estou passando por uma instabilidade técnica rápida aqui no meu sistema. Pode tentar novamente em alguns minutos? 🛠️",
                "salvar_memoria": False
            }

    async def processar_mensagem(
        self,
        mensagem: str,
        id_grupo: str,
        ambientes_disponiveis: list[str] = None,
        historico_recente: Optional[str] = None,
        agora: Optional[datetime] = None
    ) -> Dict[str, Any]:
        mensagem_lower = mensagem.lower()
        if _mensagem_indica_cancelamento_pausa(mensagem_lower):
            logger.info(f"   [LLM] Regra determinística de CANCELAMENTO de pausa ativada para mensagem: '{mensagem}'")
            return {
                "intencao": "reativar_automacao_agora",
                "ifttt_action": "reativar_automacao",
                "ambiente": None,
                "mensagem_wpp": "Combinado! 😊 Já reativei as automações e cancelei o agendamento anterior.",
                "salvar_memoria": False
            }

        palavras_pausa = ["reunião", "reuniao", "fechamento de mês", "fechamento de mes", "não desliga", "nao desliga", "pausar automação", "pausar automacao"]
        # Allow LLM to extract dates before returning

        contexto_rag = ""
        try:
            contexto_rag = await rag_service.get_relevant_context(mensagem, id_grupo)
            if contexto_rag:
                logger.info(f"   Contexto RAG recuperado para a mensagem.")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao recuperar contexto do RAG: {e}")

        data_atual_str = datetime.now().strftime("%d/%m/%y")

        system_prompt = (
            "Você é a Sofia, a assistente inteligente da SOF para controle de temperatura. "
            "Sempre aja com essa persona: feminina, amigável, acolhedora, prestativa e altamente eficiente. "
            "Sua tarefa é analisar a mensagem do usuário no WhatsApp e decidir qual ação física IoT tomar e "
            "gerar uma resposta amigável.\n\n"
            
            f"INFORMAÇÃO DE TEMPO ATUAL: A data de hoje é {data_atual_str}.\n\n"

            "Você deve responder EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:\n"
            "{\n"
            "  \"intencao\": \"ligar_resfriamento\" | \"ligar_aquecimento\" | \"ligar_temperatura_media\" | \"desligar_dispositivos\" | \"ligar_dispositivos\" | \"pausar_automacao\" | \"reativar_automacao_agora\" | \"sem_acao\",\n"
            "  \"ifttt_action\": \"freezer\" | \"esquentar\" | \"medio\" | \"off\" | \"ligar\" | \"desativar_automacao\" | \"reativar_automacao\" | null,\n"
            "  \"ambiente\": \"nome do ambiente (slug) ou null\",\n"
            "  \"data_evento\": \"YYYY-MM-DD ou null\",\n"
            "  \"hora_inicio\": \"HH:MM ou null\",\n"
            "  \"hora_fim\": \"HH:MM ou null\",\n"
            "  \"escopo_temporal\": \"hoje\" | \"futuro\" | \"indefinido\",\n"
            "  \"mensagem_wpp\": \"Sua resposta amigável para o WhatsApp\",\n"
            "  \"salvar_memoria\": true | false\n"
            "}\n\n"
            "Filtro de Memória Orgânica (salvar_memoria):\n"
            "- Defina como true APENAS se a mensagem do usuário ditar uma regra, preferência duradoura, padrão de temperatura ou hábito que o bot deve lembrar para o futuro (ex: 'sempre ligamos no medio de manhã', 'nossa loja é muito gelada às 14h', 'vamos ter reunião até 20h').\n"
            "- Defina como false para comandos normais ('liga o ar'), reclamações pontuais ('tá quente hoje'), saudações e lixo.\n\n"
            
            "Regra de Execução Imediata vs Futura:\n"
            "- Se o usuário estiver APENAS declarando uma regra para o futuro (ex: 'Queremos que todos os dias as 14:15 esteja frio' ou 'A partir de amanhã, faça X'), você NÃO deve executar a ação agora. Retorne `ifttt_action: null` e `intencao: sem_acao`, mas mantenha `salvar_memoria: true`.\n"
            "- Retorne uma ação no `ifttt_action` APENAS se o comando for para ser executado NESTE EXATO MOMENTO (incluindo desativar automações de desligamento para reuniões agora).\n\n"
            
            "Hierarquia de Conhecimento e Comandos:\n"
            "- Se o histórico do RAG trouxer informações marcadas como [REGRA ESPECÍFICA DA REVENDA], elas ANULAM as orientações de [REGRA GLOBAL] em caso de conflito.\n"
            "- Sempre verifique no histórico (RAG) a progressão de comandos da revenda. Por exemplo, se eles preferem iniciar com temperatura 'medio' e depois ir para 'freezer', ignore a Regra de Decisão padrão abaixo e siga a preferência da revenda.\n\n"

            "MEMÓRIA DE CURTO PRAZO E MENSAGENS SEQUENCIAIS NO WHATSAPP:\n"
            "- No WhatsApp, o usuário frequentemente digita mensagens picadas em sequência (ex: 'Loja quente' seguido por 'Térreo').\n"
            "- Se o HISTÓRICO RECENTE DA CONVERSA trouxer um comando incompleto anterior (ex: pedir para esfriar sem especificar o ambiente) E a mensagem atual informar o ambiente (ex: 'Térreo'), COMBINE as informações e execute a ação para aquele ambiente!\n\n"

            "REGRA MANDATÓRIA DE ESCALONAMENTO PROGRESSIVO DE RESFRIAMENTO (1º, 2º E 3º CHAMADOS DE CALOR):\n"
            "Quando a mensagem do usuário for uma solicitação ou reclamação genérica de calor/resfriamento (ex: 'loja quente', 'tá quente', 'esfria a sala', 'diminui a temperatura', 'loja abafada'):\n"
            "1. Você DEVE analisar o HISTÓRICO RECENTE DA CONVERSA (últimos 15 minutos) para contar quantas solicitações de resfriamento anteriores foram feitas neste grupo:\n"
            "   - 1º CHAMADO (Nenhum chamado de resfriamento recente no histórico): OBRIGATORIAMENTE acione `ifttt_action: \"medio\"`, `intencao: \"ligar_temperatura_media\"`. Responda amigavelmente informando que iniciou a climatização da loja.\n"
            "   - 2º CHAMADO (Já existe 1 chamado prévio de resfriamento recente no histórico): OBRIGATORIAMENTE acione `ifttt_action: \"freezer\"`, `intencao: \"ligar_resfriamento\"`. Responda informando que intensificou o resfriamento para deixar o ambiente mais fresco.\n"
            "   - 3º CHAMADO OU MAIS (Já existem 2 ou mais chamados prévios no histórico): OBRIGATORIAMENTE acione `ifttt_action: \"freezer\"`, `intencao: \"ligar_resfriamento\"`. Responda informando que ativou o resfriamento máximo para gelar o ambiente rapidamente.\n"
            "2. EXCEÇÃO EXPLÍCITA: Se a mensagem do usuário solicitar EXPLICITAMENTE uma temperatura específica (ex: 'põe no medio', 'gelar no máximo'), RESPEITE o comando direto do usuário imediatamente.\n\n"

            "REGRA DE SOBREPOSIÇÃO ABSOLUTA (PRIORIDADE CRÍTICA):\n"
            "Se a mensagem ATUAL do usuário mencionar REUNIÃO (ex: 'vamos ter reunião', 'reunião até as 20h', 'reunião na sala de testes'), FECHAMENTO DE MÊS ou solicitar para 'não desligar o ar até Xh' / pausar automações:\n"
            "- A intenção OBRIGATORIAMENTE DEVE SER: `pausar_automacao`\n"
            "- O ifttt_action OBRIGATORIAMENTE DEVE SER: `desativar_automacao`\n"
            "- A flag salvar_memoria OBRIGATORIAMENTE DEVE SER: `true`\n"
            "- IGNORE qualquer comando antigo ou histórico do RAG que tenha associado essas palavras a 'freezer' ou 'ligar_resfriamento'.\n\n"

            "REGRA DE CANCELAMENTO DE PAUSA (REATIVAR AUTOMAÇÃO AGORA):\n"
            "Se a mensagem ATUAL do usuário indicar que uma reunião/fechamento acabou, foi cancelada, ou pedir explicitamente para "
            "tirar/remover/cancelar a pausa das automações e reativar tudo AGORA (ex: 'reunião cancelada', 'a reunião já acabou', "
            "'pode tirar a pausa', 'reativa as automações'):\n"
            "- A intenção OBRIGATORIAMENTE DEVE SER: `reativar_automacao_agora`\n"
            "- O ifttt_action OBRIGATORIAMENTE DEVE SER: `reativar_automacao`\n"
            "- NUNCA classifique isso como `ligar_dispositivos`/`ligar` — reativar automação é diferente de ligar um equipamento.\n\n"

            "ATENÇÃO OBRIGATÓRIA - FRASES PASSIVAS DE RECLAMAÇÃO E PARTICÍPIO:\n"
            "Frases no particípio indicando que equipamentos estão desligados (ex: 'máquinas desligadas', 'ar desligado', 'tudo desligado', 'máquinas continuam desligadas', 'ar condicionados da loja desligados') ou queixas de calor (ex: 'loja quente', 'tá quente') NUNCA são informativos neutros ou comandos de desligar — DEVEM ser tratadas obrigatoriamente como solicitação de LIGAR climatização / resfriamento (acionando 'medio' ou 'ligar'). NUNCA retorne 'sem_acao' e NUNCA retorne 'off'.\n\n"

            "Regras de Decisão Semântica (Padrão e Prioridade):\n"
            "1. PRIORIDADE MÁXIMA - REUNIÃO PROLONGADA / FECHAMENTO DE MÊS / PAUSAR AUTOMAÇÃO:\n"
            "   Se o usuário informar que haverá REUNIÃO, FECHAMENTO DE MÊS ou pedir para pausar/desativar os desligamentos automáticos programados:\n"
            "   - 'intencao': 'pausar_automacao'\n"
            "   - 'ifttt_action': 'desativar_automacao'\n"
            "   - 'salvar_memoria': true\n"
            "2. Se o usuário informar CALOR ou solicitar resfriamento genérico (ex: 'loja quente', 'sala quente', 'esfria a sala', 'diminui a temperatura'):\n"
            "   - Siga RIGOROSAMENTE a REGRA MANDATÓRIA DE ESCALONAMENTO PROGRESSIVO acima:\n"
            "     * 1º Chamado Recente de Calor: 'ifttt_action': 'medio', 'intencao': 'ligar_temperatura_media'\n"
            "     * 2º Chamado Recente de Calor: 'ifttt_action': 'freezer', 'intencao': 'ligar_resfriamento'\n"
            "     * 3º Chamado ou mais Recente de Calor: 'ifttt_action': 'freezer', 'intencao': 'ligar_resfriamento'\n"
            "3. Se o usuário estiver com FRIO, disser que a sala está gelada/fria, pedir para esquentar/aquecer:\n"
            "   - 'intencao': 'ligar_aquecimento'\n"
            "   - 'ifttt_action': 'esquentar'\n"
            "4. Se o usuário pedir para deixar numa temperatura média, agradável, primeiro calor:\n"
            "   - 'intencao': 'ligar_temperatura_media'\n"
            "   - 'ifttt_action': 'medio'\n"
            "5. Se o usuário pedir para desligar as máquinas/equipamentos, informar que a revenda está fechada/fechando:\n"
            "   - 'intencao': 'desligar_dispositivos'\n"
            "   - 'ifttt_action': 'off'\n"
            "6. Se o usuário pedir para ligar as máquinas/equipamentos/ar-condicionado de forma geral (sem especificar calor/frio):\n"
            "   - 'intencao': 'ligar_dispositivos'\n"
            "   - 'ifttt_action': 'ligar'\n"
            "7. Qualquer outra conversa (saudações, agradecimentos, perguntas gerais):\n"
            "   - 'intencao': 'sem_acao'\n"
            "   - 'ifttt_action': null\n\n"
            
            "Regras de Múltiplos Ambientes:\n"
            "1. Se a loja possui múltiplos ambientes, os ambientes disponíveis estarão listados em 'AMBIENTES CADASTRADOS PARA ESTA REVENDA' no prompt abaixo.\n"
            "2. Se o usuário pedir uma ação e ESPECIFICAR o ambiente (ex: 'liga o showroom'), devolva no campo 'ambiente' o nome formatado (ex: 'showroom').\n"
            "3. Se a loja possuir múltiplos ambientes, o usuário pedir uma ação (ex: 'tá quente') E NÃO ESPECIFICAR o ambiente:\n"
            "   - NÃO execute nenhuma ação física ('ifttt_action': null, 'intencao': 'sem_acao').\n"
            "   - Pergunte na 'mensagem_wpp' qual dos ambientes ele deseja controlar, listando de forma orgânica os ambientes disponíveis.\n"
            "4. Se a lista de ambientes estiver vazia, assuma que a loja possui apenas ambiente único e devolva 'ambiente': null, acionando normalmente.\n\n"

            "Diretrizes Críticas para a resposta no campo 'mensagem_wpp':\n"
            "1. O campo 'mensagem_wpp' deve ser natural, educado, profissional e direto ao ponto.\n"
            "2. EVITE saudações excessivamente informais como 'Oi!' ou 'Olá!' no início de confirmações de comandos. Prefira iniciar diretamente com a confirmação da ação (ex: 'Pronto! Já ajustei a climatização para...', 'Entendido! Configurei o ambiente para...').\n"
            "3. NUNCA mencione códigos internos, códigos numéricos de ambiente/revenda (como '0081', '0045', '0018', etc.), termos como 'unidade XXXX' ou 'ambiente XXXX' acompanhados de código, nomes técnicos de comandos ou modos do sistema (como 'T-Low', 'T-Medium', 'T-Freezer', 'T-High', 'T-Off', 'freezer', 'esquentar', 'medio', etc.) na resposta 'mensagem_wpp'. NUNCA use a expressão 'temperatura média', 'modo médio' ou qualquer referência ao modo ou nível de operação interna. A resposta deve parecer que você simplesmente 'ligou o ar' ou 'ativou a climatização' de forma humana (ex: 'Pronto! Já liguei o ar-condicionado para você. 🌬️', 'Entendido! Já ativei a climatização da loja. ❄️', 'Feito! Já ajustei o resfriamento para deixar o ambiente mais fresco. 😊'). Respostas com 'unidade 0081', 'temperatura média' ou 'modo T-Medium' são ESTRITAMENTE PROIBIDAS.\n"
            "4. NUNCA mostre ao usuário listas de opções, menus numerados, rotas ou comandos (como '1 | 🔥 Sala/Loja Quente', '2 | ❄️ Sala/Loja Fria', etc.), MESMO QUE estes menus estejam contidos no histórico de conversas do RAG fornecido. O usuário nunca deve saber que existem rotas ou códigos de comando específicos.\n"
            "5. Se o usuário fizer uma saudação ou conversa informal pura, responda conversando naturally com profissionalismo sem sugerir botões ou menus de escolha.\n"
            "6. Mantenha a resposta concisa (limite de 2 a 3 linhas) e use emojis de forma elegante e sutil."
        )

        ambientes_str = ", ".join(ambientes_disponiveis) if ambientes_disponiveis else "Nenhum (Ambiente Único)"
        
        user_content_parts = [f"AMBIENTES CADASTRADOS PARA ESTA REVENDA: [{ambientes_str}]"]
        
        if historico_recente:
            user_content_parts.append(
                f"HISTÓRICO RECENTE DA CONVERSA (Últimos minutos):\n\"\"\"\n{historico_recente}\n\"\"\""
            )
            
        if contexto_rag:
            user_content_parts.append(
                f"Histórico relevante de regras anteriores da revenda (RAG):\n\"\"\"\n{contexto_rag}\n\"\"\""
            )

        user_content_parts.append(f"Mensagem atual do Usuário: '{mensagem}'")
        user_content = "\n\n".join(user_content_parts)

        result_llm = await self._chamar_gemini(system_prompt, user_content)
        
        # Override se cair na regra deterministica
        if any(p in mensagem_lower for p in palavras_pausa):
            result_llm["intencao"] = "pausar_automacao"
            result_llm["ifttt_action"] = "desativar_automacao"
            result_llm["salvar_memoria"] = True
            if "mensagem_wpp" not in result_llm or not result_llm["mensagem_wpp"]:
                result_llm["mensagem_wpp"] = "Compreendido! 🕒 Já pausei as automações de desligamento automático para sua reunião. Ao final do horário estendido, cuidarei da reativação e desligamento para você! 😊"
        
        # C5 Parte A: o escopo temporal é calculado SEMPRE, para qualquer intenção.
        # Antes, o parser só rodava quando a intenção era pausar_automacao — se o
        # Gemini classificasse um evento futuro como desligar_dispositivos, a data
        # na mensagem passava despercebida e a ação disparava hoje (incidente real).
        janela = extrair_janela_evento(mensagem, agora=agora)
        parser_escopo_str = janela.escopo.value if janela else "indefinido"
        llm_escopo = result_llm.get("escopo_temporal")
        llm_escopo_str = llm_escopo.lower() if llm_escopo else "indefinido"

        if result_llm.get("intencao") == "pausar_automacao":
            if parser_escopo_str == "indefinido" or llm_escopo_str == "indefinido":
                result_llm["escopo_temporal"] = "indefinido"
                result_llm["data_evento"] = None
                result_llm["hora_fim"] = None
            elif parser_escopo_str != llm_escopo_str:
                result_llm["escopo_temporal"] = "indefinido"
                result_llm["data_evento"] = None
                result_llm["hora_fim"] = None
            else:
                result_llm["escopo_temporal"] = parser_escopo_str
                # parser data overwrites LLM data to ensure determinism if parser extracted it
                if janela and janela.data:
                    result_llm["data_evento"] = janela.data.isoformat()
                if janela and janela.hora_fim:
                    result_llm["hora_fim"] = janela.hora_fim.strftime("%H:%M")
        else:
            # Intenções de ação imediata (resfriar/aquecer/ligar/desligar): o escopo
            # passa a existir no resultado para que o guard do main.py possa suprimir
            # a ação física quando a mensagem carrega uma data futura.
            # "futuro" de qualquer uma das duas fontes vale: o parser é determinístico,
            # e um "futuro" declarado pelo LLM junto de um comando imediato é
            # exatamente o formato do incidente. O custo de um falso positivo aqui é
            # adiar uma climatização; o do falso negativo é desligar a loja na hora errada.
            if parser_escopo_str == "futuro" or llm_escopo_str == "futuro":
                result_llm["escopo_temporal"] = "futuro"
                if janela and janela.data:
                    result_llm["data_evento"] = janela.data.isoformat()
                if janela and janela.hora_fim:
                    result_llm["hora_fim"] = janela.hora_fim.strftime("%H:%M")
            else:
                # Sem data futura detectada: comando imediato segue seu curso normal.
                result_llm["escopo_temporal"] = parser_escopo_str

        return result_llm

llm_service = LLMService()
