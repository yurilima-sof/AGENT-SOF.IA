# =============================================================================
# app/core/security.py - Dependências de Autenticação Compartilhadas
# =============================================================================
# Extraído de app/main.py para poder ser importado tanto pelas rotas principais
# quanto pelo router de admin (app/routers/admin.py) sem import circular.
# =============================================================================

import logging
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_bearer_scheme = HTTPBearer(
    description="Chave de autenticação da API. Envie no formato: Bearer <API_KEY>",
)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    Dependência FastAPI que valida a API Key do header Authorization.

    Retorna a chave validada ou lança HTTP 401 se inválida.
    Usa comparação timing-safe para evitar ataques de side-channel.
    """
    if not secrets.compare_digest(credentials.credentials, settings.api_key):
        logger.warning("🔒 Tentativa de acesso com API Key inválida.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "API Key inválida ou ausente."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def verify_admin_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    Valida a API Key do Admin.
    """
    if not secrets.compare_digest(credentials.credentials, settings.admin_api_key):
        logger.warning("🔒 Tentativa de acesso ADMIN com API Key inválida.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Admin API Key inválida."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
