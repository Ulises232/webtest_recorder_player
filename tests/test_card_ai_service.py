import json
from datetime import datetime, timezone
from typing import Dict, List

import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config.ai_config import AIConfiguration
from app.dtos.card_ai_dto import CardAIRequestDTO, CardDTO, CardFiltersDTO
from app.services.card_ai_service import CardAIService, CardAIServiceError


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "app" / "prompts"
DEFAULT_SYSTEM_PROMPT = (PROMPTS_DIR / "system_prompt.yaml").read_text(encoding="utf-8").strip()


class FakeCardDAO:
    """Minimal DAO providing cards for the tests."""

    def __init__(self) -> None:
        self.cards: Dict[int, CardDTO] = {
            1: CardDTO(
                cardId=1,
                title="EA-172 No genera vencimientos",
                cardType="INCIDENCIA",
                status="pending",
                createdAt=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updatedAt=datetime(2024, 1, 2, tzinfo=timezone.utc),
                ticketId="EA-172",
                branchKey="feature/ea-172",
            )
        }

    def list_cards(self, filters: CardFiltersDTO, limit: int = 200) -> List[CardDTO]:  # pragma: no cover - utilizado indirectamente
        return list(self.cards.values())[:limit]

    def get_card_title(self, card_id: int) -> str:
        if card_id not in self.cards:
            raise RuntimeError("not found")
        return self.cards[card_id].title


class FakeInputDAO:
    """Persist inputs in memory for the service tests."""

    def __init__(self) -> None:
        self.created: List[Dict[str, object]] = []
        self._next_id = 1

    def create_input(
        self,
        card_id: int,
        tipo: str,
        descripcion: str,
        analisis: str,
        recomendaciones: str,
        cosas_prevenir: str,
        info_adicional: str,
        completeness_pct: int,
        is_draft: bool,
    ):
        input_id = self._next_id
        self._next_id += 1
        dto = type("InputDTO", (), {})()
        dto.inputId = input_id
        dto.cardId = card_id
        dto.tipo = tipo
        dto.descripcion = descripcion
        dto.analisis = analisis
        dto.recomendaciones = recomendaciones
        dto.cosasPrevenir = cosas_prevenir
        dto.infoAdicional = info_adicional
        dto.completenessPct = completeness_pct
        dto.isDraft = is_draft
        dto.createdAt = datetime.now(timezone.utc)
        dto.updatedAt = dto.createdAt
        self.created.append({"dto": dto, "is_draft": is_draft})
        return dto

    def list_by_card(self, card_id: int, limit: int = 50):  # pragma: no cover - no se usa en estas pruebas
        return []

    def get_input(self, input_id: int):
        for entry in self.created:
            dto = entry["dto"]
            if dto.inputId == input_id:
                return dto
        return None


class FakeOutputDAO:
    """Store LLM outputs without persisting them to SQL Server."""

    def __init__(self) -> None:
        self.created: List[Dict[str, object]] = []
        self._next_id = 1

    def create_output(
        self,
        card_id: int,
        input_id: int,
        llm_id: str,
        llm_model: str,
        llm_usage: dict,
        content: dict,
    ):
        output_id = self._next_id
        self._next_id += 1
        dto = type("OutputDTO", (), {})()
        dto.outputId = output_id
        dto.cardId = card_id
        dto.inputId = input_id
        dto.llmId = llm_id
        dto.llmModel = llm_model
        dto.llmUsage = llm_usage
        dto.content = content
        dto.createdAt = datetime.now(timezone.utc)
        self.created.append(dto)
        return dto

    def list_by_card(self, card_id: int, limit: int = 50):  # pragma: no cover - no se usa en estas pruebas
        return []


