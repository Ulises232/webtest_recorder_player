"""Data access layer for reading and writing history information."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, List, Optional, Sequence

if TYPE_CHECKING:  # pragma: no cover - solo para tipado
    import pymssql

from app.daos.database import DatabaseConnectorError
from app.dtos.history_entry import HistoryEntry


class HistoryDAOError(RuntimeError):
    """Raised when an operation against the history storage fails."""


class HistoryDAO:
    """Provide CRUD-like helpers backed by the SQL Server history table."""

    def __init__(
        self,
        connection_factory: Callable[[], "pymssql.Connection"],
        default_limit: int = 15,
    ) -> None:
        """Persist the callable used to request new connections."""
        self._connection_factory = connection_factory
        self._default_limit = default_limit

    def list_recent(self, category: str, default_value: str, limit: Optional[int] = None) -> List[HistoryEntry]:
        """Return the stored history entries ordered from newest to oldest."""
        effective_limit = limit or self._default_limit
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise HistoryDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "SELECT TOP (%s) entry_id, category, value, created_at "
                    "FROM dbo.history_entries "
                    "WHERE category = %s "
                    "ORDER BY created_at DESC, entry_id DESC"
                ),
                (effective_limit, category),
            )
            rows: Sequence[Sequence[object]] = cursor.fetchall() or []
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise HistoryDAOError("No fue posible leer el historial desde la base de datos.") from exc

        entries: List[HistoryEntry] = []
        for row in rows:
            entry_id = int(row[0]) if row[0] is not None else None
            entry_category = str(row[1]) if row[1] is not None else category
            value = str(row[2]) if row[2] is not None else ""
            created_at: Optional[datetime]
            if row[3] is None:
                created_at = None
            elif isinstance(row[3], datetime):
                created_at = row[3]
            else:
                try:
                    created_at = datetime.fromisoformat(str(row[3]))
                except ValueError:
                    created_at = None
            entries.append(HistoryEntry(entry_id, entry_category, value, created_at))

        connection.close()

        if entries:
            return entries
        return [HistoryEntry(None, category, default_value, None)]

    def record_value(self, category: str, value: str, limit: Optional[int] = None) -> None:
        """Persist a new history value, ensuring uniqueness and max capacity."""
        clean_value = (value or "").strip()
        if not clean_value:
            return

        effective_limit = limit or self._default_limit
        try:
            connection = self._connection_factory()
        except DatabaseConnectorError as exc:  # pragma: no cover - depende del entorno
            raise HistoryDAOError(str(exc)) from exc

        try:
            cursor = connection.cursor()
            cursor.execute(
                (
                    "DECLARE @existing_id INT; "
                    "SELECT @existing_id = entry_id FROM dbo.history_entries "
                    "WHERE category = %s AND LOWER(value) = LOWER(%s); "
                    "IF @existing_id IS NOT NULL "
                    "BEGIN "
                    "    UPDATE dbo.history_entries "
                    "    SET value = %s, created_at = SYSUTCDATETIME() "
                    "    WHERE entry_id = @existing_id; "
                    "END "
                    "ELSE "
                    "BEGIN "
                    "    INSERT INTO dbo.history_entries (category, value, created_at) "
                    "    VALUES (%s, %s, SYSUTCDATETIME()); "
                    "END"
                ),
                (category, clean_value, clean_value, category, clean_value),
            )
            cursor.execute(
                (
                    "WITH ordered AS ("
                    "    SELECT entry_id, ROW_NUMBER() OVER (ORDER BY created_at DESC, entry_id DESC) AS row_num "
                    "    FROM dbo.history_entries WHERE category = %s"
                    ") "
                    "DELETE FROM dbo.history_entries "
                    "WHERE entry_id IN (SELECT entry_id FROM ordered WHERE row_num > %s);"
                ),
                (category, effective_limit),
            )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del driver
            try:
                connection.rollback()
            except Exception:
                pass
            connection.close()
            raise HistoryDAOError("No fue posible guardar el historial en la base de datos.") from exc

        connection.close()
