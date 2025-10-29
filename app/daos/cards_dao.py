"""Data access helpers for cards and AI generation records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, List, Optional, Sequence

from app.daos.database import DatabaseConnectorError
from app.dtos.card_ai_dto import (
    CardAIInputRecord,
    CardAIOutputRecord,
    CardFilters,
    CardSummary,
)


class CardsDAOError(RuntimeError):
    """Raised when the card catalog cannot be queried."""


class CardAIInputDAOError(RuntimeError):
    """Raised when persisting captured inputs fails."""


class CardAIOutputDAOError(RuntimeError):
    """Raised when storing LLM outputs fails."""


def _normalize_datetime(value: object) -> Optional[datetime]:
    """Normalize SQL Server values into timezone-aware datetimes."""

    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _clean_string(value: Optional[str]) -> str:
    """Return a trimmed string representation for SQL persistence."""

    return (value or "").strip()


class CardsDAO:
    """Provide read operations for the dbo.cards table."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the callable that creates SQL Server connections."""

        self._connection_factory = connection_factory

    def listCards(self, filters: Optional[CardFilters] = None, limit: int = 250) -> List[CardSummary]:
        """Return a limited set of cards applying optional filters."""

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardsDAOError(str(exc)) from exc

        query = [
            "SELECT TOP (%s) c.id, c.title, COALESCE(it.name, '') AS tipo, c.status, c.created_at "
            "FROM dbo.cards c "
            "LEFT JOIN dbo.catalog_incidence_types it ON it.id = c.incidence_type_id "
        ]
        params: List[object] = [limit]
        conditions: List[str] = []

        if filters:
            if filters.tipo:
                conditions.append("(LOWER(it.name) = LOWER(%s) OR LOWER(c.status) = LOWER(%s))")
                params.extend([filters.tipo, filters.tipo])
            if filters.status:
                conditions.append("LOWER(c.status) = LOWER(%s)")
                params.append(filters.status)

        if conditions:
            query.append("WHERE " + " AND ".join(conditions))

        query.append("ORDER BY c.created_at DESC, c.id DESC")

        try:
            cursor = connection.cursor()
            cursor.execute(" ".join(query), tuple(params))
            rows: Sequence[Sequence[object]] = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardsDAOError("No fue posible leer las tarjetas desde la base de datos.") from exc

        cards: List[CardSummary] = []
        for row in rows:
            card_id = int(row[0]) if row and row[0] is not None else 0
            title = str(row[1]) if len(row) > 1 and row[1] is not None else ""
            tipo = str(row[2]) if len(row) > 2 and row[2] is not None else ""
            status = str(row[3]) if len(row) > 3 and row[3] is not None else ""
            created_at = _normalize_datetime(row[4] if len(row) > 4 else None)
            cards.append(CardSummary(card_id, title, tipo, status, created_at))

        connection.close()
        return cards

    def fetchCard(self, card_id: int) -> Optional[CardSummary]:
        """Retrieve a single card by identifier."""

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardsDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT c.id, c.title, COALESCE(it.name, '') AS tipo, c.status, c.created_at "
                    "FROM dbo.cards c "
                    "LEFT JOIN dbo.catalog_incidence_types it ON it.id = c.incidence_type_id "
                    "WHERE c.id = %s"
                ),
                (card_id,),
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardsDAOError("No fue posible consultar la tarjeta solicitada.") from exc

        connection.close()
        if not row:
            return None
        card_id_value = int(row[0]) if row[0] is not None else card_id
        title = str(row[1]) if row[1] is not None else ""
        tipo = str(row[2]) if row[2] is not None else ""
        status = str(row[3]) if row[3] is not None else ""
        created_at = _normalize_datetime(row[4])
        return CardSummary(card_id_value, title, tipo, status, created_at)