class FakeResponse:
    """Minimal requests.Response stand-in used for the LLM client."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code == 200
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


def successful_http_post(*_args, **_kwargs) -> FakeResponse:
    """Return a fake response mimicking a successful completion."""

    return FakeResponse(
        {
            "id": "chatcmpl-1",
            "model": "qwen/qwen2.5-vl-7b",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"titulo": "Demo", "requerimientos_funcionales": []}),
                    }
                }
            ],
            "usage": {"total_tokens": 10},
        }
    )


def failing_http_post(*_args, **_kwargs) -> FakeResponse:
    """Return a fake response indicating a server failure."""

    return FakeResponse({}, status_code=500)


def test_calculate_completeness_counts_non_empty_fields() -> None:
    """The completeness helper should consider the number of filled fields."""

    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        FakeOutputDAO(),
        http_post=successful_http_post,
    )
    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Uno",
        analisis="Dos",
        recomendaciones="",
        cosasPrevenir=None,
        infoAdicional="Tres",
    )
    assert CardAIService.calculate_completeness(payload) == 60


def test_save_draft_persists_input_and_marks_as_draft() -> None:
    """Drafts should be flagged without contacting the LLM."""

    fake_input = FakeInputDAO()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        FakeOutputDAO(),
        http_post=successful_http_post,
    )
    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
    )
    dto = service.save_draft(payload)
    assert dto.isDraft is True
    assert fake_input.created[0]["is_draft"] is True


def test_generate_document_calls_llm_and_stores_output() -> None:
    """A successful generation should persist input and output DTOs."""

    fake_input = FakeInputDAO()
    fake_output = FakeOutputDAO()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        fake_output,
        http_post=successful_http_post,
    )
    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
    )
    result = service.generate_document(payload)
    assert result.input.inputId == fake_input.created[0]["dto"].inputId
    assert result.output.outputId == fake_output.created[0].outputId
    assert result.output.content["titulo"] == "Demo"


def test_generate_document_handles_llm_errors() -> None:
    """Non-200 responses from the LLM should raise a service error."""

    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        FakeOutputDAO(),
        http_post=failing_http_post,
    )
    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
    )
    with pytest.raises(CardAIServiceError):
        service.generate_document(payload)


def test_generate_document_sends_system_prompt_first() -> None:
    """The LLM request must prepend the corporate system prompt before user content."""

    captured: Dict[str, object] = {}

    def capturing_http_post(*_args, **kwargs) -> FakeResponse:
        captured["payload"] = kwargs.get("json")
        return successful_http_post()

    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        FakeOutputDAO(),
        http_post=capturing_http_post,
    )
    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
    )

    service.generate_document(payload)

    payload_sent = captured.get("payload")
    assert isinstance(payload_sent, dict)
    messages = payload_sent["messages"]  # type: ignore[index]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == DEFAULT_SYSTEM_PROMPT
    assert messages[1]["role"] == "user"
    assert "Genera un documento formal" in messages[1]["content"]


def test_generate_document_uses_custom_system_prompt_file(tmp_path) -> None:
    """The loader must read the prompt content from the configured file path."""

    prompt_file = tmp_path / "custom_prompt.yaml"
    prompt_file.write_text("Contenido personalizado", encoding="utf-8")

    captured: Dict[str, object] = {}

    def capturing_http_post(*_args, **kwargs) -> FakeResponse:
        captured["payload"] = kwargs.get("json")
        return successful_http_post()

    config = AIConfiguration({"LM_SYSTEM_PROMPT_PATH": str(prompt_file)})
    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        FakeOutputDAO(),
        configuration=config,
        http_post=capturing_http_post,
    )

    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
    )

    service.generate_document(payload)

    payload_sent = captured.get("payload")
    assert isinstance(payload_sent, dict)
    messages = payload_sent["messages"]  # type: ignore[index]
    assert messages[0]["content"] == "Contenido personalizado"


def test_generate_document_fails_when_system_prompt_missing(tmp_path) -> None:
    """An informative error should be raised if the system prompt file is unavailable."""

    missing_path = tmp_path / "missing_prompt.yaml"
    config = AIConfiguration({"LM_SYSTEM_PROMPT_PATH": str(missing_path)})
    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        FakeOutputDAO(),
        configuration=config,
        http_post=successful_http_post,
    )

    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
    )

    with pytest.raises(CardAIServiceError) as excinfo:
        service.generate_document(payload)

    assert "prompt de sistema" in str(excinfo.value)
