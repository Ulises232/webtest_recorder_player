"""Controller coordinating the desktop view with domain services."""

from __future__ import annotations

from app.config.storage_paths import (
    getEvidenceDirectory,
    getLoginCachePath,
    getSessionsDirectory,
)
from app.controllers.auth_controller import AuthenticationController
from app.controllers.browser_controller import BrowserController
from app.controllers.history_controller import HistoryController
from app.controllers.naming_controller import NamingController
from app.controllers.session_controller import SessionController
from app.daos.database import DatabaseConnector
from app.daos.evidence_dao import SessionEvidenceDAO
from app.daos.history_dao import HistoryDAO
from app.daos.session_dao import SessionDAO
from app.daos.session_pause_dao import SessionPauseDAO
from app.daos.user_dao import UserDAO
from app.services.auth_service import AuthService
from app.services.browser_service import BrowserService
from app.services.history_service import HistoryService
from app.services.naming_service import NamingService
from app.services.session_service import SessionService


class MainController:
    """Aggregate specialized controllers required by the desktop GUI."""

    DEFAULT_URL = "http://localhost:8080/ELLiS/login"
    CONF_DEFAULT = "https://sistemaspremium.atlassian.net/wiki/spaces/"
    URL_HISTORY_CATEGORY = "desktop-url-history"
    CONFLUENCE_HISTORY_CATEGORY = "desktop-confluence-history"
    CONFLUENCE_SPACES_CATEGORY = "desktop-confluence-space-history"
    LOGIN_CACHE_PATH = getLoginCachePath()

    SESSIONS_DIR = getSessionsDirectory()
    EVIDENCE_DIR = getEvidenceDirectory()

    def __init__(self) -> None:
        """Bootstrap services and expose domain specific controllers."""

        history_connector = DatabaseConnector().connection_factory()
        history_service = HistoryService(HistoryDAO(history_connector))
        self.history = HistoryController(history_service)

        browser_service = BrowserService()
        self.browser = BrowserController(browser_service)

        naming_service = NamingService()
        self.naming = NamingController(naming_service)

        user_connector = DatabaseConnector().connection_factory()
        auth_service = AuthService(UserDAO(user_connector))
        self.auth = AuthenticationController(auth_service, self.LOGIN_CACHE_PATH)

        session_connector = DatabaseConnector().connection_factory()
        session_service = SessionService(
            SessionDAO(session_connector),
            SessionEvidenceDAO(session_connector),
            SessionPauseDAO(session_connector),
        )
        self.sessions = SessionController(
            session_service,
            self.auth,
            self.SESSIONS_DIR,
            self.EVIDENCE_DIR,
        )
