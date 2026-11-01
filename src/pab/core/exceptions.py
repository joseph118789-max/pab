"""PAB Exception hierarchy."""

class PABError(Exception):
    """Base exception for PersonaOS Agent Bridge."""
    pass

class ProviderNotFoundError(PABError):
    """Raised when a requested provider is not found or installed."""
    pass

class ProviderExecutionError(PABError):
    """Raised when a native provider CLI command fails."""
    pass

class AgentValidationError(PABError):
    """Raised when an agent schema fails validation."""
    pass

class AgentNotFoundError(PABError):
    """Raised when an agent ID does not exist."""
    pass

class SkillValidationError(PABError):
    """Raised when a skill manifest or structure is invalid."""
    pass

class SecurityViolationError(PABError):
    """Raised when a security policy or path restriction is violated."""
    pass

class SyncConflictError(PABError):
    """Raised when a synchronisation plan encounters unresolved conflicts."""
    pass

class UnsupportedOperationError(PABError):
    """Raised when a requested operation is not supported by the provider adapter."""
    pass

class DuplicateExecutionError(PABError):
    """Raised when a duplicate execution request violates idempotency constraints."""
    pass

class ExecutionNotFoundError(PABError):
    """Raised when a referenced execution ID does not exist in the supervisor."""
    pass

class StaleGenerationError(PABError):
    """Raised when an event or action references an outdated execution generation."""
    pass
