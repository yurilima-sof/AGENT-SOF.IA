# =============================================================================
# app/schemas/agent.py - Modelos Pydantic para o Endpoint /agent
# =============================================================================
# Pydantic é a biblioteca que o FastAPI usa para validar dados automaticamente.
#
# CONCEITO CHAVE para o estagiário:
#   Pydantic Models são como "contratos" de dados. Quando o n8n enviar um
#   JSON para nossa API, o FastAPI usará estes modelos para:
#   1. Validar se todos os campos obrigatórios estão presentes.
#   2. Verificar se os tipos estão corretos (str, int, dict, etc.).
#   3. Converter automaticamente (ex: string "22" vira int 22).
#   4. Gerar documentação automática no Swagger UI (/docs).
#
# Se o JSON vier inválido, o FastAPI retorna automaticamente um erro 422
# com uma mensagem clara explicando o problema. Zero código extra!
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


# =============================================================================
# REQUEST MODEL (Entrada) - O que o n8n vai nos enviar
# =============================================================================

class AgentRequest(BaseModel):
    """
    Schema de entrada do endpoint POST /agent.

    Representa o payload que o n8n envia para nossa API após receber
    uma mensagem do WhatsApp e identificar a qual revenda ela pertence.

    Exemplo de payload JSON:
    {
        "mensagem": "liga o ar da recepção",
        "id_grupo": "12345-6789@g.us",
        "nome_revenda": "Revenda Alpha"
    }
    """

    mensagem: str = Field(
        ...,  # O "..." significa que este campo é OBRIGATÓRIO.
        description="Mensagem original enviada pelo usuário no WhatsApp.",
        min_length=1,
        max_length=4096,  # Limite de caracteres do WhatsApp.
        examples=["liga o ar da recepção", "desliga todas as luzes"],
    )

    id_grupo: str = Field(
        ...,
        description="ID do grupo WhatsApp, no formato XXXXXXXXXXX@g.us.",
        examples=["12345-6789@g.us", "55119999XXXX-XXXXXXXXXX@g.us"],
    )

    nome_revenda: str = Field(
        ...,
        description="Nome da revenda proprietária do grupo, consultado previamente pelo n8n.",
        examples=["Revenda Alpha", "Clima Tech Solutions"],
    )

    # Configurações do modelo Pydantic v2.
    model_config = {
        # Gera um exemplo no Swagger UI automaticamente.
        "json_schema_extra": {
            "examples": [
                {
                    "mensagem": "liga o ar da recepção",
                    "id_grupo": "12345-6789@g.us",
                    "nome_revenda": "Revenda Alpha",
                }
            ]
        }
    }


# =============================================================================
# RESPONSE MODEL (Saída) - O que nossa API vai devolver ao n8n
# =============================================================================

class AgentResponse(BaseModel):
    """
    Schema de saída do endpoint POST /agent.

    Representa o JSON estruturado que nossa API retorna ao n8n.
    O n8n usa esses dados para:
    - Executar o comando correto na API Tuya (intencao + dispositivo_id + parametros).
    - Enviar a mensagem de confirmação de volta ao WhatsApp (mensagem_wpp).

    Exemplo de resposta JSON:
    {
        "intencao": "ligar_dispositivo",
        "dispositivo_id": "xyz123",
        "parametros": {"temperatura": 22},
        "mensagem_wpp": "Claro, ligando o ar da recepção em 22 graus."
    }
    """

    intencao: str = Field(
        ...,
        description=(
            "Intenção identificada pelo agente de IA. "
            "Valores possíveis: ligar_dispositivo | desligar_dispositivo | "
            "ajustar_temperatura | consultar_status | intencao_nao_identificada"
        ),
        examples=["ligar_dispositivo", "desligar_dispositivo", "consultar_status"],
    )

    dispositivo_id: Optional[str] = Field(
        default=None,
        description=(
            "ID do dispositivo Tuya a ser controlado. "
            "Será None quando a intenção não envolve um dispositivo específico "
            "(ex: saudação, erro de compreensão)."
        ),
        examples=["xyz123abc", "tuya_device_456"],
    )

    ifttt_action: Optional[str] = Field(
        default=None,
        description=(
            "[FASE DE TESTES] Ação a ser disparada no IFTTT. "
            "Valores possíveis: 'freezer' (esfriar) | 'esquentar' | 'off' | None (sem ação física). "
            "O n8n usa este campo para buscar a URL correta no mapa de grupos "
            "enquanto não migramos para a API Tuya direta."
        ),
        examples=["freezer", "esquentar", "off", None],
    )

    link_ifttt: Optional[str] = Field(
        default=None,
        description=(
            "[FASE DE TESTES] URL do webhook IFTTT correspondente à ação. "
            "Retornado para o n8n poder executar o webhook diretamente na fase de testes."
        ),
        examples=["https://maker.ifttt.com/trigger/..."],
    )

    parametros: Dict[str, Any] = Field(
        default_factory=dict,  # Valor padrão: dicionário vazio {}.
        description=(
            "Parâmetros adicionais para o comando Tuya. "
            "O conteúdo varia conforme a intenção. "
            "Exemplos: {'temperatura': 22}, {'brilho': 80}, {}"
        ),
        examples=[{"temperatura": 22}, {"brilho": 80}, {}],
    )

    mensagem_wpp: str = Field(
        ...,
        description=(
            "Mensagem de resposta amigável para ser enviada de volta ao usuário "
            "pelo WhatsApp. Deve ser clara, concisa e em português do Brasil."
        ),
        examples=[
            "Claro, ligando o ar da recepção em 22 graus. ❄️",
            "Desligando todas as luzes do escritório. ✅",
        ],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "intencao": "ligar_dispositivo",
                    "dispositivo_id": "xyz123",
                    "parametros": {"temperatura": 22},
                    "mensagem_wpp": "Claro, ligando o ar da recepção em 22 graus. ❄️",
                }
            ]
        }
    }


# =============================================================================
# MODELO DE ERRO PADRONIZADO
# =============================================================================

class ErrorResponse(BaseModel):
    """
    Schema padronizado para respostas de erro da API.

    Retornado nos casos de falha para que o n8n possa
    tratar o erro de forma programática.
    """

    error: str = Field(..., description="Código do erro em snake_case.", examples=["internal_server_error"])
    message: str = Field(..., description="Descrição legível do erro.", examples=["Erro interno ao processar a requisição."])
    detail: Optional[Any] = Field(default=None, description="Detalhes adicionais do erro (para debug).")
