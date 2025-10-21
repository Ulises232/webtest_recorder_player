"""Data access object for reading user records from SQL Server."""

import importlib
from contextlib import closing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional, Tuple, Type

if TYPE_CHECKING:  # pragma: no cover - solo para tipado
    import pymssql

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

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the connection factory for later usage."""
        self._connection_factory = connection_factory

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        """Return the user associated to the username or ``None`` if missing."""
        error_types: Tuple[Type[BaseException], ...] = (DatabaseConnectorError,)
        try:
            pymssql = importlib.import_module("pymssql")
        except ModuleNotFoundError:
            pymssql = None
        else:
            error_types = (DatabaseConnectorError, pymssql.Error)

        try:
            with closing(self._connection_factory()) as connection:
                with closing(connection.cursor(as_dict=True)) as cursor:
                    cursor.execute(
                        (
                            "SELECT username, display_name, email, active, "
                            "password_hash, password_salt, password_algo, require_password_reset "
                            "FROM dbo.users WHERE username = %s"
                        ),
                        (username,),
                    )
                    row = cursor.fetchone()
        except error_types as exc:  # pragma: no cover - depende del entorno
            raise UserDAOError("No fue posible consultar el usuario en la base de datos.") from exc

        if not row:
            return None

        return UserRecord(
            username=row.get("username"),
            displayName=row.get("display_name"),
            email=row.get("email"),
            active=bool(row.get("active", False)),
            passwordHash=row.get("password_hash"),
            passwordSalt=row.get("password_salt"),
            passwordAlgo=row.get("password_algo"),
            requirePasswordReset=bool(row.get("require_password_reset", False)),
        )
