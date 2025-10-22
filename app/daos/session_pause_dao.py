"""Data access helpers for session pause intervals."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Iterable, List

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.session_dto import SessionPauseDTO


class SessionPauseDAOError(RuntimeError):
    """Raised when pause intervals cannot be persisted or read."""


class SessionPauseDAO:
    """Provide CRUD operations for pauses within a session."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the callable used to open database connections."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the pauses table on demand."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionPauseDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'recorder_session_pauses' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.recorder_session_pauses (
                        pause_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                        session_id INT NOT NULL,
                        paused_at DATETIME2(0) NOT NULL,
                        resumed_at DATETIME2(0) NULL,
                        elapsed_seconds_when_paused INT NOT NULL DEFAULT 0,
                        pause_duration_seconds INT NULL,
                        CONSTRAINT fk_recorder_session_pauses_session FOREIGN KEY (session_id)
                            REFERENCES dbo.recorder_sessions(session_id) ON DELETE CASCADE
                    );
                    CREATE INDEX ix_recorder_session_pauses_session
                        ON dbo.recorder_session_pauses (session_id, paused_at DESC, pause_id DESC);
                END
                """
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            raise SessionPauseDAOError("No fue posible preparar la tabla de pausas.") from exc
        finally:
            connection.close()

        self._schema_ready = True

    def create_pause(
        self,
        session_id: int,
        paused_at: datetime,
        elapsed_seconds_when_paused: int,
    ) -> SessionPauseDTO:
        """Insert a new pause row associated with the provided session."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionPauseDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "INSERT INTO dbo.recorder_session_pauses "
                    "(session_id, paused_at, resumed_at, elapsed_seconds_when_paused, pause_duration_seconds) "
                    "VALUES (%s, %s, NULL, %s, NULL); "
                    "SELECT CAST(SCOPE_IDENTITY() AS INT);"
                ),
                (session_id, paused_at, elapsed_seconds_when_paused),
            )
            row = cursor.fetchone()
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionPauseDAOError("No fue posible registrar la pausa de la sesión.") from exc

        connection.close()
        pause_id = int(row[0]) if row and row[0] is not None else None
        return SessionPauseDTO(
            pauseId=pause_id,
            sessionId=session_id,
            pausedAt=paused_at,
            resumedAt=None,
            elapsedSecondsWhenPaused=elapsed_seconds_when_paused,
            pauseDurationSeconds=None,
        )

    def finish_pause(
        self,
        pause_id: int,
        resumed_at: datetime,
        pause_duration_seconds: int,
    ) -> None:
        """Update the pause row once the session is resumed."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionPauseDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "UPDATE dbo.recorder_session_pauses "
                    "SET resumed_at = %s, pause_duration_seconds = %s "
                    "WHERE pause_id = %s"
                ),
                (resumed_at, pause_duration_seconds, pause_id),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionPauseDAOError("No fue posible actualizar la pausa de la sesión.") from exc

        connection.close()

    def list_by_session(self, session_id: int) -> List[SessionPauseDTO]:
        """Return the pauses registered for the given session."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionPauseDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT pause_id, session_id, paused_at, resumed_at, elapsed_seconds_when_paused, pause_duration_seconds "
                    "FROM dbo.recorder_session_pauses WHERE session_id = %s "
                    "ORDER BY paused_at DESC, pause_id DESC"
                ),
                (session_id,),
            )
            rows: Iterable[Iterable[object]] = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise SessionPauseDAOError("No fue posible obtener las pausas de la sesión.") from exc

        connection.close()
        pauses: List[SessionPauseDTO] = []
        for row in rows:
            paused_at = row[2] if isinstance(row[2], datetime) else datetime.fromisoformat(str(row[2]))
            resumed_at = None
            if row[3] is not None:
                resumed_at = row[3] if isinstance(row[3], datetime) else datetime.fromisoformat(str(row[3]))
            pauses.append(
                SessionPauseDTO(
                    pauseId=int(row[0]) if row[0] is not None else None,
                    sessionId=int(row[1]) if row[1] is not None else session_id,
                    pausedAt=paused_at,
                    resumedAt=resumed_at,
                    elapsedSecondsWhenPaused=int(row[4] or 0),
                    pauseDurationSeconds=(int(row[5]) if row[5] is not None else None),
                )
            )
        return pauses
