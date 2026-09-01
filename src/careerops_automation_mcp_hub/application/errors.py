from uuid import UUID


class ApplicationNotFoundError(LookupError):
    """Raised when an application is unavailable to the requesting user."""

    def __init__(self, application_id: UUID) -> None:
        super().__init__(f"Application {application_id} was not found.")


class AgentEngineError(RuntimeError):
    """Base error for Agent Engine integration failures."""


class AgentEngineUnavailableError(AgentEngineError):
    """Raised when the Agent Engine cannot service a request."""


class AgentEngineAuthenticationError(AgentEngineError):
    """Raised when the Agent Engine rejects service authentication."""


class AgentEngineValidationError(AgentEngineError):
    """Raised when the Agent Engine rejects request semantics."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class AgentEngineAnalysisNotFoundError(AgentEngineError):
    """Raised when a requested Agent Engine analysis is unavailable."""


class AgentEngineContractError(AgentEngineError):
    """Raised when the Agent Engine returns an invalid API contract."""


class AgentEngineRequestError(AgentEngineError):
    """Raised for an unexpected Agent Engine HTTP response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Agent Engine returned unexpected HTTP status {status_code}.")


class ApplicationReviewBlockedError(RuntimeError):
    """Raised when another unresolved review makes a new submission unsafe."""


class ApplicationAnalysisUnavailableError(LookupError):
    """Raised when an application has no recoverable Agent Engine analysis."""

    def __init__(self, application_id: UUID) -> None:
        super().__init__(
            f"Application {application_id} does not have a recoverable analysis."
        )
