from uuid import UUID


class ApplicationNotFoundError(LookupError):
    """Raised when an application is unavailable to the requesting user."""

    def __init__(self, application_id: UUID) -> None:
        super().__init__(f"Application {application_id} was not found.")
