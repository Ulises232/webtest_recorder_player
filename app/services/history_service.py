"""Business logic to manage history entries for the desktop UI."""

from typing import List

from app.daos.history_dao import FileHistoryDAO
class HistoryService:
    """Expose high-level operations for URL and Confluence histories."""

    def __init__(self, dao: FileHistoryDAO) -> None:
        """Create the service with its associated DAO instance."""
        self.dao = dao

    def load_history(self, default_value: str) -> List[str]:
        """Return the history values as plain strings for the view layer."""
        return [entry.value for entry in self.dao.load(default_value)]

    def register_value(self, value: str) -> None:
        """Persist a new history entry when a view triggers it."""
        self.dao.save(value)
