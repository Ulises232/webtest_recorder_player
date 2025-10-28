"""Data transfer objects for the card AI generation workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CardFilters:
    """Represent filter options used to load cards from the catalog."""

    tipo: Optional[str]
    status: Optional[str]
    startDate: Optional[datetime]
    endDate: Optional[datetime]
    searchText: str


@dataclass
class CardSummary:
    """Describe the key information displayed in the card listing."""

    cardId: int
    title: str
    tipo: str
    status: str
    createdAt: Optional[datetime]


@dataclass
class CardAIInputPayload:
    """Hold the raw values captured from the user interface."""

    cardId: int
    tipo: str
    analisisDescProblema: Optional[str]
    analisisRevisionSistema: Optional[str]
    analisisDatos: Optional[str]
    analisisCompReglas: Optional[str]
    recoInvestigacion: Optional[str]
    recoSolucionTemporal: Optional[str]
    recoImplMejoras: Optional[str]
    recoComStakeholders: Optional[str]
    recoDocumentacion: Optional[str]


@dataclass
class CardAIInputRecord(CardAIInputPayload):
    """Persisted representation of an input payload stored in SQL Server."""

    inputId: Optional[int]
    completenessPct: int
    isDraft: bool
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]


@dataclass
class CardAIOutputRecord:
    """Represent a stored LLM generation associated with a card."""

    outputId: Optional[int]
    cardId: int
    inputId: Optional[int]
    llmId: Optional[str]
    llmModel: Optional[str]
    llmUsage: Dict[str, Any]
    content: Dict[str, Any]
    createdAt: Optional[datetime]


@dataclass
class LLMGenerationResponse:
    """Capture the relevant data returned by the LLM service."""

    llmId: Optional[str]
    model: Optional[str]
    usage: Dict[str, Any]
    content: Dict[str, Any]


@dataclass
class GenerationResult:
    """Expose the data returned to the view after calling the LLM."""

    inputRecord: CardAIInputRecord
    outputRecord: CardAIOutputRecord
    completenessPct: int
