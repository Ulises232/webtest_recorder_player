"""Data transfer objects describing authentication responses."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AuthenticationStatus(str, Enum):
    """Enumerate the possible outcomes of a login attempt."""

    AUTHENTICATED = "authenticated"
    INVALID_CREDENTIALS = "invalid_credentials"
    INACTIVE = "inactive"
    PASSWORD_REQUIRED = "password_required"
    RESET_REQUIRED = "reset_required"
    ERROR = "error"


@dataclass(slots=True)
class AuthenticationResult:
    """Represent the result of an authentication attempt."""

    status: AuthenticationStatus
    message: str
    username: Optional[str] = None
    displayName: Optional[str] = None
