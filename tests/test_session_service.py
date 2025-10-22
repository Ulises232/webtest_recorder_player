"""Unit tests for the session service lifecycle using in-memory doubles."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import pytest

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.dtos.session_dto import SessionDTO, SessionEvidenceDTO, SessionPauseDTO
from app.services.session_service import SessionService, SessionServiceError


class FakeSessionDAO:
    """Minimal in-memory DAO to emulate recorder sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[int, SessionDTO] = {}
        self._next_id = 1

    def create_session(
        self,
        name: str,
        initial_url: str,
        docx_url: str,
        evidences_url: str,
        username: str,
        started_at: datetime,
    ) -> SessionDTO:
        session_id = self._next_id
        self._next_id += 1
        dto = SessionDTO(
            sessionId=session_id,
            name=name,
            initialUrl=initial_url,
            docxUrl=docx_url,
            evidencesUrl=evidences_url,
            durationSeconds=0,
            startedAt=started_at,
            endedAt=None,
            username=username,
            createdAt=started_at,
            updatedAt=started_at,
        )
        self._sessions[session_id] = dto
        return dto

    def update_outputs(self, session_id: int, docx_url: str, evidences_url: str, updated_at: datetime) -> None:
        dto = self._sessions[session_id]
        self._sessions[session_id] = replace(dto, docxUrl=docx_url, evidencesUrl=evidences_url, updatedAt=updated_at)

    def close_session(self, session_id: int, ended_at: datetime, duration_seconds: int) -> None:
        dto = self._sessions[session_id]
        self._sessions[session_id] = replace(dto, endedAt=ended_at, durationSeconds=duration_seconds, updatedAt=ended_at)

    def get_session(self, session_id: int) -> SessionDTO:
        return self._sessions[session_id]


class FakeSessionEvidenceDAO:
    """Store evidence DTOs without touching SQL Server."""

    def __init__(self) -> None:
        self._records: Dict[int, SessionEvidenceDTO] = {}
        self._next_id = 1

    def create_evidence(
        self,
        session_id: int,
        file_name: str,
        file_path: str,
        description: str,
        considerations: str,
        observations: str,
        created_at: datetime,
        elapsed_since_start: int,
        elapsed_since_previous: int | None,
    ) -> SessionEvidenceDTO:
        evidence_id = self._next_id
        self._next_id += 1
        dto = SessionEvidenceDTO(
            evidenceId=evidence_id,
            sessionId=session_id,
            fileName=file_name,
            filePath=file_path,
            description=description,
            considerations=considerations,
            observations=observations,
            createdAt=created_at,
            updatedAt=created_at,
            elapsedSinceSessionStartSeconds=elapsed_since_start,
            elapsedSincePreviousEvidenceSeconds=elapsed_since_previous,
        )
        self._records[evidence_id] = dto
        return dto

    def update_evidence(
        self,
        evidence_id: int,
        file_name: str,
        file_path: str,
        description: str,
        considerations: str,
        observations: str,
        updated_at: datetime,
    ) -> None:
        dto = self._records[evidence_id]
        self._records[evidence_id] = replace(
            dto,
            fileName=file_name,
            filePath=file_path,
            description=description,
            considerations=considerations,
            observations=observations,
            updatedAt=updated_at,
        )

    def list_by_session(self, session_id: int) -> List[SessionEvidenceDTO]:
        return [dto for dto in self._records.values() if dto.sessionId == session_id]


class FakeSessionPauseDAO:
    """Keep track of pauses in memory."""

    def __init__(self) -> None:
        self._records: Dict[int, SessionPauseDTO] = {}
        self._next_id = 1

    def create_pause(self, session_id: int, paused_at: datetime, elapsed_seconds_when_paused: int) -> SessionPauseDTO:
        pause_id = self._next_id
        self._next_id += 1
        dto = SessionPauseDTO(
            pauseId=pause_id,
            sessionId=session_id,
            pausedAt=paused_at,
            resumedAt=None,
            elapsedSecondsWhenPaused=elapsed_seconds_when_paused,
            pauseDurationSeconds=None,
        )
        self._records[pause_id] = dto
        return dto

    def finish_pause(self, pause_id: int, resumed_at: datetime, pause_duration_seconds: int) -> None:
        dto = self._records[pause_id]
        self._records[pause_id] = replace(dto, resumedAt=resumed_at, pauseDurationSeconds=pause_duration_seconds)

    def list_by_session(self, session_id: int) -> List[SessionPauseDTO]:
        return [dto for dto in self._records.values() if dto.sessionId == session_id]


class DeterministicSessionService(SessionService):
    """Session service that advances one second on each `_utcnow` call."""

    def __init__(
        self,
        session_dao: FakeSessionDAO,
        evidence_dao: FakeSessionEvidenceDAO,
        pause_dao: FakeSessionPauseDAO,
        start_time: datetime,
    ) -> None:
        super().__init__(session_dao, evidence_dao, pause_dao)
        self._current_time = start_time

    def _utcnow(self) -> datetime:  # type: ignore[override]
        current = self._current_time
        self._current_time = current + timedelta(seconds=1)
        return current


def test_session_lifecycle_records_evidences_and_pauses() -> None:
    """Sessions should register evidences, pauses and accumulate durations."""

    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    service = DeterministicSessionService(FakeSessionDAO(), FakeSessionEvidenceDAO(), FakeSessionPauseDAO(), start)

    session = service.begin_session("Demo", "http://example", "doc.docx", "evidences", "alice")
    assert session.sessionId == 1
    assert service.get_active_session() is not None

    evidence1 = service.record_evidence(Path("shot1.png"), "Primer paso", "", "")
    assert evidence1.elapsedSinceSessionStartSeconds == 2

    pause = service.pause_session()
    assert pause.elapsedSecondsWhenPaused == 3

    service.resume_session()
    evidence2 = service.record_evidence(Path("shot2.png"), "Segundo", "", "")
    assert evidence2.elapsedSinceSessionStartSeconds == 5
    assert evidence2.elapsedSincePreviousEvidenceSeconds == 4

    evidences = service.list_evidences()
    assert len(evidences) == 2

    finished = service.finalize_session()
    assert finished.durationSeconds == 7
    assert service.get_active_session() is None


def test_record_evidence_without_session_raises() -> None:
    """Trying to capture without an active session should fail."""

    service = DeterministicSessionService(FakeSessionDAO(), FakeSessionEvidenceDAO(), FakeSessionPauseDAO(), datetime.now(timezone.utc))
    with pytest.raises(SessionServiceError):
        service.record_evidence(Path("invalid.png"), "", "", "")
