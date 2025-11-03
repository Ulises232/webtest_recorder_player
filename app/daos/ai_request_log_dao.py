"""DAO utilities for persisting AI request and response audits."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:  # pragma: no cover - solo para tipado
    import pymssql

from app.dtos.ai_request_log_dto import AIRequestLogDTO


class AIRequestLogDAOError(RuntimeError):
    """Raised when the AI request log cannot be written or read."""


class AIRequestLogDAO:
    """Provide helpers to store and retrieve ``dbo.ai_request_logs`` entries."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Persist the connection factory used to access SQL Server."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the log table the first time it is requested."""

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
                    WHERE t.name = 'ai_request_logs' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.ai_request_logs (
                        log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        card_id BIGINT NULL,
                        input_id BIGINT NULL,
                        provider_key VARCHAR(32) NOT NULL,
                        model_name NVARCHAR(255) NULL,
                        request_payload NVARCHAR(MAX) NOT NULL,
                        response_payload NVARCHAR(MAX) NULL,
                        response_content NVARCHAR(MAX) NULL,
                        is_valid_json BIT NOT NULL DEFAULT(0),
                        error_message NVARCHAR(1024) NULL,
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        CONSTRAINT fk_ai_request_logs_card FOREIGN KEY (card_id)
                            REFERENCES dbo.cards(id) ON DELETE SET NULL,
                        CONSTRAINT fk_ai_request_logs_input FOREIGN KEY (input_id)
                            REFERENCES dbo.cards_ai_inputs(input_id) ON DELETE SET NULL
                    );
                    CREATE INDEX ix_ai_request_logs_created_at
                        ON dbo.ai_request_logs (created_at DESC, log_id DESC);
                END
                """
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del controlador SQL
            try:
                connection.rollback()
            except Exception:  # pragma: no cover - limpieza defensiva
                pass
            connection.close()
            raise AIRequestLogDAOError(
                "No fue posible preparar la tabla dbo.ai_request_logs."
            ) from exc
        finally:
            try:
                connection.close()
            except Exception:  # pragma: no cover - limpieza defensiva
                pass

        self._schema_ready = True

    def create_log(
        self,
        card_id: Optional[int],
        input_id: Optional[int],
        provider_key: str,
        model_name: Optional[str],
        request_payload: str,
        response_payload: Optional[str],
        response_content: Optional[str],
        is_valid_json: bool,
        error_message: Optional[str],
    ) -> AIRequestLogDTO:
        """Insert a new audit entry and return the stored DTO."""

        self._ensure_schema()
        connection = self._connection_factory()
        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "INSERT INTO dbo.ai_request_logs "
                    "(card_id, input_id, provider_key, model_name, request_payload, response_payload, response_content, is_valid_json, error_message) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"
                    "SELECT log_id, card_id, input_id, provider_key, model_name, request_payload, response_payload, response_content, is_valid_json, error_message, created_at "
                    "FROM dbo.ai_request_logs WHERE log_id = SCOPE_IDENTITY();"
                ),
                (
                    card_id,
                    input_id,
                    provider_key,
                    model_name,
                    request_payload,
                    response_payload,
                    response_content,
                    1 if is_valid_json else 0,
                    error_message,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del controlador SQL
            try:
                connection.rollback()
            except Exception:  # pragma: no cover - limpieza defensiva
                pass
            connection.close()
            raise AIRequestLogDAOError(
                "No fue posible registrar la bitácora de la petición de IA."
            ) from exc

        connection.close()
        created_at = row[10]
        if not isinstance(created_at, datetime):
            created_at = datetime.fromisoformat(str(created_at))
        return AIRequestLogDTO(
            logId=int(row[0]),
            cardId=int(row[1]) if row[1] is not None else None,
            inputId=int(row[2]) if row[2] is not None else None,
            providerKey=str(row[3]),
            modelName=row[4],
            requestPayload=row[5],
            responsePayload=row[6],
            responseContent=row[7],
            isValidJson=bool(row[8]),
            errorMessage=row[9],
            createdAt=created_at,
        )
