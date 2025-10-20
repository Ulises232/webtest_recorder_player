"""Data access object for reading user records from SQL Server."""

from contextlib import closing
from dataclasses import dataclass
from typing import Callable, Optional

import pyodbc

from app.daos.database import DatabaseConnectorError


@dataclass(slots=True)
class UserRecord:
    """Represent a single row from the users table."""

    username: str
    displayName: str
    email: Optional[str]
    active: bool
    passwordHash: Optional[str]
    passwordSalt: Optional[str]
    passwordAlgo: Optional[str]
    requirePasswordReset: bool


class UserDAOError(RuntimeError):
    """Raised when the DAO fails to fetch or parse a user record."""


class UserDAO:
    """Retrieve users from SQL Server using a provided connection factory."""

    def __init__(self, connection_factory: Callable[[], pyodbc.Connection]) -> None:
        """Store the connection factory for later usage."""
        self._connection_factory = connection_factory

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        """Return the user associated to the username or ``None`` if missing."""
        try:
            with closing(self._connection_factory()) as connection:
                with closing(connection.cursor()) as cursor:
                    cursor.execute(
                        (
                            "SELECT username, display_name, email, active, "
                            "password_hash, password_salt, password_algo, require_password_reset "
                            "FROM dbo.users WHERE username = ?"
                        ),
                        username,
                    )
                    row = cursor.fetchone()
        except (pyodbc.Error, DatabaseConnectorError) as exc:  # pragma: no cover - depende del entorno
            raise UserDAOError("No fue posible consultar el usuario en la base de datos.") from exc

        if not row:
            return None

        return UserRecord(
            username=row.username,
            displayName=row.display_name,
            email=getattr(row, "email", None),
            active=bool(row.active),
            passwordHash=getattr(row, "password_hash", None),
            passwordSalt=getattr(row, "password_salt", None),
            passwordAlgo=getattr(row, "password_algo", None),
            requirePasswordReset=bool(getattr(row, "require_password_reset", False)),
        )
