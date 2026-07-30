# =============================================================================
# app/services/llm_service.py - Classificação Semântica e IA (RAG) com Gemini
# =============================================================================

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import google.generativeai as genai
from app.config import get_settings
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """
    Serviço para gerenciar chamadas ao Google Gemini (gemini-2.5-flash) para classificação
    semântica de comandos de temperatura/IoT e conversação amigável.
    """

    def __init__(self):
        # Configura o SDK Gemini de forma preguiçosa caso a chave esteja presente
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

    async def processar_mensagem(self, mensagem: str, id_grupo: str, ambientes_disponiveis: list[str] = None) -> Dict[str, Any]:
        """
        Consulta o RAG por histórico contextual, envia a pergunta + contexto ao gemini-2.5-flash
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

        # 1. Recupera contexto relevante do RAG (histórico de chat)
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
            "2. Se o usuário estiver com CALOR, disser que a sala está quente, abafada, pedir para esfriar/gelar, ou enviar comandos como 'tlow', 't-low' ou 'freezer':\n"
            "   - 'intencao': 'ligar_resfriamento'\n"
            "   - 'ifttt_action': 'freezer'\n"
            "3. Se o usuário estiver com FRIO, disser que a sala está gelada/fria, pedir para esquentar/aquecer, ou enviar comandos como 'thigh' ou 't-high':\n"
            "   - 'intencao': 'ligar_aquecimento'\n"
            "   - 'ifttt_action': 'esquentar'\n"
            "4. Se o usuário pedir para deixar numa temperatura média, agradável, primeiro calor, ou enviar comandos como 'tmedium' ou 't-medium':\n"
            "   - 'intencao': 'ligar_temperatura_media'\n"
            "   - 'ifttt_action': 'medio'\n"
            "5. Se o usuário pedir para desligar as máquinas/equipamentos, informar que a revenda está fechada/fechando, ou enviar comandos como 'toff' ou 't-off':\n"
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
            "1. O campo 'mensagem_wpp' deve ser natural, educado e amigável.\n"
            "2. NUNCA mostre ao usuário listas de opções, menus numerados, rotas ou comandos (como '1 | 🔥 Sala/Loja Quente', '2 | ❄️ Sala/Loja Fria', etc.), MESMO QUE estes menus estejam contidos no histórico de conversas do RAG fornecido. O usuário nunca deve saber que existem rotas ou códigos de comando específicos.\n"
            "3. Se o usuário fizer uma saudação ou conversa informal, responda conversando naturalmente sem sugerir botões ou menus de escolha.\n"
            "4. Mantenha a resposta concisa (limite de 2 a 3 linhas) e use emojis de forma sutil."
        )

        # 3. Constrói o Prompt do Usuário com o contexto RAG e Ambientes
        ambientes_str = ", ".join(ambientes_disponiveis) if ambientes_disponiveis else "Nenhum (Ambiente Único)"
        
        user_content = f"AMBIENTES CADASTRADOS PARA ESTA REVENDA: [{ambientes_str}]\n\nMensagem do Usuário: '{mensagem}'"
        if contexto_rag:
            user_content = (
                f"AMBIENTES CADASTRADOS PARA ESTA REVENDA: [{ambientes_str}]\n\n"
                f"Histórico relevante de conversas anteriores da revenda:\n"
                f"\"\"\"\n{contexto_rag}\n\"\"\"\n\n"
                f"Mensagem atual do Usuário: '{mensagem}'"
            )

        logger.info(f"   Enviando requisição ao gemini-2.5-flash...")

        # 4. Envia para a API do Gemini de forma assíncrona usando GenerativeModel
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt
        )
        response = await model.generate_content_async(
            user_content,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0,
                max_output_tokens=1000
            )
        )

        content = response.text
        logger.info(f"   Resposta do Gemini recebida com sucesso.")
        
        # 5. Converte o JSON string para dict do Python
        dados_resposta = json.loads(content)
        return dados_resposta


# Instância única para importação
llm_service = LLMService()

