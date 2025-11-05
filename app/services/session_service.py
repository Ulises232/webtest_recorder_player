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
    resumeReference: Optional[datetime]
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
        card_id: Optional[int] = None,
    ) -> SessionDTO:
        """Create a new session and keep it as the active one."""

        if self._active_state is not None:
            raise SessionServiceError("Ya existe una sesión activa. Finalízala antes de iniciar otra.")

        if card_id is not None:
            try:
                existing = self._session_dao.get_session_by_card(card_id)
            except SessionDAOError as exc:
                logger.error("No fue posible verificar la sesión asociada a la tarjeta %s: %s", card_id, exc)
                raise SessionServiceError(str(exc)) from exc
            if existing is not None:
                raise SessionServiceError("Ya existe una sesión registrada para la tarjeta seleccionada.")

        started_at = self._utcnow()
        try:
            session = self._session_dao.create_session(
                name,
                initial_url,
                docx_url,
                evidences_url,
                username,
                started_at,
                card_id=card_id,
            )
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

    def get_session_by_card(self, card_id: int) -> Optional[SessionDTO]:
        """Return the persisted session linked to the provided card identifier."""

        try:
            return self._session_dao.get_session_by_card(card_id)
        except SessionDAOError as exc:
            logger.error("No fue posible consultar la sesión asociada a la tarjeta %s: %s", card_id, exc)
            raise SessionServiceError(str(exc)) from exc

    def list_sessions(self, username: Optional[str] = None, limit: int = 100) -> List[SessionDTO]:
        """Return the most recent sessions for the dashboard."""

        try:
            return self._session_dao.list_sessions(limit=limit, username=username)
        except SessionDAOError as exc:
            logger.error("No fue posible consultar las sesiones: %s", exc)
            raise SessionServiceError(str(exc)) from exc

    def update_session_details(
        self,
        session_id: int,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
        requesting_username: str,
    ) -> SessionDTO:
        """Update metadata ensuring the requester owns the session."""

        if not requesting_username:
            raise SessionServiceError("Debes iniciar sesión para editar una sesión.")

        try:
            session = self._session_dao.get_session(session_id)
        except SessionDAOError as exc:
            logger.error("No fue posible consultar la sesión %s: %s", session_id, exc)
            raise SessionServiceError(str(exc)) from exc

        if session is None:
            raise SessionServiceError("La sesión solicitada no existe.")

        if session.username.lower() != requesting_username.lower():
            raise SessionServiceError("Solo el usuario que creó la sesión puede editarla.")

        updated_at = self._utcnow()
        new_name = name or session.name
        new_initial = initial_url or session.initialUrl
        new_doc = docx_url or session.docxUrl
        new_evid = evidences_url or session.evidencesUrl

        try:
            self._session_dao.update_session_details(
                session_id,
                new_name,
                new_initial,
                new_doc,
                new_evid,
                updated_at,
            )
            refreshed = self._session_dao.get_session(session_id)
        except SessionDAOError as exc:
            logger.error("No fue posible actualizar la sesión %s: %s", session_id, exc)
            raise SessionServiceError(str(exc)) from exc

        if refreshed and self._active_state and self._active_state.session.sessionId == session_id:
            self._active_state.session = refreshed

        return refreshed or session

    def delete_session(self, session_id: int, requesting_username: str) -> None:
        """Delete a session verifying the requester owns it."""

        if not requesting_username:
            raise SessionServiceError("Debes iniciar sesión para eliminar una sesión.")

        try:
            session = self._session_dao.get_session(session_id)
        except SessionDAOError as exc:
            logger.error("No fue posible consultar la sesión %s: %s", session_id, exc)
            raise SessionServiceError(str(exc)) from exc

        if session is None:
            raise SessionServiceError("La sesión solicitada no existe.")

        if session.username.lower() != requesting_username.lower():
            raise SessionServiceError("Solo el usuario que creó la sesión puede eliminarla.")

        try:
            self._session_dao.delete_session(session_id)
        except SessionDAOError as exc:
            logger.error("No fue posible eliminar la sesión %s: %s", session_id, exc)
            raise SessionServiceError(str(exc)) from exc

        if self._active_state and self._active_state.session.sessionId == session_id:
            self._active_state = None

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

    def get_session_with_evidences(
        self,
        session_id: int,
        requesting_username: str,
    ) -> tuple[SessionDTO, List[SessionEvidenceDTO]]:
        """Return a session and its evidences enforcing ownership."""

        if not requesting_username:
            raise SessionServiceError("Debes iniciar sesión para editar una sesión.")

        try:
            session = self._session_dao.get_session(session_id)
        except SessionDAOError as exc:
            logger.error("No fue posible consultar la sesión %s: %s", session_id, exc)
            raise SessionServiceError(str(exc)) from exc

        if session is None:
            raise SessionServiceError("La sesión solicitada no existe.")

        if session.username.lower() != requesting_username.lower():
            raise SessionServiceError("Solo el usuario que creó la sesión puede editarla.")

        try:
            evidences = self._evidence_dao.list_by_session(session_id)
        except SessionEvidenceDAOError as exc:
            logger.error("No fue posible consultar las evidencias de la sesión %s: %s", session_id, exc)
            raise SessionServiceError(str(exc)) from exc

        return session, evidences

    def activate_session_for_dashboard_edit(
        self,
        session_id: int,
        requesting_username: str,
    ) -> tuple[SessionDTO, List[SessionEvidenceDTO]]:
        """Set an existing session as active so the GUI can edit it."""

        session, evidences = self.get_session_with_evidences(session_id, requesting_username)
        if self._active_state and self._active_state.session.sessionId != session_id:
            raise SessionServiceError("Finaliza la sesión activa antes de editar otra desde el tablero.")

        last_evidence_at = evidences[-1].createdAt if evidences else None
        elapsed_seconds = session.durationSeconds or 0

        if self._active_state and self._active_state.session.sessionId == session_id:
            state = self._active_state
            state.session = session
            state.elapsedSeconds = elapsed_seconds
            state.lastEvidenceAt = last_evidence_at
            state.resumeReference = None
            state.activePause = None
        else:
            self._active_state = ActiveSessionState(
                session=session,
                resumeReference=None,
                elapsedSeconds=elapsed_seconds,
                lastEvidenceAt=last_evidence_at,
                activePause=None,
            )

        return session, evidences

    def clear_active_session(self) -> None:
        """Release the active session reference without persisting changes."""

        self._active_state = None

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

    def update_session_evidence_details(
        self,
        session_id: int,
        evidence_id: int,
        file_path: Path,
        description: str,
        considerations: str,
        observations: str,
        requesting_username: str,
    ) -> None:
        """Allow dashboard edits for evidence metadata enforcing ownership."""

        if not requesting_username:
            raise SessionServiceError("Debes iniciar sesión para editar evidencias.")

        try:
            session = self._session_dao.get_session(session_id)
        except SessionDAOError as exc:
            logger.error("No fue posible consultar la sesión %s: %s", session_id, exc)
            raise SessionServiceError(str(exc)) from exc

        if session is None:
            raise SessionServiceError("La sesión solicitada no existe.")

        if session.username.lower() != requesting_username.lower():
            raise SessionServiceError("Solo el usuario que creó la sesión puede editar sus evidencias.")

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
            logger.error("No fue posible actualizar la evidencia %s: %s", evidence_id, exc)
            raise SessionServiceError(str(exc)) from exc

        if self._active_state and self._active_state.session.sessionId == session_id:
            try:
                evidences = self._evidence_dao.list_by_session(session_id)
            except SessionEvidenceDAOError as exc:
                logger.warning(
                    "No se pudieron refrescar las evidencias de la sesión activa %s tras una edición: %s",
                    session_id,
                    exc,
                )
                return
            if evidences:
                self._active_state.lastEvidenceAt = evidences[-1].createdAt
