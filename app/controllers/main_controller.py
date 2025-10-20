"""Controller coordinating the desktop view with domain services."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.daos.database import DatabaseConnector
from app.daos.history_dao import FileHistoryDAO
from app.daos.user_dao import UserDAO
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus
from app.services.auth_service import AuthService
from app.services.browser_service import BrowserService
from app.services.history_service import HistoryService
from app.services.naming_service import NamingService


class MainController:
    """Expose high-level actions required by the Tkinter views."""

    DEFAULT_URL = "http://localhost:8080/ELLiS/login"
    CONF_DEFAULT = "https://sistemaspremium.atlassian.net/wiki/spaces/"

    def __init__(self) -> None:
        """Bootstrap all services used by the desktop application."""
        self._history_services: Dict[Path, HistoryService] = {}
        self._browser_service = BrowserService()
        self._naming_service = NamingService()
        user_dao = UserDAO(DatabaseConnector().connection_factory())
        self._auth_service = AuthService(user_dao)
        self._authenticated_user: Optional[AuthenticationResult] = None

    def _get_history_service(self, file_path: Path) -> HistoryService:
        """Lazy-load the history service associated to a specific file."""
        if file_path not in self._history_services:
            self._history_services[file_path] = HistoryService(FileHistoryDAO(file_path))
        return self._history_services[file_path]

    def load_history(self, file_path: Path, default_value: str) -> List[str]:
        """Return the stored history for a file path."""
        return self._get_history_service(file_path).load_history(default_value)

    def register_history_value(self, file_path: Path, value: str) -> None:
        """Store a new value in the history file."""
        self._get_history_service(file_path).register_value(value)

    def open_chrome_with_profile(self, url: str, profile_dir: str = "Default") -> Tuple[bool, str]:
        """Delegate the browser opening logic to the service layer."""
        return self._browser_service.open_with_profile(url, profile_dir)

    def slugify_for_windows(self, name: str) -> str:
        """Expose the naming helper for view usage."""
        return self._naming_service.slugify_for_windows(name)

    def authenticate_user(self, username: str, password: str) -> AuthenticationResult:
        """Validate a login request and cache the authenticated user."""
        result = self._auth_service.authenticate(username, password)
        if result.status == AuthenticationStatus.AUTHENTICATED:
            self._authenticated_user = result
        return result

    def get_authenticated_user(self) -> Optional[AuthenticationResult]:
        """Return the cached authenticated user, if any."""
        return self._authenticated_user
