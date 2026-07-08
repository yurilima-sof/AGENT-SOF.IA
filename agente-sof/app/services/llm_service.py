# =============================================================================
# app/services/llm_service.py - Classificação Semântica e IA (RAG) com Gemini
# =============================================================================

import json
import logging
from typing import Optional, Dict, Any

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

    async def processar_mensagem(self, mensagem: str, id_grupo: str) -> Dict[str, Any]:
        """
        Consulta o RAG por histórico contextual, envia a pergunta + contexto ao gemini-2.5-flash
        e retorna a classificação estruturada no formato compatível com AgentResponse.
        """
        pass

        # 1. Recupera contexto relevante do RAG (histórico de chat)
        contexto_rag = ""
        try:
            contexto_rag = await rag_service.get_relevant_context(mensagem, id_grupo)
            if contexto_rag:
                logger.info(f"   Contexto RAG recuperado para a mensagem.")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao recuperar contexto do RAG: {e}")

        # 2. Define o Prompt do Sistema (System Prompt)
        system_prompt = (
            "Você é o Bot SOF, um assistente inteligente de controle de temperatura e dispositivos IoT. "
            "Sua tarefa é analisar a mensagem do usuário no WhatsApp e decidir qual ação física IoT tomar, "
            "além de gerar uma resposta amigável e concisa em português do Brasil.\n\n"
            
            "Você deve responder EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:\n"
            "{\n"
            "  \"intencao\": \"ligar_resfriamento\" | \"ligar_aquecimento\" | \"ligar_temperatura_media\" | \"desligar_dispositivos\" | \"ligar_dispositivos\" | \"sem_acao\",\n"
            "  \"ifttt_action\": \"freezer\" | \"esquentar\" | \"medio\" | \"off\" | \"ligar\" | null,\n"
            "  \"mensagem_wpp\": \"Sua resposta amigável para o WhatsApp\"\n"
            "}\n\n"
            
            "Regras de Decisão Semântica:\n"
            "1. Se o usuário estiver com CALOR, disser que a sala está quente, abafada ou pedir para esfriar/gelar:\n"
            "   - 'intencao': 'ligar_resfriamento'\n"
            "   - 'ifttt_action': 'freezer'\n"
            "2. Se o usuário estiver com FRIO, disser que a sala está gelada/fria ou pedir para esquentar/aquecer:\n"
            "   - 'intencao': 'ligar_aquecimento'\n"
            "   - 'ifttt_action': 'esquentar'\n"
            "3. Se o usuário pedir para deixar numa temperatura média, agradável, ou primeiro calor:\n"
            "   - 'intencao': 'ligar_temperatura_media'\n"
            "   - 'ifttt_action': 'medio'\n"
            "4. Se o usuário pedir para desligar as máquinas/equipamentos, ou informar que a revenda está fechada/fechando:\n"
            "   - 'intencao': 'desligar_dispositivos'\n"
            "   - 'ifttt_action': 'off'\n"
            "5. Se o usuário pedir para ligar as máquinas/equipamentos/ar-condicionado de forma geral (sem especificar calor/frio):\n"
            "   - 'intencao': 'ligar_dispositivos'\n"
            "   - 'ifttt_action': 'ligar'\n"
            "6. Qualquer outra conversa (saudações, agradecimentos, perguntas gerais):\n"
            "   - 'intencao': 'sem_acao'\n"
            "   - 'ifttt_action': null\n\n"
            
            "Diretrizes Críticas para a resposta no campo 'mensagem_wpp':\n"
            "1. O campo 'mensagem_wpp' deve ser natural, educado e amigável.\n"
            "2. NUNCA mostre ao usuário listas de opções, menus numerados, rotas ou comandos (como '1 | 🔥 Sala/Loja Quente', '2 | ❄️ Sala/Loja Fria', etc.), MESMO QUE estes menus estejam contidos no histórico de conversas do RAG fornecido. O usuário nunca deve saber que existem rotas ou códigos de comando específicos.\n"
            "3. Se o usuário fizer uma saudação ou conversa informal, responda conversando naturalmente sem sugerir botões ou menus de escolha.\n"
            "4. Mantenha a resposta concisa (limite de 2 a 3 linhas) e use emojis de forma sutil."
        )

        # 3. Constrói o Prompt do Usuário com o contexto RAG
        user_content = f"Mensagem do Usuário: '{mensagem}'"
        if contexto_rag:
            user_content = (
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
                temperature=0.0
            )
        )

        content = response.text
        logger.info(f"   Resposta do Gemini recebida com sucesso.")
        
        # 5. Converte o JSON string para dict do Python
        dados_resposta = json.loads(content)
        return dados_resposta


# Instância única para importação
llm_service = LLMService()

