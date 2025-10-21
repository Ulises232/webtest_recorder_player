"""Helper utilities to establish SQL Server connections for DAOs."""

import importlib
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

if TYPE_CHECKING:  # pragma: no cover - solo se usa para tipado
    import pymssql

from app.config.database_config import DatabaseConfiguration

class DatabaseConnectorError(RuntimeError):
    """Raised when the application is unable to open a database connection."""


class DatabaseConnector:
    """Provide SQL Server connections based on environment configuration."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        configuration: Optional[DatabaseConfiguration] = None,
    ) -> None:
        """Store the connection string for future usage.

        Args:
            connection_string: Optional explicit connection string overriding the
                environment resolution.
            configuration: Optional configuration helper used to resolve the
                connection string and backend from environment variables.
        """

        self._configuration = configuration or DatabaseConfiguration()
        resolved = connection_string if connection_string is not None else self._configuration.get_connection_string()
        self._connection_string = resolved.strip() if isinstance(resolved, str) and resolved.strip() else None

    def _load_driver(self) -> Any:
        """Import ``pymssql`` on demand to keep the dependency optional."""
        try:
            return importlib.import_module("pymssql")
        except ModuleNotFoundError as exc:  # pragma: no cover - depende del entorno
            raise DatabaseConnectorError(
                "No se encontró la dependencia 'pymssql'. Instálala ejecutando 'pip install pymssql==2.3.8'."
            ) from exc

    def _build_connection_kwargs(self, raw_connection: str) -> Dict[str, Any]:
        """Translate a connection string into arguments understood by ``pymssql``."""
        params: Dict[str, Any] = {}

        if "://" in raw_connection:
            parsed = urlparse(raw_connection)
            if parsed.hostname:
                params["server"] = parsed.hostname
            if parsed.port:
                params["port"] = parsed.port
            if parsed.username:
                params["user"] = unquote(parsed.username)
            if parsed.password:
                params["password"] = unquote(parsed.password)
            database = parsed.path.lstrip("/")
            if database:
                params["database"] = database
            query_params = parse_qs(parsed.query, keep_blank_values=True)
            for key, value in query_params.items():
                if not value:
                    continue
                normalized = key.lower()
                candidate = value[0]
                if normalized in {"timeout", "login_timeout", "port"}:
                    try:
                        params[normalized if normalized != "port" else "port"] = int(candidate)
                    except ValueError:  # pragma: no cover - depende del formato recibido
                        continue
                elif normalized in {"charset", "appname"}:
                    params[normalized] = candidate
            return params

        key_map = {
            "server": {"server", "data source", "addr", "address", "network address", "host"},
            "database": {"database", "initial catalog"},
            "user": {"user id", "uid", "user", "username"},
            "password": {"password", "pwd"},
            "port": {"port"},
            "timeout": {"timeout"},
            "login_timeout": {"login timeout"},
            "charset": {"charset"},
            "appname": {"app", "appname", "application name"},
        }

        tokens = [segment.strip() for segment in raw_connection.split(";") if segment.strip()]
        normalized_pairs: Dict[str, str] = {}
        for token in tokens:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            normalized_pairs[key.strip().lower()] = value.strip()

        for target_key, aliases in key_map.items():
            for alias in aliases:
                if alias not in normalized_pairs:
                    continue
                raw_value = normalized_pairs[alias]
                if target_key in {"port", "timeout", "login_timeout"}:
                    try:
                        params[target_key] = int(raw_value)
                    except ValueError:  # pragma: no cover - depende del formato recibido
                        pass
                else:
                    params[target_key] = raw_value
                break

        return params

    def get_connection(self) -> "pymssql.Connection":
        """Open and return a new SQL Server connection."""
        if not self._configuration.is_sqlserver_backend():
            raise DatabaseConnectorError(
                "El backend configurado no apunta a SQL Server. Ajusta BRANCH_HISTORY_BACKEND=sqlserver para usar esta conexión.",
            )
        if not self._connection_string:
            raise DatabaseConnectorError(
                "No se encontró la cadena de conexión para SQL Server. "
                "Define SQLSERVER_CONNECTION_STRING o BRANCH_HISTORY_DB_URL en el entorno o en el archivo .env.",
            )
        pymssql = self._load_driver()
        connection_kwargs = self._build_connection_kwargs(self._connection_string)
        if not connection_kwargs:
            raise DatabaseConnectorError(
                "La cadena de conexión no tiene un formato compatible con pymssql. "
                "Utiliza pares clave-valor (Server, Database, User Id, Password, Port) o una URL mssql://usuario:contraseña@host/db."
            )
        try:
            return pymssql.connect(**connection_kwargs)
        except pymssql.Error as exc:  # pragma: no cover - depende del entorno
            raise DatabaseConnectorError("No fue posible conectarse a SQL Server.") from exc

    def connection_factory(self) -> Callable[[], "pymssql.Connection"]:
        """Expose a callable that creates a new connection on each invocation."""
        return self.get_connection
