"""Controller coordinating the desktop view with domain services."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.daos.database import DatabaseConnector
from app.daos.history_dao import FileHistoryDAO
from app.daos.user_dao import UserDAO, UserDAOError
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus
from app.services.auth_service import AuthService
from app.services.browser_service import BrowserService
from app.services.history_service import HistoryService
from app.services.naming_service import NamingService


class MainController:
    """Expose high-level actions required by the Tkinter views."""

    DEFAULT_URL = "http://localhost:8080/ELLiS/login"
    CONF_DEFAULT = "https://sistemaspremium.atlassian.net/wiki/spaces/"
    LOGIN_CACHE_PATH = Path(
        os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
    ) / "ForgeBuild" / "login_cache.json"

    def __init__(self) -> None:
        """Bootstrap all services used by the desktop application."""
        self._history_services: Dict[Path, HistoryService] = {}
        self._browser_service = BrowserService()
        self._naming_service = NamingService()
        self._user_dao = UserDAO(DatabaseConnector().connection_factory())
        self._auth_service = AuthService(self._user_dao)
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
        """Validate a login request, caching both the user and the credentials."""
        result = self._auth_service.authenticate(username, password)
        if result.status == AuthenticationStatus.AUTHENTICATED:
            self._authenticated_user = result
            self._store_cached_credentials(username, password)
        return result

    def get_authenticated_user(self) -> Optional[AuthenticationResult]:
        """Return the cached authenticated user, if any."""
        return self._authenticated_user

    def list_active_users(self) -> Tuple[List[Tuple[str, str]], Optional[str]]:
        """Fetch the username/display name pairs available for selection."""

        try:
            records = self._auth_service.list_active_users()
        except UserDAOError as exc:
            return [], str(exc)

        return [
            (
                record.username,
                record.displayName or record.username,
            )
            for record in records
        ], None

    def load_cached_credentials(self) -> Optional[Dict[str, str]]:
        """Load cached credentials if the previous login was persisted."""

        path = self.LOGIN_CACHE_PATH
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, OSError):  # pragma: no cover - ruta de error
            return None

        username = payload.get("username", "").strip()
        password = payload.get("password", "")
        if not username or not password:
            return None

        return {"username": username, "password": password}

    def _store_cached_credentials(self, username: str, password: str) -> None:
        """Persist the last successful login to mirror the sibling application."""

        if not username or not password:
            return

        path = self.LOGIN_CACHE_PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump({"username": username, "password": password}, handle)
        except OSError:  # pragma: no cover - depende del entorno
            pass
