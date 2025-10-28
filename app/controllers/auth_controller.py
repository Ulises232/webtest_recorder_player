"""Controller focused on authentication flows for the desktop UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.daos.user_dao import UserDAOError
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus
from app.services.auth_service import AuthService


class AuthenticationController:
    """Handle login requests, caching and active user listings."""

    def __init__(self, auth_service: AuthService, cache_path: Path) -> None:
        """Persist dependencies required to authenticate desktop users."""

        self._auth_service = auth_service
        self._cache_path = cache_path
        self._authenticated_user: Optional[AuthenticationResult] = None

    def authenticate_user(self, username: str, password: str) -> AuthenticationResult:
        """Validate a login request and cache credentials on success."""

        result = self._auth_service.authenticate(username, password)
        if result.status == AuthenticationStatus.AUTHENTICATED:
            self._authenticated_user = result
            self._store_cached_credentials(username, password)
        return result

    def get_authenticated_user(self) -> Optional[AuthenticationResult]:
        """Return the cached authenticated user, if any."""

        return self._authenticated_user

    def get_authenticated_username(self) -> str:
        """Return the username for the authenticated user or an empty string."""

        if not self._authenticated_user or not self._authenticated_user.username:
            return ""
        return self._authenticated_user.username

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

        try:
            with self._cache_path.open("r", encoding="utf-8") as handle:
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

        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_path.open("w", encoding="utf-8") as handle:
                json.dump({"username": username, "password": password}, handle)
        except OSError:  # pragma: no cover - depende del entorno
            pass
