# =============================================================================
# app/core/security.py - Dependências de Autenticação Compartilhadas
# =============================================================================
# Extraído de app/main.py para poder ser importado tanto pelas rotas principais
# quanto pelo router de admin (app/routers/admin.py) sem import circular.
# =============================================================================

import logging
import secrets

from fastapi import Depends, HTTPException, Request, status
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


async def verify_admin_ip_allowlist(request: Request) -> None:
    """
    Restringe qualquer rota /admin/* a uma lista de IPs de confiança, configurada
    via ADMIN_ALLOWED_IPS no .env (separados por vírgula). Mitigação temporária
    enquanto não há um proxy reverso com TLS na frente da API (ver README, seção 9).

    Lê `request.client.host` (endereço da conexão TCP real) — só é confiável em
    exposição DIRETA (sem reverse proxy no meio), que é o cenário atual. Se um
    proxy (Caddy, Nginx) for colocado na frente, esta função precisa passar a
    validar X-Forwarded-For de forma segura (só confiando nele quando a conexão
    de origem for do próprio proxy) — do contrário, qualquer cliente poderia
    forjar esse header e burlar a lista.
    """
    allowed = settings.admin_allowed_ips_list
    if not allowed:
        return  # ADMIN_ALLOWED_IPS não configurado: sem restrição adicional de IP

    client_ip = request.client.host if request.client else None
    if client_ip not in allowed:
        logger.warning(f"🔒 Acesso a rota admin bloqueado pela allowlist de IP: '{client_ip}' não está autorizado.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Acesso não permitido a partir deste endereço IP."},
        )
