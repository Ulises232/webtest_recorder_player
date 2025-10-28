"""Controller dedicated to orchestrating session workflows."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from app.dtos.session_dto import SessionDTO, SessionEvidenceDTO
from app.services.session_service import SessionService, SessionServiceError

from app.controllers.auth_controller import AuthenticationController


class SessionController:
    """Expose evidence session actions required by the desktop GUI."""

    def __init__(
        self,
        session_service: SessionService,
        auth_controller: AuthenticationController,
        sessions_dir: Path,
        evidence_dir: Path,
    ) -> None:
        """Store dependencies required to manipulate evidence sessions."""

        self._session_service = session_service
        self._auth_controller = auth_controller
        self._sessions_dir = sessions_dir
        self._evidence_dir = evidence_dir

    def getSessionsDirectory(self) -> Path:
        """Provide the storage folder for generated session documents."""

        return self._sessions_dir

    def getEvidenceDirectory(self) -> Path:
        """Provide the storage folder for evidence artifacts."""

        return self._evidence_dir

    def begin_evidence_session(
        self,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
    ) -> Tuple[Optional[SessionDTO], Optional[str]]:
        """Start a new evidence session for the authenticated user."""

        username = self._auth_controller.get_authenticated_username()
        if not username:
            return None, "Debes iniciar sesión antes de crear una sesión de evidencias."
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

        username = self._auth_controller.get_authenticated_username()
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

        username = self._auth_controller.get_authenticated_username()
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

        username = self._auth_controller.get_authenticated_username()
        try:
            session, evidences = self._session_service.get_session_with_evidences(session_id, username)
        except SessionServiceError as exc:
            return None, [], str(exc)
        return session, evidences, None

    def activate_session_for_dashboard_edit(
        self,
        session_id: int,
    ) -> Tuple[Optional[SessionDTO], List[SessionEvidenceDTO], Optional[str]]:
        """Load a session and mark it as active so the GUI can edit it."""

        username = self._auth_controller.get_authenticated_username()
        try:
            session, evidences = self._session_service.activate_session_for_dashboard_edit(session_id, username)
        except SessionServiceError as exc:
            return None, [], str(exc)
        return session, evidences, None

    def clear_active_session(self) -> None:
        """Release any active session cached in the service."""

        self._session_service.clear_active_session()

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

        username = self._auth_controller.get_authenticated_username()
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