class CardAIInputDAO:
    """Persist captured inputs that feed the LLM generation."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the connection factory and lazily ensure the schema."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the inputs table when it does not exist."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
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
                        input_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                        card_id BIGINT NOT NULL,
                        tipo VARCHAR(20) NOT NULL,
                        analisis_desc_problema NVARCHAR(MAX) NULL,
                        analisis_revision_sistema NVARCHAR(MAX) NULL,
                        analisis_datos NVARCHAR(MAX) NULL,
                        analisis_comp_reglas NVARCHAR(MAX) NULL,
                        reco_investigacion NVARCHAR(MAX) NULL,
                        reco_solucion_temporal NVARCHAR(MAX) NULL,
                        reco_impl_mejoras NVARCHAR(MAX) NULL,
                        reco_com_stakeholders NVARCHAR(MAX) NULL,
                        reco_documentacion NVARCHAR(MAX) NULL,
                        completeness_pct TINYINT NOT NULL DEFAULT(0),
                        is_draft BIT NOT NULL DEFAULT(1),
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        updated_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
                    );
                    CREATE INDEX ix_cards_ai_inputs_card_id
                        ON dbo.cards_ai_inputs (card_id, updated_at DESC, input_id DESC);
                END
                """
            )
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM sys.foreign_keys WHERE name = 'fk_cards_ai_inputs_card'
                )
                BEGIN
                    ALTER TABLE dbo.cards_ai_inputs
                        ADD CONSTRAINT fk_cards_ai_inputs_card
                        FOREIGN KEY (card_id) REFERENCES dbo.cards(id);
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
            raise CardAIInputDAOError("No fue posible preparar la tabla de entradas para IA.") from exc

        connection.close()
        self._schema_ready = True

    def insertInput(self, record: CardAIInputRecord) -> int:
        """Persist a new captured input and return its identifier."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO dbo.cards_ai_inputs (
                    card_id, tipo, analisis_desc_problema, analisis_revision_sistema,
                    analisis_datos, analisis_comp_reglas, reco_investigacion,
                    reco_solucion_temporal, reco_impl_mejoras, reco_com_stakeholders,
                    reco_documentacion, completeness_pct, is_draft, created_at, updated_at
                )
                OUTPUT INSERTED.input_id
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, SYSUTCDATETIME(), SYSUTCDATETIME())
                """,
                (
                    record.cardId,
                    record.tipo,
                    _clean_string(record.analisisDescProblema),
                    _clean_string(record.analisisRevisionSistema),
                    _clean_string(record.analisisDatos),
                    _clean_string(record.analisisCompReglas),
                    _clean_string(record.recoInvestigacion),
                    _clean_string(record.recoSolucionTemporal),
                    _clean_string(record.recoImplMejoras),
                    _clean_string(record.recoComStakeholders),
                    _clean_string(record.recoDocumentacion),
                    record.completenessPct,
                    1 if record.isDraft else 0,
                ),
            )
            row = cursor.fetchone()
            input_id = int(row[0]) if row else 0
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del driver
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise CardAIInputDAOError("No fue posible guardar los datos capturados para la tarjeta.") from exc

        connection.close()
        return input_id

    def updateDraftFlag(self, input_id: int, is_draft: bool) -> None:
        """Adjust the draft flag on an existing input."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE dbo.cards_ai_inputs
                SET is_draft = %s, updated_at = SYSUTCDATETIME()
                WHERE input_id = %s
                """,
                (1 if is_draft else 0, input_id),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del driver
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise CardAIInputDAOError("No fue posible actualizar el estado del borrador.") from exc

        connection.close()

    def fetchLatestForCard(self, card_id: int) -> Optional[CardAIInputRecord]:
        """Return the most recent input captured for the given card."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT TOP (1) input_id, card_id, tipo, analisis_desc_problema, analisis_revision_sistema,"
                    " analisis_datos, analisis_comp_reglas, reco_investigacion, reco_solucion_temporal,"
                    " reco_impl_mejoras, reco_com_stakeholders, reco_documentacion, completeness_pct, is_draft,"
                    " created_at, updated_at"
                    " FROM dbo.cards_ai_inputs WHERE card_id = %s"
                    " ORDER BY updated_at DESC, input_id DESC"
                ),
                (card_id,),
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardAIInputDAOError("No fue posible obtener el último borrador registrado.") from exc

        connection.close()
        if not row:
            return None
        return self._row_to_record(row)

    def fetchById(self, input_id: int) -> Optional[CardAIInputRecord]:
        """Retrieve a specific input by identifier."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIInputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT input_id, card_id, tipo, analisis_desc_problema, analisis_revision_sistema,"
                    " analisis_datos, analisis_comp_reglas, reco_investigacion, reco_solucion_temporal,"
                    " reco_impl_mejoras, reco_com_stakeholders, reco_documentacion, completeness_pct, is_draft,"
                    " created_at, updated_at"
                    " FROM dbo.cards_ai_inputs WHERE input_id = %s"
                ),
                (input_id,),
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardAIInputDAOError("No fue posible consultar los datos guardados para la tarjeta.") from exc

        connection.close()
        if not row:
            return None
        return self._row_to_record(row)

    def _row_to_record(self, row: Sequence[object]) -> CardAIInputRecord:
        """Convert a SQL row into a ``CardAIInputRecord`` instance."""

        return CardAIInputRecord(
            inputId=int(row[0]) if row[0] is not None else None,
            cardId=int(row[1]) if row[1] is not None else 0,
            tipo=str(row[2]) if row[2] is not None else "",
            analisisDescProblema=str(row[3]) if row[3] is not None else None,
            analisisRevisionSistema=str(row[4]) if row[4] is not None else None,
            analisisDatos=str(row[5]) if row[5] is not None else None,
            analisisCompReglas=str(row[6]) if row[6] is not None else None,
            recoInvestigacion=str(row[7]) if row[7] is not None else None,
            recoSolucionTemporal=str(row[8]) if row[8] is not None else None,
            recoImplMejoras=str(row[9]) if row[9] is not None else None,
            recoComStakeholders=str(row[10]) if row[10] is not None else None,
            recoDocumentacion=str(row[11]) if row[11] is not None else None,
            completenessPct=int(row[12]) if row[12] is not None else 0,
            isDraft=bool(row[13]) if row[13] is not None else True,
            createdAt=_normalize_datetime(row[14] if len(row) > 14 else None),
            updatedAt=_normalize_datetime(row[15] if len(row) > 15 else None),
        )


