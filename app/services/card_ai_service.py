"""Business logic that orchestrates card listing and AI generation."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from app.daos.cards_dao import (
    CardAIInputDAO,
    CardAIInputDAOError,
    CardAIOutputDAO,
    CardAIOutputDAOError,
    CardsDAO,
    CardsDAOError,
)
from app.dtos.card_ai_dto import (
    CardAIInputPayload,
    CardAIInputRecord,
    CardAIOutputRecord,
    CardFilters,
    CardSummary,
    GenerationResult,
)
from app.services.card_prompt_builder import buildUserPrompt
from app.services.llm_client import LLMClientError, LocalLLMClient


class CardAIServiceError(RuntimeError):
    """Raised when the card AI flow cannot be completed."""


class CardAIService:
    """Provide high-level operations for the DDE/HU generator."""

    def __init__(
        self,
        cards_dao: CardsDAO,
        inputs_dao: CardAIInputDAO,
        outputs_dao: CardAIOutputDAO,
        llm_client: LocalLLMClient,
    ) -> None:
        """Store dependencies used across service operations."""

        self._cards_dao = cards_dao
        self._inputs_dao = inputs_dao
        self._outputs_dao = outputs_dao
        self._llm_client = llm_client

    def listCards(self, filters: Optional[CardFilters] = None, limit: int = 250) -> List[CardSummary]:
        """Return cards applying filters both at SQL and in-memory level."""

        try:
            cards = self._cards_dao.listCards(filters, limit=limit)
        except CardsDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        if not filters:
            return cards

        return self._applyFilters(cards, filters)

    def _applyFilters(self, cards: Iterable[CardSummary], filters: CardFilters) -> List[CardSummary]:
        """Apply client-side filters for search text and date ranges."""

        results: List[CardSummary] = []
        text = (filters.searchText or "").strip().lower()
        start = filters.startDate
        end = filters.endDate
        if end and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        for card in cards:
            if text and text not in (card.title or "").lower():
                continue
            if start and card.createdAt and card.createdAt < start:
                continue
            if end and card.createdAt and card.createdAt > end:
                continue
            results.append(card)
        return results

    def calculateCompleteness(self, payload: CardAIInputPayload) -> int:
        """Evaluate how many fields are filled to offer soft validation."""

        values = [
            payload.analisisDescProblema,
            payload.analisisRevisionSistema,
            payload.analisisDatos,
            payload.analisisCompReglas,
            payload.recoInvestigacion,
            payload.recoSolucionTemporal,
            payload.recoImplMejoras,
            payload.recoComStakeholders,
            payload.recoDocumentacion,
        ]
        total = len(values)
        if total == 0:
            return 0
        filled = sum(1 for value in values if isinstance(value, str) and value.strip())
        return round((filled / total) * 100)

    def loadLatestInput(self, card_id: int) -> Optional[CardAIInputRecord]:
        """Return the most recent captured input for the selected card."""

        try:
            return self._inputs_dao.fetchLatestForCard(card_id)
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def saveDraft(self, payload: CardAIInputPayload) -> CardAIInputRecord:
        """Persist a draft version of the captured inputs."""

        completeness = self.calculateCompleteness(payload)
        record = self._buildRecord(payload, completeness, is_draft=True)
        try:
            input_id = self._inputs_dao.insertInput(record)
            stored = self._inputs_dao.fetchById(input_id)
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc
        if stored is None:
            record.inputId = input_id
            now = datetime.now(timezone.utc)
            record.createdAt = now
            record.updatedAt = now
            return record
        return stored

    def generateDocument(self, payload: CardAIInputPayload) -> GenerationResult:
        """Call the LLM using the provided payload and persist the outcome."""

        card = self._ensureCardExists(payload.cardId)
        completeness = self.calculateCompleteness(payload)
        record = self._buildRecord(payload, completeness, is_draft=False)
        try:
            input_id = self._inputs_dao.insertInput(record)
            stored_input = self._inputs_dao.fetchById(input_id) or record
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        prompt = buildUserPrompt(record.tipo or card.tipo, card.title, asdict(record))
        try:
            generation = self._llm_client.generateJson(prompt)
        except LLMClientError as exc:
            raise CardAIServiceError(str(exc)) from exc

        output = CardAIOutputRecord(
            outputId=None,
            cardId=record.cardId,
            inputId=input_id,
            llmId=generation.llmId,
            llmModel=generation.model,
            llmUsage=generation.usage,
            content=generation.content,
            createdAt=None,
        )
        try:
            output_id = self._outputs_dao.insertOutput(output)
            stored_output = self._outputs_dao.fetchById(output_id) or output
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        return GenerationResult(
            inputRecord=stored_input,
            outputRecord=stored_output,
            completenessPct=completeness,
        )

    def regenerateFromInput(self, input_id: int) -> GenerationResult:
        """Re-run the LLM using a previously stored input payload."""

        try:
            existing = self._inputs_dao.fetchById(input_id)
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc
        if existing is None:
            raise CardAIServiceError("No se encontró el registro de entrada solicitado.")

        card = self._ensureCardExists(existing.cardId)

        if existing.isDraft:
            try:
                self._inputs_dao.updateDraftFlag(input_id, False)
                existing.isDraft = False
            except CardAIInputDAOError as exc:
                raise CardAIServiceError(str(exc)) from exc

        prompt = buildUserPrompt(existing.tipo or card.tipo, card.title, asdict(existing))
        try:
            generation = self._llm_client.generateJson(prompt)
        except LLMClientError as exc:
            raise CardAIServiceError(str(exc)) from exc

        output = CardAIOutputRecord(
            outputId=None,
            cardId=existing.cardId,
            inputId=input_id,
            llmId=generation.llmId,
            llmModel=generation.model,
            llmUsage=generation.usage,
            content=generation.content,
            createdAt=None,
        )
        try:
            output_id = self._outputs_dao.insertOutput(output)
            stored_output = self._outputs_dao.fetchById(output_id) or output
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        return GenerationResult(
            inputRecord=existing,
            outputRecord=stored_output,
            completenessPct=existing.completenessPct,
        )

    def listOutputs(self, card_id: int, limit: int = 20) -> List[CardAIOutputRecord]:
        """Retrieve previous generations for the given card."""

        try:
            return self._outputs_dao.listOutputsForCard(card_id, limit=limit)
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def _buildRecord(
        self,
        payload: CardAIInputPayload,
        completeness: int,
        is_draft: bool,
    ) -> CardAIInputRecord:
        """Construct an input record ready for persistence."""

        return CardAIInputRecord(
            inputId=None,
            cardId=payload.cardId,
            tipo=(payload.tipo or "").strip() or "HU",
            analisisDescProblema=payload.analisisDescProblema,
            analisisRevisionSistema=payload.analisisRevisionSistema,
            analisisDatos=payload.analisisDatos,
            analisisCompReglas=payload.analisisCompReglas,
            recoInvestigacion=payload.recoInvestigacion,
            recoSolucionTemporal=payload.recoSolucionTemporal,
            recoImplMejoras=payload.recoImplMejoras,
            recoComStakeholders=payload.recoComStakeholders,
            recoDocumentacion=payload.recoDocumentacion,
            completenessPct=completeness,
            isDraft=is_draft,
            createdAt=None,
            updatedAt=None,
        )

    def _ensureCardExists(self, card_id: int) -> CardSummary:
        """Retrieve the card summary or raise a domain error."""

        try:
            card = self._cards_dao.fetchCard(card_id)
        except CardsDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc
        if card is None:
            raise CardAIServiceError("La tarjeta seleccionada no existe en la base de datos.")
        return card


__all__ = ["CardAIService", "CardAIServiceError"]
