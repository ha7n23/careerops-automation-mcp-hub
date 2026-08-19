from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken


@dataclass(frozen=True, slots=True)
class Principal:
    """Trusted identity used to scope CareerOps operations."""

    user_id: str
    actor_id: str

    def __post_init__(self) -> None:
        user_id = self.user_id.strip()
        actor_id = self.actor_id.strip()

        if not user_id:
            raise ValueError("user_id must not be blank.")

        if not actor_id:
            raise ValueError("actor_id must not be blank.")

        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "actor_id", actor_id)


class PrincipalProvider(Protocol):
    """Provide the trusted principal for the current MCP operation."""

    def get_principal(self) -> Principal:
        """Return the principal associated with the current operation."""
        ...


class PrincipalUnavailableError(RuntimeError):
    """Raised when no trusted MCP principal can be established."""


@dataclass(frozen=True, slots=True)
class StaticPrincipalProvider:
    """Provide one trusted principal for local and in-memory runtimes."""

    principal: Principal

    def get_principal(self) -> Principal:
        return self.principal


@dataclass(frozen=True, slots=True)
class AccessTokenPrincipalProvider:
    """Build a CareerOps principal from the authenticated MCP access token."""

    token_getter: Callable[[], AccessToken | None] = get_access_token

    def get_principal(self) -> Principal:
        token = self.token_getter()

        if token is None:
            raise PrincipalUnavailableError(
                "No authenticated MCP access token is available."
            )

        subject = token.subject.strip() if token.subject is not None else ""

        if not subject:
            raise PrincipalUnavailableError(
                "Authenticated MCP token does not identify a subject."
            )

        client_id = token.client_id.strip()

        if not client_id:
            raise PrincipalUnavailableError(
                "Authenticated MCP token does not identify a client."
            )

        return Principal(
            user_id=subject,
            actor_id=client_id,
        )
