"""DAO to read Branch History cards from SQL Server."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - only used for typing hints
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.card_ai_dto import CardDTO, CardFiltersDTO, CatalogOptionDTO


class CardDAOError(RuntimeError):
    """Raised when the card catalog cannot be read from SQL Server."""


class CardDAO:
    """Provide read access to ``dbo.cards`` required by the AI assistant."""

    def __init__(self, connection_factory: Callable[[], "pymssql.Connection"]) -> None:
        """Store the callable that creates new database connections."""

        self._connection_factory = connection_factory

    def _normalize_epoch(self, value: Optional[int]) -> Optional[datetime]:
        """Convert epoch seconds into timezone-aware datetimes when possible."""

        if value is None:
            return None
        try:
            return datetime.fromtimestamp(int(value))
        except (ValueError, OverflowError, OSError):  # pragma: no cover - depende de datos
            return None

    def list_cards(self, filters: CardFiltersDTO, limit: int = 200) -> List[CardDTO]:
        """Return the cards matching the provided filters sorted by recency."""

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardDAOError(str(exc)) from exc

        conditions: List[str] = []
        params: List[object] = []

        if filters.cardType:
            conditions.append("COALESCE(c.group_name, '') = %s")
            params.append(filters.cardType)
        if filters.status:
            conditions.append("COALESCE(c.status, '') = %s")
            params.append(filters.status)
        if filters.startDate:
            conditions.append("c.created_at >= %s")
            params.append(int(filters.startDate.timestamp()))
        if filters.endDate:
            conditions.append("c.created_at <= %s")
            params.append(int(filters.endDate.timestamp()))
        if filters.searchText:
            conditions.append(
                "(c.title LIKE %s OR COALESCE(c.description,'') LIKE %s OR COALESCE(c.ticket_id,'') LIKE %s)"
            )
            like_token = f"%{filters.searchText}%"
            params.extend([like_token, like_token, like_token])
        if filters.bestSelection is not None:
            comparator = "EXISTS" if filters.bestSelection else "NOT EXISTS"
            conditions.append(
                f"{comparator} (SELECT 1 FROM dbo.cards_ai_outputs o WHERE o.card_id = c.id AND o.is_best = 1)"
            )
        if filters.ddeGenerated is not None:
            comparator = "EXISTS" if filters.ddeGenerated else "NOT EXISTS"
            conditions.append(
                f"{comparator} (SELECT 1 FROM dbo.cards_ai_outputs o WHERE o.card_id = c.id AND o.dde_generated = 1)"
            )
        if filters.testsGenerated is not None:
            comparator = "EXISTS" if filters.testsGenerated else "NOT EXISTS"
            conditions.append(
                f"{comparator} (SELECT 1 FROM dbo.recorder_sessions rs WHERE rs.card_id = c.id)"
            )
        if filters.incidentTypeId is not None:
            conditions.append("c.incidence_type_id = %s")
            params.append(filters.incidentTypeId)
        if filters.companyId is not None:
            conditions.append("c.company_id = %s")
            params.append(filters.companyId)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        sql = (
            "SELECT TOP (%s)"
            " c.id,"
            " c.title,"
            " COALESCE(c.group_name, ''),"
            " COALESCE(c.status,''),"
            " c.created_at,"
            " c.updated_at,"
            " COALESCE(c.ticket_id,''),"
            " COALESCE(c.branch_key,''),"
            " c.sprint_id,"
            " COALESCE(s.name, ''),"
            " c.incidence_type_id,"
            " COALESCE(cit.name, ''),"
            " c.company_id,"
            " COALESCE(cc.name, ''),"
            " CASE WHEN EXISTS (SELECT 1 FROM dbo.cards_ai_outputs o WHERE o.card_id = c.id AND o.is_best = 1) THEN 1 ELSE 0 END,"
            " CASE WHEN EXISTS (SELECT 1 FROM dbo.cards_ai_outputs o WHERE o.card_id = c.id AND o.dde_generated = 1) THEN 1 ELSE 0 END,"
            " CASE WHEN EXISTS (SELECT 1 FROM dbo.recorder_sessions rs WHERE rs.card_id = c.id) THEN 1 ELSE 0 END"
            " FROM dbo.cards c"
            " LEFT JOIN dbo.catalog_incidence_types cit ON cit.id = c.incidence_type_id"
            " LEFT JOIN dbo.catalog_companies cc ON cc.id = c.company_id"
            " LEFT JOIN dbo.sprints s ON s.id = c.sprint_id"
            f"{where_clause}"
            " ORDER BY COALESCE(c.updated_at, c.created_at) DESC"
        )

        params = [limit] + params

        try:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            rows: Iterable[Tuple] = cursor.fetchall()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardDAOError("No fue posible leer las tarjetas.") from exc

        connection.close()
        cards: List[CardDTO] = []
        for row in rows:
            created_at = self._normalize_epoch(row[4])
            updated_at = self._normalize_epoch(row[5])
            cards.append(
                CardDTO(
                    cardId=int(row[0]),
                    title=str(row[1] or ""),
                    cardType=str(row[2] or ""),
                    status=str(row[3] or ""),
                    createdAt=created_at,
                    updatedAt=updated_at,
                    ticketId=str(row[6] or ""),
                    branchKey=str(row[7] or ""),
                    sprintId=int(row[8]) if row[8] is not None else None,
                    sprintName=str(row[9] or ""),
                    incidentTypeId=int(row[10]) if row[10] is not None else None,
                    incidentTypeName=str(row[11] or ""),
                    companyId=int(row[12]) if row[12] is not None else None,
                    companyName=str(row[13] or ""),
                    hasBestSelection=bool(row[14]),
                    hasDdeGenerated=bool(row[15]),
                    hasTestsGenerated=bool(row[16]),
                )
            )
        return cards

    def get_card_title(self, card_id: int) -> str:
        """Return the title of the card or raise when not found."""

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover
            raise CardDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT title FROM dbo.cards WHERE id = %s", (card_id,))
            row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardDAOError("No fue posible leer la tarjeta solicitada.") from exc

        connection.close()
        if not row:
            raise CardDAOError("La tarjeta solicitada no existe.")
        return str(row[0] or "")

    def list_incident_types(self) -> List[CatalogOptionDTO]:
        """Return the available incident types ordered alphabetically."""

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT id, COALESCE(name, '') FROM dbo.catalog_incidence_types ORDER BY name ASC")
            rows: Iterable[Tuple] = cursor.fetchall()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardDAOError("No fue posible leer los tipos de incidente.") from exc

        connection.close()
        return [
            CatalogOptionDTO(optionId=int(row[0]), name=str(row[1] or ""))
            for row in rows
            if row and row[0] is not None
        ]

    def list_companies(self) -> List[CatalogOptionDTO]:
        """Return the companies catalog ordered alphabetically."""

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT id, COALESCE(name, '') FROM dbo.catalog_companies ORDER BY name ASC")
            rows: Iterable[Tuple] = cursor.fetchall()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardDAOError("No fue posible leer el catálogo de empresas.") from exc

        connection.close()
        return [
            CatalogOptionDTO(optionId=int(row[0]), name=str(row[1] or ""))
            for row in rows
            if row and row[0] is not None
        ]

    def list_statuses(self) -> List[str]:
        """Return the distinct card statuses."""

        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise CardDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute("SELECT DISTINCT COALESCE(status, '') FROM dbo.cards ORDER BY COALESCE(status, '') ASC")
            rows: Iterable[Tuple] = cursor.fetchall()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise CardDAOError("No fue posible leer la lista de estatus.") from exc

        connection.close()
        return [str(row[0] or "") for row in rows if row and str(row[0] or "").strip()]
