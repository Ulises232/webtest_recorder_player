"""DAO responsible for loading and preparing AI settings tables."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # pragma: no cover - solo para tipado
    import pymssql

from app.config.ai_config import AIConfiguration
from app.dtos.ai_settings_dto import AISettingsRecordDTO


class AISettingsDAOError(RuntimeError):
    """Raised when the AI settings table cannot be accessed."""


class AISettingsDAO:
    """Provide helpers to read the ``dbo.ai_settings`` table."""

    def __init__(
        self,
        connection_factory: Callable[[], "pymssql.Connection"],
        configuration: AIConfiguration | None = None,
    ) -> None:
        """Store the connection factory and defaults used for bootstrapping."""

        self._connection_factory = connection_factory
        self._configuration = configuration or AIConfiguration()
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the table and default row the first time it is required."""

        if self._schema_ready:
            return

        connection = self._connection_factory()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1
                    FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'ai_settings' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.ai_settings (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        active_provider VARCHAR(32) NOT NULL DEFAULT ('local'),
                        temperature FLOAT NOT NULL DEFAULT (0.35),
                        max_tokens INT NOT NULL DEFAULT (10000),
                        timeout_seconds INT NOT NULL DEFAULT (180),
                        use_rag_local BIT NOT NULL DEFAULT (1),
                        updated_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
                    );
                END
                """
            )
            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.ai_settings)
                BEGIN
                    INSERT INTO dbo.ai_settings (
                        active_provider,
                        temperature,
                        max_tokens,
                        timeout_seconds,
                        use_rag_local
                    )
                    VALUES (%s, %s, %s, %s, 1);
                END
                """,
                (
                    "local",
                    self._configuration.get_temperature(),
                    self._configuration.get_max_tokens(),
                    180,
                ),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del controlador SQL
            try:
                connection.rollback()
            except Exception:  # pragma: no cover - depende del driver
                pass
            connection.close()
            raise AISettingsDAOError("No fue posible preparar la tabla dbo.ai_settings.") from exc
        finally:
            try:
                connection.close()
            except Exception:  # pragma: no cover - limpieza defensiva
                pass

        self._schema_ready = True

    def get_settings(self) -> AISettingsRecordDTO:
        """Return the latest AI settings stored in SQL Server."""

        self._ensure_schema()
        connection = self._connection_factory()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT TOP (1)
                    active_provider,
                    temperature,
                    max_tokens,
                    timeout_seconds,
                    use_rag_local,
                    updated_at
                FROM dbo.ai_settings
                ORDER BY updated_at DESC, id DESC;
                """
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise AISettingsDAOError("No fue posible recuperar la configuración de IA.") from exc

        connection.close()
        if not row:
            raise AISettingsDAOError("La tabla dbo.ai_settings no contiene registros válidos.")

        updated_at = row[5]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return AISettingsRecordDTO(
            activeProvider=str(row[0] or "local"),
            temperature=float(row[1] or self._configuration.get_temperature()),
            maxTokens=int(row[2] or self._configuration.get_max_tokens()),
            timeoutSeconds=int(row[3] or 180),
            useRagLocal=bool(row[4]),
            updatedAt=updated_at,
        )
