"""Controller coordinating the desktop view with domain services."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config.storage_paths import (
    getEvidenceDirectory,
    getLoginCachePath,
    getSessionsDirectory,
)
from app.daos.database import DatabaseConnector
from app.daos.history_dao import HistoryDAO
from app.daos.evidence_dao import SessionEvidenceDAO
from app.daos.session_dao import SessionDAO
from app.daos.session_pause_dao import SessionPauseDAO
from app.daos.user_dao import UserDAO, UserDAOError
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus
from app.dtos.session_dto import SessionDTO, SessionEvidenceDTO
from app.services.auth_service import AuthService
from app.services.browser_service import BrowserService
from app.services.history_service import HistoryService
from app.services.naming_service import NamingService
from app.services.session_service import SessionService, SessionServiceError


class MainController:
    """Expose high-level actions required by the Tkinter views."""

    DEFAULT_URL = "http://localhost:8080/ELLiS/login"
    CONF_DEFAULT = "https://sistemaspremium.atlassian.net/wiki/spaces/"
    URL_HISTORY_CATEGORY = "desktop-url-history"
    CONFLUENCE_HISTORY_CATEGORY = "desktop-confluence-history"
    CONFLUENCE_SPACES_CATEGORY = "desktop-confluence-space-history"
    LOGIN_CACHE_PATH = getLoginCachePath()

    SESSIONS_DIR = getSessionsDirectory()
    EVIDENCE_DIR = getEvidenceDirectory()

    def __init__(self) -> None:
        """Bootstrap all services used by the desktop application."""
        history_connector = DatabaseConnector().connection_factory()
        self._history_service = HistoryService(HistoryDAO(history_connector))
        self._browser_service = BrowserService()
        self._naming_service = NamingService()
        user_connector = DatabaseConnector().connection_factory()
        self._user_dao = UserDAO(user_connector)
        self._auth_service = AuthService(self._user_dao)
        self._authenticated_user: Optional[AuthenticationResult] = None
        session_connector = DatabaseConnector().connection_factory()
        self._session_service = SessionService(
            SessionDAO(session_connector),
            SessionEvidenceDAO(session_connector),
            SessionPauseDAO(session_connector),
        )

    def load_history(self, category: str, default_value: str) -> List[str]:
        """Return the stored history values for a logical category."""
        return self._history_service.load_history(category, default_value)

    def register_history_value(self, category: str, value: str, limit: Optional[int] = None) -> None:
        """Store a new value in the history database."""
        self._history_service.register_value(category, value, limit)

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

    def get_authenticated_username(self) -> str:
        """Return the username for the authenticated user or an empty string."""

        if not self._authenticated_user or not self._authenticated_user.username:
            return ""
        return self._authenticated_user.username

    def getSessionsDirectory(self) -> Path:
        """Provide the storage folder for generated session documents."""

        return self.SESSIONS_DIR

    def getEvidenceDirectory(self) -> Path:
        """Provide the storage folder for evidence artifacts."""

        return self.EVIDENCE_DIR

    def begin_evidence_session(
        self,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
    ) -> Tuple[Optional[SessionDTO], Optional[str]]:
        """Start a new evidence session for the authenticated user."""

        if not self._authenticated_user:
            return None, "Debes iniciar sesión antes de crear una sesión de evidencias."
        username = self._authenticated_user.username or ""
        try:
            session = self._session_service.begin_session(name, initial_url, docx_url, evidences_url, username)
        except SessionServiceError as exc:
            return None, str(exc)
        return session, None

    def update_active_session_outputs(self, docx_url: str, evidences_url: str) -> Optional[str]:
        """Persist the output locations for the active session if available."""

        try:
            self._session_service.update_outputs(docx_url, evidences_url)
        except SessionServiceError as exc:
            return str(exc)
        return None

    def get_active_session(self) -> Optional[SessionDTO]:
        """Expose the active session DTO to the view layer."""

        return self._session_service.get_active_session()

    def get_session_elapsed_seconds(self) -> int:
        """Return the total elapsed seconds for the active session."""

        return self._session_service.get_elapsed_seconds()

    def pause_evidence_session(self) -> Optional[str]:
        """Pause the active session timer."""

        try:
            self._session_service.pause_session()
        except SessionServiceError as exc:
            return str(exc)
        return None

    def resume_evidence_session(self) -> Optional[str]:
        """Resume the session timer after a pause."""

        try:
            self._session_service.resume_session()
        except SessionServiceError as exc:
            return str(exc)
        return None

    def finalize_evidence_session(self) -> Tuple[Optional[SessionDTO], Optional[str]]:
        """Finalize the active session and return the stored DTO."""

        try:
            session = self._session_service.finalize_session()
        except SessionServiceError as exc:
            return None, str(exc)
        return session, None

    def register_session_evidence(
        self,
        file_path: Path,
        description: str,
        considerations: str,
        observations: str,
    ) -> Tuple[Optional[SessionEvidenceDTO], Optional[str]]:
        """Store a captured evidence in the active session."""

        try:
            evidence = self._session_service.record_evidence(file_path, description, considerations, observations)
        except SessionServiceError as exc:
            return None, str(exc)
        return evidence, None

    def list_session_evidences(self) -> Tuple[List[SessionEvidenceDTO], Optional[str]]:
        """Return the evidences recorded in the active session."""

        try:
            evidences = self._session_service.list_evidences()
        except SessionServiceError as exc:
            return [], str(exc)
        return evidences, None

    def list_sessions(self, limit: int = 100) -> Tuple[List[SessionDTO], Optional[str]]:
        """Return the available sessions for the dashboard."""

        try:
            sessions = self._session_service.list_sessions(limit=limit)
        except SessionServiceError as exc:
            return [], str(exc)
        return sessions, None

    def update_session_details(
        self,
        session_id: int,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
    ) -> Optional[str]:
        """Persist metadata changes requested from the dashboard."""

        username = self.get_authenticated_username()
        try:
            self._session_service.update_session_details(
                session_id,
                name,
                initial_url,
                docx_url,
                evidences_url,
                username,
            )
        except SessionServiceError as exc:
            return str(exc)
        return None

    def delete_session(self, session_id: int) -> Optional[str]:
        """Remove a session when requested from the dashboard."""

        username = self.get_authenticated_username()
        try:
            self._session_service.delete_session(session_id, username)
        except SessionServiceError as exc:
            return str(exc)
        return None

    def load_session_for_edit(
        self,
        session_id: int,
    ) -> Tuple[Optional[SessionDTO], List[SessionEvidenceDTO], Optional[str]]:
        """Return a session and its evidences for dashboard editing."""

        username = self.get_authenticated_username()
        try:
            session, evidences = self._session_service.get_session_with_evidences(session_id, username)
        except SessionServiceError as exc:
            return None, [], str(exc)
        return session, evidences, None

    def update_session_evidence(
        self,
        evidence_id: int,
        file_path: Path,
        description: str,
        considerations: str,
        observations: str,
    ) -> Optional[str]:
        """Update metadata or the file path for an existing evidence."""

        try:
            self._session_service.update_evidence(evidence_id, file_path, description, considerations, observations)
        except SessionServiceError as exc:
            return str(exc)
        return None

    def update_session_evidence_from_dashboard(
        self,
        session_id: int,
        evidence_id: int,
        file_path: Path,
        description: str,
        considerations: str,
        observations: str,
    ) -> Optional[str]:
        """Persist evidence edits performed from the session dashboard."""

        username = self.get_authenticated_username()
        try:
            self._session_service.update_session_evidence_details(
                session_id,
                evidence_id,
                file_path,
                description,
                considerations,
                observations,
                username,
            )
        except SessionServiceError as exc:
            return str(exc)
        return None

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
