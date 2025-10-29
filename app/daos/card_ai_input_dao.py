"""DAO responsible for persisting captured AI inputs."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - only used for typing hints
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.card_ai_dto import CardAIInputDTO


class CardAIInputDAOError(RuntimeError):
    """Raised when input prompts cannot be stored or retrieved."""


class CardAIInputDAO:
    """Provide CRUD helpers for ``dbo.cards_ai_inputs``."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the callable that opens SQL Server connections."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the inputs table the first time it is required."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'cards_ai_inputs' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.cards_ai_inputs (
                        input_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        card_id BIGINT NOT NULL,
                        tipo VARCHAR(20) NOT NULL,
                        descripcion NVARCHAR(MAX) NULL,
                        analisis NVARCHAR(MAX) NULL,
                        recomendaciones NVARCHAR(MAX) NULL,
                        cosas_prevenir NVARCHAR(MAX) NULL,
                        info_adicional NVARCHAR(MAX) NULL,
                        completeness_pct TINYINT NOT NULL DEFAULT(0),
                        is_draft BIT NOT NULL DEFAULT(1),
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        updated_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
                    );
                    CREATE INDEX ix_cards_ai_inputs_card_id
                        ON dbo.cards_ai_inputs (card_id DESC, input_id DESC);
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
            raise CardAIInputDAOError("No fue posible preparar la tabla de entradas AI.") from exc
        finally:
            connection.close()

        self._schema_ready = True

    @staticmethod
    def _row_to_dto(row: Tuple) -> CardAIInputDTO:
        """Convert a database row into a DTO instance."""

        created_at = row[10]
        updated_at = row[11]
        if not isinstance(created_at, datetime):
            created_at = datetime.fromisoformat(str(created_at))
        if not isinstance(updated_at, datetime):
            updated_at = datetime.fromisoformat(str(updated_at))
        return CardAIInputDTO(
            inputId=int(row[0]),
            cardId=int(row[1]),
            tipo=str(row[2] or ""),
            descripcion=row[3],
            analisis=row[4],
            recomendaciones=row[5],
            cosasPrevenir=row[6],
            infoAdicional=row[7],
            completenessPct=int(row[8] or 0),
            isDraft=bool(row[9]),
            createdAt=created_at,
            updatedAt=updated_at,
        )

    def create_input(
        self,
        card_id: int,
        tipo: str,
        descripcion: Optional[str],
        analisis: Optional[str],
        recomendaciones: Optional[str],
        cosas_prevenir: Optional[str],
        info_adicional: Optional[str],
        completeness_pct: int,
        is_draft: bool,
    ) -> CardAIInputDTO:
        """Insert a new prompt input and return the persisted DTO."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "INSERT INTO dbo.cards_ai_inputs "
                    "(card_id, tipo, descripcion, analisis, recomendaciones, cosas_prevenir, info_adicional, completeness_pct, is_draft) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"
                    "SELECT input_id, card_id, tipo, descripcion, analisis, recomendaciones, cosas_prevenir, info_adicional, completeness_pct, is_draft, created_at, updated_at "
                    "FROM dbo.cards_ai_inputs WHERE input_id = SCOPE_IDENTITY();"
                ),
                (
                    card_id,
                    tipo,
                    descripcion,
                    analisis,
                    recomendaciones,
                    cosas_prevenir,
                    info_adicional,
                    completeness_pct,
                    1 if is_draft else 0,
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
            raise CardAIInputDAOError("No fue posible guardar la captura de la tarjeta.") from exc

        connection.close()
        return self._row_to_dto(row)

    def list_by_card(self, card_id: int, limit: int = 50) -> List[CardAIInputDTO]:
        """Return the most recent inputs associated with a card."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT TOP (%s) input_id, card_id, tipo, descripcion, analisis, recomendaciones,"
                    " cosas_prevenir, info_adicional, completeness_pct, is_draft, created_at, updated_at "
                    "FROM dbo.cards_ai_inputs WHERE card_id = %s ORDER BY created_at DESC, input_id DESC"
                ),
                (limit, card_id),
            )
            rows: Iterable[Tuple] = cursor.fetchall()
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise CardAIInputDAOError("No fue posible consultar las capturas de la tarjeta.") from exc

        connection.close()
        results: List[CardAIInputDTO] = []
        for row in rows:
            created_at = row[10]
            updated_at = row[11]
            if not isinstance(created_at, datetime):
                created_at = datetime.fromisoformat(str(created_at))
            if not isinstance(updated_at, datetime):
                updated_at = datetime.fromisoformat(str(updated_at))
            results.append(
                CardAIInputDTO(
                    inputId=int(row[0]),
                    cardId=int(row[1]),
                    tipo=str(row[2] or ""),
                    descripcion=row[3],
                    analisis=row[4],
                    recomendaciones=row[5],
                    cosasPrevenir=row[6],
                    infoAdicional=row[7],
                    completenessPct=int(row[8] or 0),
                    isDraft=bool(row[9]),
                    createdAt=created_at,
                    updatedAt=updated_at,
                )
            )
        return results

    def get_input(self, input_id: int) -> Optional[CardAIInputDTO]:
        """Return an input DTO by its identifier."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT input_id, card_id, tipo, descripcion, analisis, recomendaciones,"
                " cosas_prevenir, info_adicional, completeness_pct, is_draft, created_at, updated_at"
                " FROM dbo.cards_ai_inputs WHERE input_id = %s",
                (input_id,),
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover
            connection.close()
            raise CardAIInputDAOError("No fue posible consultar la captura solicitada.") from exc

        connection.close()
        if not row:
            return None

        created_at = row[10]
        updated_at = row[11]
        if not isinstance(created_at, datetime):
            created_at = datetime.fromisoformat(str(created_at))
        if not isinstance(updated_at, datetime):
            updated_at = datetime.fromisoformat(str(updated_at))
        return CardAIInputDTO(
            inputId=int(row[0]),
            cardId=int(row[1]),
            tipo=str(row[2] or ""),
            descripcion=row[3],
            analisis=row[4],
            recomendaciones=row[5],
            cosasPrevenir=row[6],
            infoAdicional=row[7],
            completenessPct=int(row[8] or 0),
            isDraft=bool(row[9]),
            createdAt=created_at,
            updatedAt=updated_at,
        )

