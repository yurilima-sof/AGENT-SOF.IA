# =============================================================================
# app/core/exceptions.py - Hierarquia de Exceções de Domínio do Agente SOF
# =============================================================================

class AgenteSofError(Exception):
    """Exceção base para todos os erros de domínio da aplicação."""
    pass

class ConfigError(AgenteSofError):
    """Falha fatal de configuração no momento do boot. Deve impedir a aplicação de subir."""
    pass

class DegradableError(AgenteSofError):
    """
    Exceção para capacidade opcional que falhou mas permite degradação graciosa.
    Registra log/métrica e prossegue com estratégia conservadora.
    """
    capability: str = "unknown"

    def __init__(self, message: str, capability: str = None):
        super().__init__(message)
        if capability:
            self.capability = capability

class RagUnavailable(DegradableError):
    capability = "rag"

class ShortTermMemoryUnavailable(DegradableError):
    capability = "chat_history"

class LlmUnavailable(DegradableError):
    capability = "llm"

class FatalError(AgenteSofError):
    """Exceção fatal para a requisição. Degradar aqui produziria ação incorreta."""
    pass

class TenantResolutionError(FatalError):
    """Falha ao resolver a revenda/tenant. Jamais deve degradar."""
    pass

class SchedulePersistError(FatalError):
    """Falha ao persistir agendamento. Impede o bot de prometer reativação."""
    pass

class AuditLogWriteFailed(AgenteSofError):
    """Falha ao gravar log de auditoria."""
    pass

class TuyaError(AgenteSofError):
    """Erro genérico de comunicação com a API Tuya."""
    pass

class TuyaAuthError(TuyaError):
    """Credenciais Tuya inválidas ou expiradas."""
    pass

class TuyaTransientError(TuyaError):
    """Erro temporário da API Tuya (HTTP 5xx / Timeout). Requer retry."""
    pass

class TuyaDeviceOffline(TuyaError):
    """Dispositivos IR físicos da revenda estão offline."""
    pass
