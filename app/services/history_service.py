"""Business logic for handling browsing history entries."""
from __future__ import annotations

from typing import List

from app.daos.history_dao import HistoryDAO


class HistoryService:
    """Coordinate history retrieval and persistence via the DAO."""

    def __init__(self, dao: HistoryDAO, default_item: str) -> None:
        """Set up the service with its DAO and default history entry."""
        self.dao = dao
        self.default_item = default_item

    def get_recent(self) -> List[str]:
        """Return the most recent entries ensuring the default one exists."""
        entries = self.dao.read()
        if entries:
            return entries
        return [self.default_item]

    def remember(self, url: str, cap: int = 15) -> None:
        """Persist the provided URL while respecting the history capacity."""
        cleaned = (url or "").strip()
        if not cleaned:
            return
        entries = self.dao.read()
        lowered = cleaned.lower()
        filtered = [item for item in entries if item.lower() != lowered]
        updated = [cleaned, *filtered][:cap]
        self.dao.write(updated)
