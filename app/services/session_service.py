"""Business logic to orchestrate evidence recording sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import List, Optional

from app.daos.evidence_dao import SessionEvidenceDAO, SessionEvidenceDAOError
from app.daos.session_dao import SessionDAO, SessionDAOError
from app.daos.session_pause_dao import SessionPauseDAO, SessionPauseDAOError
from app.dtos.session_dto import SessionDTO, SessionEvidenceDTO, SessionPauseDTO


logger = logging.getLogger(__name__)


class SessionServiceError(RuntimeError):
    """Raised when a session-level operation cannot be completed."""


@dataclass
class ActiveSessionState:
    """Track runtime information for the session timer."""

    session: SessionDTO
    resumeReference: datetime
    elapsedSeconds: int
    lastEvidenceAt: Optional[datetime]
    activePause: Optional[SessionPauseDTO]


class SessionService:
    """Coordinate session lifecycle, evidences and pause management."""

    def __init__(
        self,
        session_dao: SessionDAO,
        evidence_dao: SessionEvidenceDAO,
        pause_dao: SessionPauseDAO,
    ) -> None:
        """Store the DAO dependencies and reset the active state."""

        self._session_dao = session_dao
        self._evidence_dao = evidence_dao
        self._pause_dao = pause_dao
        self._active_state: Optional[ActiveSessionState] = None

    @staticmethod
    def _utcnow() -> datetime:
        """Return the current UTC timestamp with second precision."""

        return datetime.now(timezone.utc).replace(microsecond=0)

    def begin_session(
        self,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
        username: str,
    ) -> SessionDTO:
        """Create a new session and keep it as the active one."""

        if self._active_state is not None:
            raise SessionServiceError("Ya existe una sesión activa. Finalízala antes de iniciar otra.")

        started_at = self._utcnow()
        try:
            session = self._session_dao.create_session(name, initial_url, docx_url, evidences_url, username, started_at)
        except SessionDAOError as exc:
            logger.error("No fue posible crear la sesión de evidencias: %s", exc)
            raise SessionServiceError(str(exc)) from exc

        self._active_state = ActiveSessionState(
            session=session,
            resumeReference=started_at,
            elapsedSeconds=0,
            lastEvidenceAt=None,
            activePause=None,
        )
        return session

    def get_active_session(self) -> Optional[SessionDTO]:
        """Return the active session DTO, if any."""

        if not self._active_state:
            return None
        return self._active_state.session

    def update_outputs(self, docx_url: str, evidences_url: str) -> None:
        """Persist the latest output locations if a session is active."""

        if not self._active_state:
            return
        updated_at = self._utcnow()
        session = self._active_state.session
        refreshed: Optional[SessionDTO] = None
        try:
            self._session_dao.update_outputs(session.sessionId or 0, docx_url, evidences_url, updated_at)
            refreshed = self._session_dao.get_session(session.sessionId or 0)
        except SessionDAOError as exc:
            logger.error(
                "No se pudieron actualizar o refrescar los datos de la sesión %s: %s",
                session.sessionId,
                exc,
            )
            raise SessionServiceError(str(exc)) from exc
        if refreshed:
            self._active_state.session = refreshed

    def get_elapsed_seconds(self) -> int:
        """Compute the total elapsed seconds for the active session."""

        if not self._active_state:
            return 0
        state = self._active_state
        elapsed = state.elapsedSeconds
        if state.activePause is None and state.resumeReference:
            now = self._utcnow()
            elapsed += max(0, int((now - state.resumeReference).total_seconds()))
        return elapsed

    def _ensure_session_running(self) -> ActiveSessionState:
        """Return the active state ensuring the session is running."""

        if self._active_state is None:
            raise SessionServiceError("No hay una sesión activa en curso.")
        return self._active_state

    def pause_session(self) -> SessionPauseDTO:
        """Register a pause and freeze the timer."""

        state = self._ensure_session_running()
        if state.activePause is not None:
            raise SessionServiceError("La sesión ya está en pausa.")

        now = self._utcnow()
        if state.resumeReference:
            state.elapsedSeconds += max(0, int((now - state.resumeReference).total_seconds()))
        try:
            pause = self._pause_dao.create_pause(state.session.sessionId or 0, now, state.elapsedSeconds)
        except SessionPauseDAOError as exc:
            logger.error("No fue posible pausar la sesión %s: %s", state.session.sessionId, exc)
            raise SessionServiceError(str(exc)) from exc

        state.activePause = pause
        state.resumeReference = now
        return pause

    def resume_session(self) -> SessionPauseDTO:
        """Finish the active pause and resume the timer."""

        state = self._ensure_session_running()
        pause = state.activePause
        if pause is None:
            raise SessionServiceError("La sesión no está en pausa.")

        now = self._utcnow()
        pause_duration = max(0, int((now - pause.pausedAt).total_seconds()))
        try:
            self._pause_dao.finish_pause(pause.pauseId or 0, now, pause_duration)
        except SessionPauseDAOError as exc:
            logger.error("No fue posible reanudar la sesión %s: %s", state.session.sessionId, exc)
            raise SessionServiceError(str(exc)) from exc

        updated_pause = SessionPauseDTO(
            pauseId=pause.pauseId,
            sessionId=pause.sessionId,
            pausedAt=pause.pausedAt,
            resumedAt=now,
            elapsedSecondsWhenPaused=pause.elapsedSecondsWhenPaused,
            pauseDurationSeconds=pause_duration,
        )
        state.activePause = None
        state.resumeReference = now
        return updated_pause

    def record_evidence(
        self,
        file_path: Path,
        description: str,
        considerations: str,
        observations: str,
    ) -> SessionEvidenceDTO:
        """Persist a captured evidence and update timer checkpoints."""

        state = self._ensure_session_running()
        if state.activePause is not None:
            raise SessionServiceError("No se pueden capturar evidencias mientras la sesión está en pausa.")

        now = self._utcnow()
        elapsed_since_start = self.get_elapsed_seconds()
        elapsed_since_previous: Optional[int]
        if state.lastEvidenceAt is None:
            elapsed_since_previous = elapsed_since_start
        else:
            elapsed_since_previous = max(0, int((now - state.lastEvidenceAt).total_seconds()))

        file_name = file_path.name
        try:
            evidence = self._evidence_dao.create_evidence(
                state.session.sessionId or 0,
                file_name,
                str(file_path),
                description,
                considerations,
                observations,
                now,
                elapsed_since_start,
                elapsed_since_previous,
            )
        except SessionEvidenceDAOError as exc:
            logger.error("No se pudo guardar la evidencia para la sesión %s: %s", state.session.sessionId, exc)
            raise SessionServiceError(str(exc)) from exc

        state.lastEvidenceAt = now
        return evidence

    def list_evidences(self) -> List[SessionEvidenceDTO]:
        """Return the evidences stored for the active session."""

        state = self._ensure_session_running()
        try:
            evidences = self._evidence_dao.list_by_session(state.session.sessionId or 0)
        except SessionEvidenceDAOError as exc:
            logger.error("No se pudieron leer las evidencias de la sesión %s: %s", state.session.sessionId, exc)
            raise SessionServiceError(str(exc)) from exc

        if evidences:
            state.lastEvidenceAt = evidences[-1].createdAt
        return evidences

    def update_evidence(
        self,
        evidence_id: int,
        file_path: Path,
        description: str,
        considerations: str,
        observations: str,
    ) -> None:
        """Update the stored metadata for a given evidence."""

        state = self._ensure_session_running()
        updated_at = self._utcnow()
        try:
            self._evidence_dao.update_evidence(
                evidence_id,
                file_path.name,
                str(file_path),
                description,
                considerations,
                observations,
                updated_at,
            )
        except SessionEvidenceDAOError as exc:
            logger.error("No se pudo actualizar la evidencia %s: %s", evidence_id, exc)
            raise SessionServiceError(str(exc)) from exc

        # Refresh local cache ordering
        evidences = self.list_evidences()
        if evidences:
            state.lastEvidenceAt = evidences[-1].createdAt

    def finalize_session(self) -> SessionDTO:
        """Close the active session and persist the duration."""

        state = self._ensure_session_running()
        if state.activePause is not None:
            raise SessionServiceError("Reanuda la sesión antes de finalizarla.")

        now = self._utcnow()
        total_elapsed = self.get_elapsed_seconds()
        try:
            self._session_dao.close_session(state.session.sessionId or 0, now, total_elapsed)
        except SessionDAOError as exc:
            logger.error("No fue posible finalizar la sesión %s: %s", state.session.sessionId, exc)
            raise SessionServiceError(str(exc)) from exc

        refreshed: Optional[SessionDTO] = None
        try:
            refreshed = self._session_dao.get_session(state.session.sessionId or 0)
        except SessionDAOError as exc:
            logger.error("No fue posible refrescar la sesión %s: %s", state.session.sessionId, exc)
            raise SessionServiceError(str(exc)) from exc
        finally:
            self._active_state = None
        return refreshed or state.session
