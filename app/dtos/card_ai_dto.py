"""DTOs used by the card AI assistant workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CardDTO:
    """Represent a Jira/Branch History card available for AI generation."""

    cardId: int
    title: str
    cardType: str
    status: str
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]
    ticketId: str
    branchKey: str
    incidentTypeId: Optional[int] = None
    incidentTypeName: str = ""
    companyId: Optional[int] = None
    companyName: str = ""
    hasBestSelection: bool = False
    hasDdeGenerated: bool = False


@dataclass
class CardFiltersDTO:
    """Encapsulate filter values applied to the cards grid."""

    cardType: Optional[str] = None
    status: Optional[str] = None
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
    searchText: Optional[str] = None
    bestSelection: Optional[bool] = None
    ddeGenerated: Optional[bool] = None
    incidentTypeId: Optional[int] = None
    companyId: Optional[int] = None


@dataclass
class CardAIInputDTO:
    """Represent a captured prompt for a particular card."""

    inputId: int
    cardId: int
    tipo: str
    descripcion: Optional[str]
    analisis: Optional[str]
    recomendaciones: Optional[str]
    cosasPrevenir: Optional[str]
    infoAdicional: Optional[str]
    completenessPct: int
    isDraft: bool
    createdAt: datetime
    updatedAt: datetime


@dataclass
class CardAIOutputDTO:
    """Represent the JSON document returned by the LLM."""

    outputId: int
    cardId: int
    inputId: Optional[int]
    llmId: Optional[str]
    llmModel: Optional[str]
    llmUsage: Dict[str, Any]
    content: Dict[str, Any]
    createdAt: datetime
    isBest: bool
    ddeGenerated: bool


@dataclass
class CardAIContextDocumentDTO:
    """Expose a simplified view of outputs required for RAG indexing."""

    outputId: int
    cardId: int
    cardTitle: str
    content: Dict[str, Any]


@dataclass
class CardAIHistoryEntryDTO:
    """Combine input and output metadata for history listings."""

    output: CardAIOutputDTO
    input: Optional[CardAIInputDTO]


@dataclass
class CardAIGenerationResultDTO:
    """Return the stored input/output pair after generation."""

    input: CardAIInputDTO
    output: CardAIOutputDTO
    completenessPct: int


@dataclass
class CardAIRequestDTO:
    """Capture the fields provided by the UI before persisting them."""

    cardId: int
    tipo: str
    descripcion: Optional[str]
    analisis: Optional[str]
    recomendaciones: Optional[str]
    cosasPrevenir: Optional[str]
    infoAdicional: Optional[str]
    providerKey: Optional[str] = None
    forceSaveInputs: bool = False


def card_ai_request_from_dict(payload: Dict[str, Any]) -> CardAIRequestDTO:
    """Create a request DTO from a dictionary received from the view."""

    return CardAIRequestDTO(
        cardId=int(payload.get("cardId", 0)),
        tipo=str(payload.get("tipo", "")).strip() or "INCIDENCIA",
        descripcion=payload.get("descripcion"),
        analisis=payload.get("analisis"),
        recomendaciones=payload.get("recomendaciones"),
        cosasPrevenir=payload.get("cosasPrevenir"),
        infoAdicional=payload.get("infoAdicional"),
        providerKey=(
            str(payload.get("providerKey")).strip() or None
            if payload.get("providerKey") is not None
            else None
        ),
        forceSaveInputs=bool(payload.get("forceSaveInputs", False)),
    )


@dataclass
class CatalogOptionDTO:
    """Represent a generic catalog option exposed to the UI layer."""

    optionId: int
    name: str

