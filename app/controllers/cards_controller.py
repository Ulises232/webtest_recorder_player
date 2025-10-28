"""Controller dedicated to the card-based AI generation flow."""

from __future__ import annotations

from typing import List, Optional

from app.dtos.card_ai_dto import (
    CardAIInputPayload,
    CardAIInputRecord,
    CardAIOutputRecord,
    CardFilters,
    CardSummary,
    GenerationResult,
)
from app.services.card_ai_service import CardAIService, CardAIServiceError


class CardsControllerError(RuntimeError):
    """Raised when the controller cannot complete the requested action."""


class CardsController:
    """Expose high-level operations required by the AI generation view."""

    def __init__(self, service: CardAIService) -> None:
        """Persist the service dependency used by the controller."""

        self._service = service

    def listCards(self, filters: Optional[CardFilters] = None) -> List[CardSummary]:
        """Return cards according to the provided filters."""

        try:
            return self._service.listCards(filters)
        except CardAIServiceError as exc:
            raise CardsControllerError(str(exc)) from exc

    def calculateCompleteness(self, payload: CardAIInputPayload) -> int:
        """Delegate the completeness calculation to the service."""

        return self._service.calculateCompleteness(payload)

    def loadLatestInput(self, card_id: int) -> Optional[CardAIInputRecord]:
        """Load the most recent saved input for the specified card."""

        try:
            return self._service.loadLatestInput(card_id)
        except CardAIServiceError as exc:
            raise CardsControllerError(str(exc)) from exc

    def saveDraft(self, payload: CardAIInputPayload) -> CardAIInputRecord:
        """Persist the captured inputs without calling the LLM."""

        try:
            return self._service.saveDraft(payload)
        except CardAIServiceError as exc:
            raise CardsControllerError(str(exc)) from exc

    def generateDocument(self, payload: CardAIInputPayload) -> GenerationResult:
        """Trigger the LLM using the provided payload."""

        try:
            return self._service.generateDocument(payload)
        except CardAIServiceError as exc:
            raise CardsControllerError(str(exc)) from exc

    def regenerateFromInput(self, input_id: int) -> GenerationResult:
        """Re-run the LLM using a previously stored input."""

        try:
            return self._service.regenerateFromInput(input_id)
        except CardAIServiceError as exc:
            raise CardsControllerError(str(exc)) from exc

    def listOutputs(self, card_id: int) -> List[CardAIOutputRecord]:
        """Return the history of LLM generations for a card."""

        try:
            return self._service.listOutputs(card_id)
        except CardAIServiceError as exc:
            raise CardsControllerError(str(exc)) from exc


__all__ = ["CardsController", "CardsControllerError"]
