"""Unit tests for the card AI service workflow."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pytest
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.dtos.card_ai_dto import (
    CardAIInputPayload,
    CardAIInputRecord,
    CardAIOutputRecord,
    CardSummary,
    LLMGenerationResponse,
)
from app.services.card_ai_service import CardAIService, CardAIServiceError


class FakeCardsDAO:
    """In-memory implementation that mimics the cards DAO."""

    def __init__(self) -> None:
        self.card = CardSummary(1, "Card title", "INCIDENCIA", "pending", datetime.now(timezone.utc))

    def listCards(self, filters: Optional[CardFilters] = None, limit: int = 250) -> List[CardSummary]:
        return [self.card]

    def fetchCard(self, card_id: int) -> Optional[CardSummary]:
        if card_id == self.card.cardId:
            return self.card
        return None


class FakeInputDAO:
    """In-memory storage that emulates card input persistence."""

    def __init__(self) -> None:
        self.records: Dict[int, CardAIInputRecord] = {}
        self.next_id = 1

    def insertInput(self, record: CardAIInputRecord) -> int:
        identifier = self.next_id
        self.next_id += 1
        stored = replace(record, inputId=identifier, createdAt=datetime.now(timezone.utc), updatedAt=datetime.now(timezone.utc))
        self.records[identifier] = stored
        return identifier

    def fetchById(self, input_id: int) -> Optional[CardAIInputRecord]:
        return self.records.get(input_id)

    def fetchLatestForCard(self, card_id: int) -> Optional[CardAIInputRecord]:
        for record in reversed(list(self.records.values())):
            if record.cardId == card_id:
                return record
        return None

    def updateDraftFlag(self, input_id: int, is_draft: bool) -> None:
        record = self.records.get(input_id)
        if record:
            self.records[input_id] = replace(record, isDraft=is_draft, updatedAt=datetime.now(timezone.utc))


class FakeOutputDAO:
    """In-memory storage that emulates card output persistence."""

    def __init__(self) -> None:
        self.records: Dict[int, CardAIOutputRecord] = {}
        self.next_id = 1

    def insertOutput(self, record: CardAIOutputRecord) -> int:
        identifier = self.next_id
        self.next_id += 1
        stored = replace(record, outputId=identifier, createdAt=datetime.now(timezone.utc))
        self.records[identifier] = stored
        return identifier

    def fetchById(self, output_id: int) -> Optional[CardAIOutputRecord]:
        return self.records.get(output_id)

    def listOutputsForCard(self, card_id: int, limit: int = 20) -> List[CardAIOutputRecord]:
        return [record for record in self.records.values() if record.cardId == card_id][:limit]


class FakeLLMClient:
    """Capture prompts and return predictable responses for tests."""

    def __init__(self) -> None:
        self.last_prompt: Optional[str] = None

    def generateJson(self, prompt: str) -> LLMGenerationResponse:
        self.last_prompt = prompt
        return LLMGenerationResponse(
            llmId="chat-123",
            model="fake-model",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            content={"titulo": "Documento", "descripcion": "Contenido generado"},
        )


def _build_payload(card_id: int = 1) -> CardAIInputPayload:
    """Helper to create a sample payload with partial data."""

    return CardAIInputPayload(
        cardId=card_id,
        tipo="INCIDENCIA",
        analisisDescProblema="Detalle",
        analisisRevisionSistema="Revisión",
        analisisDatos="Datos",
        analisisCompReglas="Reglas",
        recoInvestigacion="Investigación",
        recoSolucionTemporal="Temporal",
        recoImplMejoras="Mejoras",
        recoComStakeholders="Stakeholders",
        recoDocumentacion="Documentación",
    )


def test_calculate_completeness_counts_filled_fields() -> None:
    """Verify that the completeness percentage reflects filled fields."""

    service = CardAIService(FakeCardsDAO(), FakeInputDAO(), FakeOutputDAO(), FakeLLMClient())
    payload = _build_payload()
    pct = service.calculateCompleteness(payload)
    assert pct == 100

    partial_payload = replace(payload, analisisDatos="", recoDocumentacion="")
    pct_partial = service.calculateCompleteness(partial_payload)
    assert pct_partial == pytest.approx(round(7 / 9 * 100))


def test_generate_document_persists_records_and_calls_llm() -> None:
    """The service should store inputs and outputs and return the result."""

    fake_llm = FakeLLMClient()
    service = CardAIService(FakeCardsDAO(), FakeInputDAO(), FakeOutputDAO(), fake_llm)
    payload = _build_payload()

    result = service.generateDocument(payload)

    assert result.inputRecord.inputId is not None
    assert result.outputRecord.outputId is not None
    assert result.outputRecord.content["titulo"] == "Documento"
    assert "### Análisis" in (fake_llm.last_prompt or "")


def test_regenerate_from_input_uses_existing_payload() -> None:
    """Regeneration should reuse stored inputs and create a new output."""

    fake_llm = FakeLLMClient()
    inputs = FakeInputDAO()
    outputs = FakeOutputDAO()
    service = CardAIService(FakeCardsDAO(), inputs, outputs, fake_llm)

    draft = service.saveDraft(_build_payload())
    assert draft.inputId is not None

    result = service.regenerateFromInput(draft.inputId or 0)
    assert result.outputRecord.outputId is not None
    assert outputs.records


def test_generate_document_raises_error_for_unknown_card() -> None:
    """Attempting to generate a document for an unknown card fails."""

    fake_llm = FakeLLMClient()
    service = CardAIService(FakeCardsDAO(), FakeInputDAO(), FakeOutputDAO(), fake_llm)
    payload = _build_payload(card_id=999)

    with pytest.raises(CardAIServiceError):
        service.generateDocument(payload)
