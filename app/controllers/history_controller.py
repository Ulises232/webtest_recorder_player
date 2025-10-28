"""Controller responsible for interacting with history services."""

from __future__ import annotations

from typing import List, Optional

from app.services.history_service import HistoryService


class HistoryController:
    """Coordinate read/write access to the persistent history store."""

    def __init__(self, history_service: HistoryService) -> None:
        """Initialize the controller with the history service dependency."""

        self._history_service = history_service

    def load_history(self, category: str, default_value: str) -> List[str]:
        """Return the stored history values for a logical category."""

        return self._history_service.load_history(category, default_value)

    def register_history_value(self, category: str, value: str, limit: Optional[int] = None) -> None:
        """Persist a new value in the history register with an optional limit."""

        self._history_service.register_value(category, value, limit)
