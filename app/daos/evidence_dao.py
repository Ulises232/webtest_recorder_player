"""Data access helpers for session evidences."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Iterable, List

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.session_dto import SessionEvidenceDTO


class SessionEvidenceDAOError(RuntimeError):
    """Raised when evidence records cannot be persisted or read."""


class SessionEvidenceDAO:
    """Provide CRUD operations for evidences captured during a session."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the connection factory used to talk with SQL Server."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the evidences table the first time it is required."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'recorder_session_evidences' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.recorder_session_evidences (
                        evidence_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                        session_id INT NOT NULL,
                        file_name NVARCHAR(512) NOT NULL,
                        file_path NVARCHAR(2048) NOT NULL,
                        description NVARCHAR(MAX) NULL,
                        considerations NVARCHAR(MAX) NULL,
                        observations NVARCHAR(MAX) NULL,
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        updated_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        elapsed_since_session_start_seconds INT NOT NULL DEFAULT 0,
                        elapsed_since_previous_evidence_seconds INT NULL,
                        CONSTRAINT fk_recorder_evidences_session FOREIGN KEY (session_id)
                            REFERENCES dbo.recorder_sessions(session_id) ON DELETE CASCADE
                    );
                    CREATE INDEX ix_recorder_session_evidences_session_created
                        ON dbo.recorder_session_evidences (session_id, created_at ASC, evidence_id ASC);
                END
                """
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            raise SessionEvidenceDAOError("No fue posible preparar la tabla de evidencias.") from exc
        finally:
            connection.close()

        self._schema_ready = True

    def create_evidence(
        self,
        session_id: int,
        file_name: str,
        file_path: str,
        description: str,
        considerations: str,
        observations: str,
        created_at: datetime,
        elapsed_since_start: int,
        elapsed_since_previous: int | None,
    ) -> SessionEvidenceDTO:
        """Insert a new evidence row linked to the provided session."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "INSERT INTO dbo.recorder_session_evidences "
                    "(session_id, file_name, file_path, description, considerations, observations, created_at, updated_at, "
                    "elapsed_since_session_start_seconds, elapsed_since_previous_evidence_seconds) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s); "
                    "SELECT CAST(SCOPE_IDENTITY() AS INT);"
                ),
                (
                    session_id,
                    file_name,
                    file_path,
                    description,
                    considerations,
                    observations,
                    created_at,
                    created_at,
                    elapsed_since_start,
                    elapsed_since_previous,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionEvidenceDAOError("No fue posible guardar la evidencia capturada.") from exc

        connection.close()
        evidence_id = int(row[0]) if row and row[0] is not None else None
        return SessionEvidenceDTO(
            evidenceId=evidence_id,
            sessionId=session_id,
            fileName=file_name,
            filePath=file_path,
            description=description,
            considerations=considerations,
            observations=observations,
            createdAt=created_at,
            updatedAt=created_at,
            elapsedSinceSessionStartSeconds=elapsed_since_start,
            elapsedSincePreviousEvidenceSeconds=elapsed_since_previous,
        )

    def update_evidence(
        self,
        evidence_id: int,
        file_name: str,
        file_path: str,
        description: str,
        considerations: str,
        observations: str,
        updated_at: datetime,
    ) -> None:
        """Persist metadata or path changes for an existing evidence."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "UPDATE dbo.recorder_session_evidences "
                    "SET file_name = %s, file_path = %s, description = %s, considerations = %s, observations = %s, updated_at = %s "
                    "WHERE evidence_id = %s"
                ),
                (file_name, file_path, description, considerations, observations, updated_at, evidence_id),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionEvidenceDAOError("No fue posible actualizar la evidencia seleccionada.") from exc

        connection.close()

    def list_by_session(self, session_id: int) -> List[SessionEvidenceDTO]:
        """Return all evidences recorded for the given session."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT evidence_id, session_id, file_name, file_path, description, considerations, observations, created_at, updated_at, "
                    "elapsed_since_session_start_seconds, elapsed_since_previous_evidence_seconds "
                    "FROM dbo.recorder_session_evidences WHERE session_id = %s "
                    "ORDER BY created_at ASC, evidence_id ASC"
                ),
                (session_id,),
            )
            rows: Iterable[Iterable[object]] = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise SessionEvidenceDAOError("No fue posible leer las evidencias registradas.") from exc

        connection.close()
        evidences: List[SessionEvidenceDTO] = []
        for row in rows:
            created_at = row[7] if isinstance(row[7], datetime) else datetime.fromisoformat(str(row[7]))
            updated_at = row[8] if isinstance(row[8], datetime) else datetime.fromisoformat(str(row[8]))
            evidences.append(
                SessionEvidenceDTO(
                    evidenceId=int(row[0]) if row[0] is not None else None,
                    sessionId=int(row[1]) if row[1] is not None else session_id,
                    fileName=str(row[2] or ""),
                    filePath=str(row[3] or ""),
                    description=str(row[4] or ""),
                    considerations=str(row[5] or ""),
                    observations=str(row[6] or ""),
                    createdAt=created_at,
                    updatedAt=updated_at,
                    elapsedSinceSessionStartSeconds=int(row[9] or 0),
                    elapsedSincePreviousEvidenceSeconds=(int(row[10]) if row[10] is not None else None),
                )
            )
        return evidences
