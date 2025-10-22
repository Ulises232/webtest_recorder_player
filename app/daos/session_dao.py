"""Data access helpers for recorder sessions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, List, Optional

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.session_dto import SessionDTO


class SessionDAOError(RuntimeError):
    """Raised when the session storage cannot be accessed."""


class SessionDAO:
    """Provide CRUD operations for recorder sessions."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the callable used to obtain database connections."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    @staticmethod
    def _row_to_dto(row: tuple) -> SessionDTO:
        """Convert a database row into a session DTO."""

        started_raw = row[6]
        ended_raw = row[7]
        created_raw = row[9]
        updated_raw = row[10]
        started_at = (
            started_raw
            if isinstance(started_raw, datetime)
            else datetime.fromisoformat(str(started_raw))
        )
        ended_at = (
            ended_raw
            if isinstance(ended_raw, datetime) or ended_raw is None
            else datetime.fromisoformat(str(ended_raw))
        )
        created_at = (
            created_raw
            if isinstance(created_raw, datetime)
            else datetime.fromisoformat(str(created_raw))
        )
        updated_at = (
            updated_raw
            if isinstance(updated_raw, datetime)
            else datetime.fromisoformat(str(updated_raw))
        )
        return SessionDTO(
            sessionId=int(row[0]) if row[0] is not None else None,
            name=str(row[1] or ""),
            initialUrl=str(row[2] or ""),
            docxUrl=str(row[3] or ""),
            evidencesUrl=str(row[4] or ""),
            durationSeconds=int(row[5] or 0),
            startedAt=started_at,
            endedAt=ended_at,
            username=str(row[8] or ""),
            createdAt=created_at,
            updatedAt=updated_at,
        )

    def _ensure_schema(self) -> None:
        """Create the sessions table on first use."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depends on environment
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'recorder_sessions' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.recorder_sessions (
                        session_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                        name NVARCHAR(255) NOT NULL,
                        initial_url NVARCHAR(2048) NULL,
                        docx_url NVARCHAR(2048) NULL,
                        evidences_url NVARCHAR(2048) NULL,
                        duration_seconds INT NOT NULL DEFAULT 0,
                        started_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        ended_at DATETIME2(0) NULL,
                        username NVARCHAR(255) NOT NULL,
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        updated_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
                    );
                    CREATE INDEX ix_recorder_sessions_started_at
                        ON dbo.recorder_sessions (started_at DESC, session_id DESC);
                END
                """
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depends on driver
            try:
                connection.rollback()
            except Exception:
                pass
            raise SessionDAOError("No fue posible preparar la tabla de sesiones.") from exc
        finally:
            connection.close()

        self._schema_ready = True

    def create_session(
        self,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
        username: str,
        started_at: datetime,
    ) -> SessionDTO:
        """Insert a new session row and return the created DTO."""

        self._ensure_schema()
        created_at = started_at
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "INSERT INTO dbo.recorder_sessions "
                    "(name, initial_url, docx_url, evidences_url, duration_seconds, started_at, ended_at, username, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, 0, %s, NULL, %s, %s, %s); "
                    "SELECT CAST(SCOPE_IDENTITY() AS INT);"
                ),
                (name, initial_url, docx_url, evidences_url, started_at, username, created_at, created_at),
            )
            row = cursor.fetchone()
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionDAOError("No fue posible registrar la sesión de evidencias.") from exc

        connection.close()
        session_id = int(row[0]) if row and row[0] is not None else None
        return SessionDTO(
            sessionId=session_id,
            name=name,
            initialUrl=initial_url,
            docxUrl=docx_url,
            evidencesUrl=evidences_url,
            durationSeconds=0,
            startedAt=started_at,
            endedAt=None,
            username=username,
            createdAt=created_at,
            updatedAt=created_at,
        )

    def update_outputs(
        self,
        session_id: int,
        docx_url: str,
        evidences_url: str,
        updated_at: datetime,
    ) -> None:
        """Persist the latest output locations for an active session."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "UPDATE dbo.recorder_sessions "
                    "SET docx_url = %s, evidences_url = %s, updated_at = %s "
                    "WHERE session_id = %s"
                ),
                (docx_url, evidences_url, updated_at, session_id),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionDAOError("No fue posible actualizar las rutas de la sesión.") from exc

        connection.close()

    def close_session(self, session_id: int, ended_at: datetime, duration_seconds: int) -> None:
        """Mark a session as finished and store the total duration."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "UPDATE dbo.recorder_sessions "
                    "SET ended_at = %s, duration_seconds = %s, updated_at = %s "
                    "WHERE session_id = %s"
                ),
                (ended_at, duration_seconds, ended_at, session_id),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionDAOError("No fue posible finalizar la sesión de evidencias.") from exc

        connection.close()

    def get_session(self, session_id: int) -> Optional[SessionDTO]:
        """Fetch a session row to refresh the cached DTO."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT session_id, name, initial_url, docx_url, evidences_url, duration_seconds, "
                    "started_at, ended_at, username, created_at, updated_at "
                    "FROM dbo.recorder_sessions WHERE session_id = %s"
                ),
                (session_id,),
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise SessionDAOError("No fue posible consultar la sesión solicitada.") from exc

        connection.close()
        if not row:
            return None

        return self._row_to_dto(row)

    def list_sessions(self, limit: int = 100, username: Optional[str] = None) -> List[SessionDTO]:
        """Return the most recent sessions optionally filtered by user."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depends on environment
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            clauses = [
                "SELECT session_id, name, initial_url, docx_url, evidences_url, duration_seconds,",
                "started_at, ended_at, username, created_at, updated_at",
                "FROM dbo.recorder_sessions",
            ]
            params: List[object] = []
            if username:
                clauses.append("WHERE username = %s")
                params.append(username)
            clauses.append("ORDER BY started_at DESC, session_id DESC")
            clauses.append("OFFSET 0 ROWS FETCH NEXT %s ROWS ONLY")
            params.append(max(1, int(limit or 1)))
            cursor.execute(" ".join(clauses), tuple(params))
            rows = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover - depends on driver
            connection.close()
            raise SessionDAOError("No fue posible consultar las sesiones registradas.") from exc

        connection.close()
        return [self._row_to_dto(row) for row in rows]

    def update_session_details(
        self,
        session_id: int,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
        updated_at: datetime,
    ) -> None:
        """Update the editable metadata for an existing session."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depends on environment
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "UPDATE dbo.recorder_sessions "
                    "SET name = %s, initial_url = %s, docx_url = %s, evidences_url = %s, updated_at = %s "
                    "WHERE session_id = %s"
                ),
                (name, initial_url, docx_url, evidences_url, updated_at, session_id),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depends on driver
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionDAOError("No fue posible actualizar la sesión seleccionada.") from exc

        connection.close()

    def delete_session(self, session_id: int) -> None:
        """Remove a session and its evidences from storage."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depends on environment
            raise SessionDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM dbo.recorder_sessions WHERE session_id = %s", (session_id,))
            connection.commit()
        except Exception as exc:  # pragma: no cover - depends on driver
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionDAOError("No fue posible eliminar la sesión solicitada.") from exc

        connection.close()