class CardAIOutputDAO:
    """Persist the JSON responses produced by the LLM."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the connection factory used to communicate with SQL Server."""

        self._connection_factory = connection_factory
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the outputs table and constraints when required."""

        if self._schema_ready:
            return

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIOutputDAOError(str(exc)) from exc

        fk_ready = False
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
                        output_id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                        card_id BIGINT NOT NULL,
                        input_id BIGINT NULL,
                        llm_id VARCHAR(100) NULL,
                        llm_model VARCHAR(100) NULL,
                        llm_usage_json NVARCHAR(MAX) NULL,
                        content_json NVARCHAR(MAX) NOT NULL,
                        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
                    );
                    CREATE INDEX ix_cards_ai_outputs_card_id
                        ON dbo.cards_ai_outputs (card_id, created_at DESC, output_id DESC);
                END
                """
            )
            cursor.execute(
                """
                IF OBJECT_ID('dbo.cards', 'U') IS NOT NULL
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM sys.foreign_keys WHERE name = 'fk_cards_ai_outputs_card'
                    )
                    BEGIN
                        ALTER TABLE dbo.cards_ai_outputs
                            ADD CONSTRAINT fk_cards_ai_outputs_card
                            FOREIGN KEY (card_id) REFERENCES dbo.cards(id);
                    END
                END
                """
            )
            cursor.execute(
                """
                IF OBJECT_ID('dbo.cards_ai_inputs', 'U') IS NOT NULL
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM sys.foreign_keys WHERE name = 'fk_cards_ai_outputs_input'
                    )
                    BEGIN
                        ALTER TABLE dbo.cards_ai_outputs
                            ADD CONSTRAINT fk_cards_ai_outputs_input
                            FOREIGN KEY (input_id) REFERENCES dbo.cards_ai_inputs(input_id);
                    END
                END
                """
            )
            cursor.execute(
                """
                SELECT COUNT(1)
                FROM sys.foreign_keys
                WHERE name = 'fk_cards_ai_outputs_input'
                """
            )
            row = cursor.fetchone()
            fk_ready = bool(row and row[0] and int(row[0]) > 0)
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del driver
            try:
                connection.rollback()
            except Exception:
                pass
            raise CardAIOutputDAOError("No fue posible preparar la tabla de resultados de IA.") from exc
        finally:
            try:
                connection.close()
            except Exception:
                pass

        self._schema_ready = fk_ready

    def insertOutput(self, record: CardAIOutputRecord) -> int:
        """Persist a new LLM response and return its identifier."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIOutputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO dbo.cards_ai_outputs (
                    card_id, input_id, llm_id, llm_model, llm_usage_json, content_json, created_at
                )
                OUTPUT INSERTED.output_id
                VALUES (%s, %s, %s, %s, %s, %s, SYSUTCDATETIME())
                """,
                (
                    record.cardId,
                    record.inputId,
                    record.llmId,
                    record.llmModel,
                    json.dumps(record.llmUsage, ensure_ascii=False),
                    json.dumps(record.content, ensure_ascii=False),
                ),
            )
            row = cursor.fetchone()
            output_id = int(row[0]) if row else 0
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del driver
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise CardAIOutputDAOError("No fue posible guardar el resultado generado por IA.") from exc

        connection.close()
        return output_id

    def listOutputsForCard(self, card_id: int, limit: int = 20) -> List[CardAIOutputRecord]:
        """Return previous generations for the specified card."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIOutputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT TOP (%s) output_id, card_id, input_id, llm_id, llm_model, llm_usage_json,"
                    " content_json, created_at FROM dbo.cards_ai_outputs WHERE card_id = %s"
                    " ORDER BY created_at DESC, output_id DESC"
                ),
                (limit, card_id),
            )
            rows: Sequence[Sequence[object]] = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardAIOutputDAOError("No fue posible consultar el historial de resultados.") from exc

        connection.close()
        return [self._row_to_record(row) for row in rows]

    def fetchById(self, output_id: int) -> Optional[CardAIOutputRecord]:
        """Return a stored LLM generation by identifier."""

        self._ensure_schema()
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardAIOutputDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT output_id, card_id, input_id, llm_id, llm_model, llm_usage_json,"
                    " content_json, created_at FROM dbo.cards_ai_outputs WHERE output_id = %s"
                ),
                (output_id,),
            )
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardAIOutputDAOError("No fue posible consultar el resultado almacenado.") from exc

        connection.close()
        if not row:
            return None
        return self._row_to_record(row)

    def _row_to_record(self, row: Sequence[object]) -> CardAIOutputRecord:
        """Translate a SQL row into a ``CardAIOutputRecord`` instance."""

        usage_raw = row[5] if len(row) > 5 else None
        content_raw = row[6] if len(row) > 6 else None
        usage = {}
        content = {}
        if isinstance(usage_raw, (str, bytes)) and usage_raw:
            try:
                usage = json.loads(usage_raw)
            except json.JSONDecodeError:
                usage = {"raw": usage_raw}
        if isinstance(content_raw, (str, bytes)) and content_raw:
            try:
                content = json.loads(content_raw)
            except json.JSONDecodeError:
                content = {"raw": content_raw}
        return CardAIOutputRecord(
            outputId=int(row[0]) if row[0] is not None else None,
            cardId=int(row[1]) if row[1] is not None else 0,
            inputId=int(row[2]) if row[2] is not None else None,
            llmId=str(row[3]) if row[3] is not None else None,
            llmModel=str(row[4]) if row[4] is not None else None,
            llmUsage=usage,
            content=content,
            createdAt=_normalize_datetime(row[7] if len(row) > 7 else None),
        )


try:  # pragma: no cover - solo para tipado
    import pymssql  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - evita errores al generar documentación
    pass
