# =============================================================================
# app/schemas/admin.py - Modelos Pydantic do Painel Administrativo
# =============================================================================

from typing import Optional

from pydantic import BaseModel, Field


class ToggleRequest(BaseModel):
    """Payload de POST /admin/revendas/{id_grupo}/toggle."""
    ativo: bool


class DispararAcaoRequest(BaseModel):
    """
    Payload de POST /admin/revendas/{id_grupo}/disparar.

    Permite ao operador do painel disparar manualmente a mesma ação física
    que a Sofia dispararia a partir de uma mensagem de WhatsApp.
    """
    acao: str = Field(
        ...,
        description="freezer | esquentar | medio | off | ligar | desativar_automacao",
        examples=["freezer", "desativar_automacao"],
    )
    ambiente: Optional[str] = Field(
        default=None,
        description="Ambiente/sala a controlar. Deixe vazio para lojas de ambiente único.",
    )
    duracao_horas: float = Field(
        default=2.0,
        gt=0,
        description="Só usada quando acao='desativar_automacao': por quantas horas a automação fica pausada antes da reativação automática.",
    )


class AtualizarMapeamentoRequest(BaseModel):
    """Payload de PATCH /admin/revendas/{id_grupo}/mapeamento."""
    tuya_home_id: str = Field(..., min_length=1, description="Novo tuya_home_id a vincular à revenda.")


class CenaUpsertRequest(BaseModel):
    """Payload de POST /admin/tuya/cenas (cria ou atualiza por scene_id)."""
    home_id: str
    sigla_cliente: str
    ambiente: str
    scene_id: str
    nome_cena: str
    acao: str
