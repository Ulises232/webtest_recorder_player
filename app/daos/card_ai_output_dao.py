"""DAO responsible for persisting LLM outputs for cards."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - only used for typing hints
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.card_ai_dto import CardAIContextDocumentDTO, CardAIOutputDTO


class CardAIOutputDAOError(RuntimeError):
    """Raised when LLM outputs cannot be stored or retrieved."""


class CardAIOutputDAO:
    """Provide CRUD helpers for ``dbo.cards_ai_outputs``."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the callable that opens SQL Server connections."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the outputs table the first time it is required."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardAIOutputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'cards_ai_outputs' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.cards_ai_outputs (
                        output_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        card_id BIGINT NOT NULL,
                        input_id BIGINT NULL,
                        llm_id VARCHAR(100) NULL,
                        llm_model VARCHAR(100) NULL,
                        llm_usage_json NVARCHAR(MAX) NULL,
                        content_json NVARCHAR(MAX) NOT NULL,
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
                    );
                    CREATE INDEX ix_cards_ai_outputs_card_id
                        ON dbo.cards_ai_outputs (card_id DESC, output_id DESC);
                END
                """
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del driver
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise CardAIOutputDAOError("No fue posible preparar la tabla de resultados AI.") from exc
        finally:
            connection.close()

        self._schema_ready = True

    def create_output(
        self,
        card_id: int,
        input_id: Optional[int],
        llm_id: Optional[str],
        llm_model: Optional[str],
        llm_usage: Optional[dict],
        content: dict,
    ) -> CardAIOutputDTO:
        """Insert a new output document and return the stored DTO."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardAIOutputDAOError(str(exc)) from exc

        usage_json = json.dumps(llm_usage or {})
        content_json = json.dumps(content)

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "INSERT INTO dbo.cards_ai_outputs "
                    "(card_id, input_id, llm_id, llm_model, llm_usage_json, content_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s);"
                    "SELECT output_id, card_id, input_id, llm_id, llm_model, llm_usage_json, content_json, created_at "
                    "FROM dbo.cards_ai_outputs WHERE output_id = SCOPE_IDENTITY();"
                ),
                (card_id, input_id, llm_id, llm_model, usage_json, content_json),
            )
            row = cursor.fetchone()
            connection.commit()
        except Exception as exc:  # pragma: no cover
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise CardAIOutputDAOError("No fue posible guardar el resultado generado.") from exc

        connection.close()
        created_at = row[7]
        if not isinstance(created_at, datetime):
            created_at = datetime.fromisoformat(str(created_at))
        return CardAIOutputDTO(
            outputId=int(row[0]),
            cardId=int(row[1]),
            inputId=int(row[2]) if row[2] is not None else None,
            llmId=row[3],
            llmModel=row[4],
            llmUsage=json.loads(row[5] or "{}"),
            content=json.loads(row[6] or "{}"),
            createdAt=created_at,
        )

    def list_by_card(self, card_id: int, limit: int = 50) -> List[CardAIOutputDTO]:
        """Return the most recent outputs stored for a card."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardAIOutputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT TOP (%s) output_id, card_id, input_id, llm_id, llm_model, llm_usage_json, content_json, created_at "
                    "FROM dbo.cards_ai_outputs WHERE card_id = %s ORDER BY created_at DESC, output_id DESC"
                ),
                (limit, card_id),
            )
            rows: Iterable[Tuple] = cursor.fetchall()
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise CardAIOutputDAOError("No fue posible consultar los resultados generados.") from exc

        connection.close()
        outputs: List[CardAIOutputDTO] = []
        for row in rows:
            created_at = row[7]
            if not isinstance(created_at, datetime):
                created_at = datetime.fromisoformat(str(created_at))
            outputs.append(
                CardAIOutputDTO(
                    outputId=int(row[0]),
                    cardId=int(row[1]),
                    inputId=int(row[2]) if row[2] is not None else None,
                    llmId=row[3],
                    llmModel=row[4],
                    llmUsage=json.loads(row[5] or "{}"),
                    content=json.loads(row[6] or "{}"),
                    createdAt=created_at,
                )
            )
        return outputs

    def list_recent_outputs_for_context(self, limit: int = 500) -> List[CardAIContextDocumentDTO]:
        """Return recent outputs with their associated card titles for RAG indexing."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIOutputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT TOP (%s) o.output_id, o.card_id, COALESCE(c.title, ''), o.content_json "
                    "FROM dbo.cards_ai_outputs o "
                    "INNER JOIN dbo.cards c ON c.id = o.card_id "
                    "ORDER BY o.output_id DESC"
                ),
                (limit,),
            )
            rows: Iterable[Tuple] = cursor.fetchall()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardAIOutputDAOError("No fue posible consultar los resultados para el contexto.") from exc

        connection.close()
        documents: List[CardAIContextDocumentDTO] = []
        for row in rows:
            try:
                content = json.loads(row[3] or "{}")
            except ValueError:
                content = {}
            documents.append(
                CardAIContextDocumentDTO(
                    outputId=int(row[0]),
                    cardId=int(row[1]),
                    cardTitle=str(row[2] or ""),
                    content=content,
                )
            )
        return documents

