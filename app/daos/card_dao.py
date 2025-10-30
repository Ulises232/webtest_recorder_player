"""DAO to read Branch History cards from SQL Server."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - only used for typing hints
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.card_ai_dto import CardDTO, CardFiltersDTO


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
        if filters.bestOnly:
            conditions.append(
                "EXISTS (SELECT 1 FROM dbo.cards_ai_outputs o WHERE o.card_id = c.id AND o.is_best = 1)"
            )

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        sql = (
            "SELECT TOP (%s) c.id, c.title, COALESCE(c.group_name, ''), COALESCE(c.status,''),"
            " c.created_at, c.updated_at, COALESCE(c.ticket_id,''), COALESCE(c.branch_key,''),"
            " CASE WHEN EXISTS (SELECT 1 FROM dbo.cards_ai_outputs o WHERE o.card_id = c.id AND o.is_best = 1) THEN 1 ELSE 0 END"
            " FROM dbo.cards c"
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
                    hasBestSelection=bool(row[8]),
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

