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
