"""Business logic to manage history entries for the desktop UI."""

import logging
from typing import List, Optional

from app.daos.history_dao import HistoryDAO, HistoryDAOError


logger = logging.getLogger(__name__)


class HistoryService:
    """Expose high-level operations for URL and Confluence histories."""

    def __init__(self, dao: HistoryDAO) -> None:
        """Create the service with its associated DAO instance."""
        self.dao = dao

    def load_history(self, category: str, default_value: str) -> List[str]:
        """Return the history values as plain strings for the view layer."""
        try:
            entries = self.dao.list_recent(category, default_value)
        except HistoryDAOError as exc:  # pragma: no cover - depende del driver
            logger.error("No fue posible leer el historial '%s': %s", category, exc)
            return [default_value]
        return [entry.value for entry in entries if entry.value]

    def register_value(self, category: str, value: str, limit: Optional[int] = None) -> None:
        """Persist a new history entry when a view triggers it."""
        try:
            self.dao.record_value(category, value, limit)
        except HistoryDAOError as exc:  # pragma: no cover - depende del driver
            logger.error("No fue posible guardar el historial '%s': %s", category, exc)
