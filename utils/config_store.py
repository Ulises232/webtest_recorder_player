"""Database-backed helpers to share URL history across the toolkit."""

from __future__ import annotations

from typing import List

from app.controllers.main_controller import MainController
from app.daos.database import DatabaseConnector
from app.daos.history_dao import HistoryDAO
from app.services.history_service import HistoryService


_history_service = HistoryService(HistoryDAO(DatabaseConnector().connection_factory()))
_URL_CATEGORY = MainController.URL_HISTORY_CATEGORY


def load_urls(default: str) -> List[str]:
    """Return the stored URLs for the Confluence helper combo boxes."""

    return _history_service.load_history(_URL_CATEGORY, default)


def remember_url(url: str, limit: int = 15) -> None:
    """Persist the provided URL inside the shared database history."""

    _history_service.register_value(_URL_CATEGORY, url, limit)
