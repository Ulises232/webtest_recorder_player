"""Controller wrapper for browser automation helpers."""

from __future__ import annotations

from typing import Tuple

from app.services.browser_service import BrowserService


class BrowserController:
    """Expose operations to launch browser instances with predefined profiles."""

    def __init__(self, browser_service: BrowserService) -> None:
        """Store the browser service dependency used by the desktop application."""

        self._browser_service = browser_service

    def open_chrome_with_profile(self, url: str, profile_dir: str = "Default") -> Tuple[bool, str]:
        """Delegate the browser opening logic to the browser service."""

        return self._browser_service.open_with_profile(url, profile_dir)
