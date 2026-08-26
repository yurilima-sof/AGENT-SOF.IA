# =============================================================================
# app/services/llm_service.py - Classificação Semântica e IA (RAG) com Gemini
# =============================================================================

import json
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime

import google.generativeai as genai
from app.config import get_settings
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
settings = get_settings()


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
        # Configura o SDK Gemini de forma preguiçosa caso a chave esteja presente
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

    async def processar_mensagem(
        self,
        mensagem: str,
        id_grupo: str,
        ambientes_disponiveis: list[str] = None,
        historico_recente: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Consulta o RAG por histórico contextual, analisa histórico de curto prazo, envia a pergunta + contexto ao gemini-2.5-flash
        e retorna a classificação estruturada no formato compatível com AgentResponse.
        """
        # 0. Verificação Determinística de Pausa de Automação / Reunião / Fechamento de Mês
        mensagem_lower = mensagem.lower()
        palavras_pausa = ["reunião", "reuniao", "fechamento de mês", "fechamento de mes", "não desliga", "nao desliga", "pausar automação", "pausar automacao"]
        if any(p in mensagem_lower for p in palavras_pausa):
            logger.info(f"   [LLM] Regra determinística de Pausa de Automação / Reunião ativada para mensagem: '{mensagem}'")
            return {
                "intencao": "pausar_automacao",
                "ifttt_action": "desativar_automacao",
                "ambiente": None,
                "mensagem_wpp": "Compreendido! 🕒 Já pausei as automações de desligamento automático para sua reunião. Ao final do horário estendido, cuidarei da reativação e desligamento para você! 😊",
                "salvar_memoria": True
            }

        # 1. Recupera contexto relevante do RAG (histórico de longo prazo)
        contexto_rag = ""
        try:
            contexto_rag = await rag_service.get_relevant_context(mensagem, id_grupo)
            if contexto_rag:
                logger.info(f"   Contexto RAG recuperado para a mensagem.")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao recuperar contexto do RAG: {e}")

        # Pega a data atual para o LLM gerar o log corretamente
        data_atual_str = datetime.now().strftime("%d/%m/%y")

        # 2. Define o Prompt do Sistema (System Prompt)
        system_prompt = (
            "Você é a Sofia, a assistente inteligente da SOF para controle de temperatura. "
            "Sempre aja com essa persona: feminina, amigável, acolhedora, prestativa e altamente eficiente. "
            "Sua tarefa é analisar a mensagem do usuário no WhatsApp e decidir qual ação física IoT tomar e "
            "gerar uma resposta amigável.\n\n"
            
            f"INFORMAÇÃO DE TEMPO ATUAL: A data de hoje é {data_atual_str}.\n\n"

            "Você deve responder EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:\n"
            "{\n"
            "  \"intencao\": \"ligar_resfriamento\" | \"ligar_aquecimento\" | \"ligar_temperatura_media\" | \"desligar_dispositivos\" | \"ligar_dispositivos\" | \"pausar_automacao\" | \"sem_acao\",\n"
            "  \"ifttt_action\": \"freezer\" | \"esquentar\" | \"medio\" | \"off\" | \"ligar\" | \"desativar_automacao\" | null,\n"
            "  \"ambiente\": \"nome do ambiente (slug) ou null\",\n"
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
            "   - 1º CHAMADO (Nenhum chamado de resfriamento recente no histórico): OBRIGATORIAMENTE acione `ifttt_action: \"medio\"`, `intencao: \"ligar_temperatura_media\"`. Responda amigavelmente informando que iniciou a climatização em temperatura média.\n"
            "   - 2º CHAMADO (Já existe 1 chamado prévio de resfriamento recente no histórico): OBRIGATORIAMENTE acione `ifttt_action: \"freezer\"`, `intencao: \"ligar_resfriamento\"`. Responda informando que intensificou o resfriamento para deixar o ambiente mais fresco.\n"
            "   - 3º CHAMADO OU MAIS (Já existem 2 ou mais chamados prévios no histórico): OBRIGATORIAMENTE acione `ifttt_action: \"freezer\"`, `intencao: \"ligar_resfriamento\"`. Responda informando que ativou o resfriamento máximo para gelar o ambiente rapidamente.\n"
            "2. EXCEÇÃO EXPLÍCITA: Se a mensagem do usuário solicitar EXPLICITAMENTE uma temperatura específica (ex: 'põe no medio', 'gelar no máximo'), RESPEITE o comando direto do usuário imediatamente.\n\n"

            "REGRA DE SOBREPOSIÇÃO ABSOLUTA (PRIORIDADE CRÍTICA):\n"
            "Se a mensagem ATUAL do usuário mencionar REUNIÃO (ex: 'vamos ter reunião', 'reunião até as 20h', 'reunião na sala de testes'), FECHAMENTO DE MÊS ou solicitar para 'não desligar o ar até Xh' / pausar automações:\n"
            "- A intenção OBRIGATORIAMENTE DEVE SER: `pausar_automacao`\n"
            "- O ifttt_action OBRIGATORIAMENTE DEVE SER: `desativar_automacao`\n"
            "- A flag salvar_memoria OBRIGATORIAMENTE DEVE SER: `true`\n"
            "- IGNORE qualquer comando antigo ou histórico do RAG que tenha associado essas palavras a 'freezer' ou 'ligar_resfriamento'.\n\n"

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
            "3. NUNCA mencione códigos internos, nomes técnicos de comandos ou modos do sistema (como 'T-Low', 'T-Medium', 'T-Freezer', 'T-High', 'T-Off', 'freezer', 'esquentar', 'medio', etc.) na resposta 'mensagem_wpp'. Fale sempre em linguagem humana e acolhedora (ex: 'já liguei o ar na temperatura média', 'intensifiquei o resfriamento para deixar a sala mais fresca').\n"
            "4. NUNCA mostre ao usuário listas de opções, menus numerados, rotas ou comandos (como '1 | 🔥 Sala/Loja Quente', '2 | ❄️ Sala/Loja Fria', etc.), MESMO QUE estes menus estejam contidos no histórico de conversas do RAG fornecido. O usuário nunca deve saber que existem rotas ou códigos de comando específicos.\n"
            "5. Se o usuário fizer uma saudação ou conversa informal pura, responda conversando naturalmente com profissionalismo sem sugerir botões ou menus de escolha.\n"
            "6. Mantenha a resposta concisa (limite de 2 a 3 linhas) e use emojis de forma elegante e sutil."
        )

        # 3. Constrói o Prompt do Usuário com o contexto RAG, Ambientes e Histórico Recente de Curto Prazo
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

        # 4. Envia para a API do Gemini (Solução Definitiva - Direta e sem Loop)
        m_name = getattr(settings, 'gemini_model', 'gemini-3.6-flash')
        logger.info(f"   [Gemini] Iniciando requisição direta ao modelo {m_name}...")

        try:
            try:
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction=system_prompt
                )
                
                response = await model.generate_content_async(
                    user_content,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.0,
                        max_output_tokens=2048
                    )
                )
            except Exception as e_sys:
                logger.warning(f"⚠️ Chamada com system_instruction falhou ({e_sys}). Tentando modo de prompt unificado...")
                model = genai.GenerativeModel(model_name=m_name)
                full_prompt = f"{system_prompt}\n\n{user_content}"
                response = await model.generate_content_async(
                    full_prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.0,
                        max_output_tokens=2048
                    )
                )

            if not response or not response.text:
                raise ValueError("Resposta vazia da API do Gemini.")

            logger.info(f"✅ Resposta do Gemini obtida com sucesso usando {m_name}.")

            # 5. Converte o JSON string para dict do Python, com reparos em cascata
            # para os padrões de malformação mais comuns (ver _parse_and_repair_json).
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

            # FALLBACK DE SEGURANÇA PARA PRODUÇÃO
            return {
                "intencao": "sem_acao",
                "ifttt_action": None,
                "ambiente": None,
                "mensagem_wpp": "Puxa, estou passando por uma instabilidade técnica rápida aqui no meu sistema. Pode tentar novamente em alguns minutos? 🛠️",
                "salvar_memoria": False
            }


# Instância única para importação
llm_service = LLMService()

