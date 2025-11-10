"""Data access helpers for additional evidence captures."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List

if TYPE_CHECKING:  # pragma: no cover - typing helper
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.session_dto import SessionEvidenceAssetDTO


class SessionEvidenceAssetDAOError(RuntimeError):
    """Raised when evidence asset records cannot be persisted or read."""


class SessionEvidenceAssetDAO:
    """Provide CRUD operations for evidence attachments stored per step."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the connection factory used to talk with SQL Server."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the evidence assets table the first time it is required."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - connectivity guard
            raise SessionEvidenceAssetDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'recorder_session_evidence_assets' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.recorder_session_evidence_assets (
                        asset_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                        evidence_id INT NOT NULL,
                        file_name NVARCHAR(512) NOT NULL,
                        file_path NVARCHAR(2048) NOT NULL,
                        position INT NOT NULL DEFAULT 0,
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        updated_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        CONSTRAINT fk_recorder_evidence_assets FOREIGN KEY (evidence_id)
                            REFERENCES dbo.recorder_session_evidences(evidence_id) ON DELETE CASCADE
                    );
                    CREATE INDEX ix_recorder_evidence_assets_evidence
                        ON dbo.recorder_session_evidence_assets (evidence_id, position ASC, asset_id ASC);
                END
                """
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - DDL error
            try:
                connection.rollback()
            except Exception:
                pass
            raise SessionEvidenceAssetDAOError("No fue posible preparar la tabla de capturas adicionales.") from exc
        finally:
            connection.close()

        self._schema_ready = True

    def create_asset(
        self,
        evidence_id: int,
        file_name: str,
        file_path: str,
        position: int,
        created_at: datetime,
    ) -> SessionEvidenceAssetDTO:
        """Insert a new asset row linked to the given evidence."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - connectivity guard
            raise SessionEvidenceAssetDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "INSERT INTO dbo.recorder_session_evidence_assets "
                    "(evidence_id, file_name, file_path, position, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s); "
                    "SELECT CAST(SCOPE_IDENTITY() AS INT);"
                ),
                (evidence_id, file_name, file_path, position, created_at, created_at),
            )
            row = cursor.fetchone()
            connection.commit()
        except Exception as exc:  # pragma: no cover - DML failure
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionEvidenceAssetDAOError("No fue posible guardar la captura adicional.") from exc

        connection.close()
        asset_id = int(row[0]) if row and row[0] is not None else None
        return SessionEvidenceAssetDTO(
            assetId=asset_id,
            evidenceId=evidence_id,
            fileName=file_name,
            filePath=file_path,
            position=position,
            createdAt=created_at,
            updatedAt=created_at,
        )

    def upsert_asset(
        self,
        evidence_id: int,
        position: int,
        file_name: str,
        file_path: str,
        timestamp: datetime,
    ) -> None:
        """Update an existing asset (by position) or insert it if missing."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceAssetDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "UPDATE dbo.recorder_session_evidence_assets "
                    "SET file_name = %s, file_path = %s, updated_at = %s "
                    "WHERE evidence_id = %s AND position = %s"
                ),
                (file_name, file_path, timestamp, evidence_id, position),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    (
                        "INSERT INTO dbo.recorder_session_evidence_assets "
                        "(evidence_id, file_name, file_path, position, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s)"
                    ),
                    (evidence_id, file_name, file_path, position, timestamp, timestamp),
                )
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise SessionEvidenceAssetDAOError("No fue posible actualizar la captura indicada.") from exc

        connection.close()

    def list_by_evidence(self, evidence_id: int) -> List[SessionEvidenceAssetDTO]:
        """Return the assets stored for a specific evidence."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceAssetDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT asset_id, evidence_id, file_name, file_path, position, created_at, updated_at "
                    "FROM dbo.recorder_session_evidence_assets "
                    "WHERE evidence_id = %s "
                    "ORDER BY position ASC, asset_id ASC"
                ),
                (evidence_id,),
            )
            rows: Iterable[Iterable[object]] = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise SessionEvidenceAssetDAOError("No fue posible leer las capturas adicionales.") from exc

        connection.close()
        assets: List[SessionEvidenceAssetDTO] = []
        for row in rows:
            created_at = row[5] if isinstance(row[5], datetime) else datetime.fromisoformat(str(row[5]))
            updated_at = row[6] if isinstance(row[6], datetime) else datetime.fromisoformat(str(row[6]))
            assets.append(
                SessionEvidenceAssetDTO(
                    assetId=int(row[0]) if row[0] is not None else None,
                    evidenceId=int(row[1]) if row[1] is not None else evidence_id,
                    fileName=str(row[2] or ""),
                    filePath=str(row[3] or ""),
                    position=int(row[4] or 0),
                    createdAt=created_at,
                    updatedAt=updated_at,
                )
            )
        return assets

    def list_by_session(self, session_id: int) -> Dict[int, List[SessionEvidenceAssetDTO]]:
        """Return the assets grouped by evidence for the provided session."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceAssetDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT a.asset_id, a.evidence_id, a.file_name, a.file_path, a.position, a.created_at, a.updated_at "
                    "FROM dbo.recorder_session_evidence_assets a "
                    "INNER JOIN dbo.recorder_session_evidences e ON e.evidence_id = a.evidence_id "
                    "WHERE e.session_id = %s "
                    "ORDER BY a.evidence_id ASC, a.position ASC, a.asset_id ASC"
                ),
                (session_id,),
            )
            rows: Iterable[Iterable[object]] = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise SessionEvidenceAssetDAOError("No fue posible leer las capturas asociadas a la sesi��n.") from exc

        connection.close()
        assets_by_evidence: Dict[int, List[SessionEvidenceAssetDTO]] = {}
        for row in rows:
            evidence_id = int(row[1]) if row[1] is not None else 0
            created_at = row[5] if isinstance(row[5], datetime) else datetime.fromisoformat(str(row[5]))
            updated_at = row[6] if isinstance(row[6], datetime) else datetime.fromisoformat(str(row[6]))
            dto = SessionEvidenceAssetDTO(
                assetId=int(row[0]) if row[0] is not None else None,
                evidenceId=evidence_id,
                fileName=str(row[2] or ""),
                filePath=str(row[3] or ""),
                position=int(row[4] or 0),
                createdAt=created_at,
                updatedAt=updated_at,
            )
            assets_by_evidence.setdefault(evidence_id, []).append(dto)
        return assets_by_evidence

    def get_next_position(self, evidence_id: int) -> int:
        """Return the next position to append a new asset for the evidence."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise SessionEvidenceAssetDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT MAX(position) FROM dbo.recorder_session_evidence_assets WHERE evidence_id = %s",
                (evidence_id,),
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise SessionEvidenceAssetDAOError("No fue posible calcular la siguiente posici��n de captura.") from exc

        connection.close()
        max_position = int(row[0]) if row and row[0] is not None else -1
        return max_position + 1

