"""Helper utilities to establish SQL Server connections for DAOs."""

import importlib
import os
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:  # pragma: no cover - solo se usa para tipado
    import pyodbc


class DatabaseConnectorError(RuntimeError):
    """Raised when the application is unable to open a database connection."""


class DatabaseConnector:
    """Provide SQL Server connections based on environment configuration."""

    ENV_CONNECTION_STRING = "SQLSERVER_CONNECTION_STRING"

    def __init__(self, connection_string: Optional[str] = None) -> None:
        """Store the connection string for future usage."""
        self._connection_string = connection_string or os.environ.get(self.ENV_CONNECTION_STRING)

    def _load_driver(self):
        """Import ``pyodbc`` on demand to keep the dependency optional."""
        try:
            return importlib.import_module("pyodbc")
        except ModuleNotFoundError as exc:  # pragma: no cover - depende del entorno
            raise DatabaseConnectorError(
                "No se encontró la dependencia 'pyodbc'. Instálala ejecutando 'pip install pyodbc'."
            ) from exc

    def get_connection(self) -> "pyodbc.Connection":
        """Open and return a new SQL Server connection."""
        if not self._connection_string:
            raise DatabaseConnectorError(
                "No se encontró la cadena de conexión para SQL Server. "
                "Defina SQLSERVER_CONNECTION_STRING o pase el valor explícitamente."
            )
        pyodbc = self._load_driver()
        try:
            return pyodbc.connect(self._connection_string)
        except pyodbc.Error as exc:  # pragma: no cover - depende del entorno
            raise DatabaseConnectorError("No fue posible conectarse a SQL Server.") from exc

    def connection_factory(self) -> Callable[[], "pyodbc.Connection"]:
        """Expose a callable that creates a new connection on each invocation."""
        return self.get_connection
