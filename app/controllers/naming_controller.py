"""Controller that exposes helpers for file-name normalization."""

from __future__ import annotations

from app.services.naming_service import NamingService


class NamingController:
    """Provide wrappers to reuse naming utilities from the view layer."""

    def __init__(self, naming_service: NamingService) -> None:
        """Persist the naming service dependency."""

        self._naming_service = naming_service

    def slugify_for_windows(self, name: str) -> str:
        """Return a Windows compatible slug derived from the provided name."""

        return self._naming_service.slugify_for_windows(name)
