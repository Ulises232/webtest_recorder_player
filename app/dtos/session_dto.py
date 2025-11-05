"""Data transfer objects for recorder sessions and related artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SessionDTO:
    """Represent a persisted recorder session."""

    sessionId: Optional[int]
    name: str
    initialUrl: str
    docxUrl: str
    evidencesUrl: str
    cardId: Optional[int]
    durationSeconds: int
    startedAt: datetime
    endedAt: Optional[datetime]
    username: str
    createdAt: datetime
    updatedAt: datetime


@dataclass
class SessionEvidenceDTO:
    """Represent a single evidence captured within a recorder session."""

    evidenceId: Optional[int]
    sessionId: int
    fileName: str
    filePath: str
    description: str
    considerations: str
    observations: str
    createdAt: datetime
    updatedAt: datetime
    elapsedSinceSessionStartSeconds: int
    elapsedSincePreviousEvidenceSeconds: Optional[int]


@dataclass
class SessionPauseDTO:
    """Represent a pause interval registered for a recorder session."""

    pauseId: Optional[int]
    sessionId: int
    pausedAt: datetime
    resumedAt: Optional[datetime]
    elapsedSecondsWhenPaused: int
    pauseDurationSeconds: Optional[int]
