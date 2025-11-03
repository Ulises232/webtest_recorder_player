import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config.ai_config import AIConfiguration
from app.daos.card_ai_output_dao import CardAIOutputDAOError
from app.dtos.ai_settings_dto import AIProviderRuntimeDTO, ResolvedAIConfigurationDTO
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
        self.deleted: List[int] = []
        self.fail_on_delete = False
        self.fail_on_mark = False
        self.marked_best: List[int] = []
        self.fail_on_mark_dde = False
        self.marked_dde: List[int] = []

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
        dto.isBest = False
        dto.ddeGenerated = False
        self.created.append(dto)
        return dto

    def list_by_card(self, card_id: int, limit: int = 50):  # pragma: no cover - no se usa en estas pruebas
        return []

    def delete_output(self, output_id: int) -> None:
        """Simulate the deletion of an output entry."""

        if self.fail_on_delete:
            raise CardAIOutputDAOError("boom")
        self.deleted.append(output_id)

    def mark_best_output(self, output_id: int):
        """Flag the provided output identifier as the preferred one."""

        if self.fail_on_mark:
            raise CardAIOutputDAOError("boom")
        dto = next((item for item in self.created if item.outputId == output_id), None)
        if not dto:
            raise CardAIOutputDAOError("missing")
        for item in self.created:
            item.isBest = item.outputId == output_id
        self.marked_best.append(output_id)
        return dto

    def mark_dde_generated(self, output_id: int, generated: bool):
        """Toggle the DDE generated flag for the provided output identifier."""

        if self.fail_on_mark_dde:
            raise CardAIOutputDAOError("boom")
        dto = next((item for item in self.created if item.outputId == output_id), None)
        if not dto:
            raise CardAIOutputDAOError("missing")
        dto.ddeGenerated = generated
        if generated:
            self.marked_dde.append(output_id)
        else:
            try:
                self.marked_dde.remove(output_id)
            except ValueError:
                pass
        return dto


class FakeContextService:
    """Provide deterministic context snippets for the prompt builder tests."""

    def __init__(self) -> None:
        self.receivedQueries: List[str] = []
        self.contextText = "Título: Demo previo\nDescripción: Caso histórico"
        self.contextTitles = ["EA-100 Ajuste de vencimientos"]
        self.reindexed = 0

    def search_context(self, query: str, limit: int = 3):
        self.receivedQueries.append(query)
        return self.contextText, self.contextTitles

    def index_from_database(self, limit: int = 500):  # pragma: no cover - usado indirectamente
        self.reindexed += 1
        return self.reindexed


class FakeAIConfigurationService:
    """Provide deterministic provider settings for the service tests."""

    def __init__(
        self,
        provider_key: str = "local",
        base_url: str = "http://127.0.0.1:1234/v1",
        use_rag_local: bool = True,
        api_key: Optional[str] = None,
    ) -> None:
        display_name = "Proveedor de prueba"
        self._providers = [
            AIProviderRuntimeDTO(
                providerKey=provider_key,
                displayName=display_name,
                baseUrl=base_url,
                apiKey=api_key,
                orgId=None,
                modelName="qwen/qwen2.5-vl-7b",
                extra={},
                favorite=True,
            )
        ]
        self._resolved = ResolvedAIConfigurationDTO(
            providerKey=provider_key,
            displayName=display_name,
            baseUrl=base_url,
            apiKey=api_key,
            orgId=None,
            modelName="qwen/qwen2.5-vl-7b",
            temperature=0.35,
            topP=0.9,
            maxTokens=10000,
            timeoutSeconds=180,
            useRagLocal=use_rag_local,
            extra={},
        )

    def resolve_configuration(self, selected_provider: Optional[str] = None) -> ResolvedAIConfigurationDTO:
        """Return the resolved configuration ignoring the requested key."""

        return self._resolved

    def list_providers(self) -> List[AIProviderRuntimeDTO]:
        """Return the available providers."""

        return list(self._providers)

    def get_default_provider_key(self) -> str:
        """Expose the favorite provider key."""

        return self._providers[0].providerKey


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


def codeblock_http_post(*_args, **_kwargs) -> FakeResponse:
    """Return a fake response wrapping the JSON output in markdown fences."""

    return FakeResponse(
        {
            "id": "chatcmpl-2",
            "model": "qwen/qwen2.5-vl-7b",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "```json\n{\n  \"titulo\": \"Demo cercado\"\n}\n```",
                    }
                }
            ],
            "usage": {"total_tokens": 12},
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
        FakeAIConfigurationService(),
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


def test_delete_output_delegates_to_dao() -> None:
    """Deleting history entries should invoke the DAO helper."""

    fake_output = FakeOutputDAO()
    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        fake_output,
        FakeAIConfigurationService(),
        http_post=successful_http_post,
    )

    service.delete_output(42)

    assert fake_output.deleted == [42]


def test_delete_output_wraps_dao_errors() -> None:
    """DAO failures during deletion must be surfaced as service errors."""

    fake_output = FakeOutputDAO()
    fake_output.fail_on_delete = True
    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        fake_output,
        FakeAIConfigurationService(),
        http_post=successful_http_post,
    )

    with pytest.raises(CardAIServiceError):
        service.delete_output(99)


def test_save_draft_persists_input_and_marks_as_draft() -> None:
    """Drafts should be flagged without contacting the LLM."""

    fake_input = FakeInputDAO()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        FakeOutputDAO(),
        FakeAIConfigurationService(),
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
        FakeAIConfigurationService(),
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
    assert result.output.ddeGenerated is False


def test_generate_document_parses_markdown_fenced_json() -> None:
    """Responses with markdown code fences should be sanitized before decoding."""

    fake_input = FakeInputDAO()
    fake_output = FakeOutputDAO()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        fake_output,
        FakeAIConfigurationService(),
        http_post=codeblock_http_post,
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
    assert result.output.content["titulo"] == "Demo cercado"


def test_generate_document_handles_llm_errors() -> None:
    """Non-200 responses from the LLM should raise a service error."""

    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        FakeOutputDAO(),
        FakeAIConfigurationService(),
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
        FakeAIConfigurationService(),
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


def test_generate_document_injects_retrieved_context() -> None:
    """The conversation should include recovered context and store titles in the output."""

    captured: Dict[str, object] = {}

    def capturing_http_post(*_args, **kwargs) -> FakeResponse:
        captured["payload"] = kwargs.get("json")
        return successful_http_post()

    fake_input = FakeInputDAO()
    fake_output = FakeOutputDAO()
    context_service = FakeContextService()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        fake_output,
        FakeAIConfigurationService(),
        http_post=capturing_http_post,
        context_service=context_service,
    )

    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",  # pragma: no branch - datos de prueba
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
    )

    result = service.generate_document(payload)

    payload_sent = captured.get("payload")
    assert isinstance(payload_sent, dict)
    messages = payload_sent["messages"]  # type: ignore[index]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "assistant"
    assert "Contexto extendido" in messages[1]["content"]
    assert "Título: Demo previo" in messages[1]["content"]
    assert messages[2]["role"] == "user"
    assert context_service.receivedQueries[0].startswith("EA-172")
    assert result.output.content["usados_como_contexto"] == context_service.contextTitles


def test_generate_document_uses_openai_factory_when_provider_remote() -> None:
    """Remote providers should rely on the injected OpenAI client factory."""

    captured: Dict[str, object] = {}

    def fake_factory(api_key: str, base_url: Optional[str], org_id: Optional[str], timeout: int) -> object:
        captured["factory_args"] = (api_key, base_url, org_id, timeout)

        class _Completions:
            @staticmethod
            def create(**kwargs: object) -> Dict[str, object]:
                captured["openai_payload"] = kwargs
                return {
                    "id": "chatcmpl-openai",
                    "model": "gpt-4o-mini",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps({"titulo": "OpenAI"}),
                            }
                        }
                    ],
                    "usage": {"total_tokens": 42},
                }

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        return _Client()

    config_service = FakeAIConfigurationService(
        provider_key="openai_mini",
        base_url=None,
        use_rag_local=False,
        api_key="sk-test",
    )
    fake_input = FakeInputDAO()
    fake_output = FakeOutputDAO()
    context_service = FakeContextService()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        fake_output,
        config_service,
        context_service=context_service,
        openai_client_factory=fake_factory,
    )

    payload = CardAIRequestDTO(
        cardId=1,
        tipo="INCIDENCIA",
        descripcion="Descripción",
        analisis="",
        recomendaciones="",
        cosasPrevenir="",
        infoAdicional="",
        providerKey="openai_mini",
    )

    result = service.generate_document(payload)

    assert captured["factory_args"] == ("sk-test", None, None, 180)
    assert "messages" in captured["openai_payload"]
    assert context_service.receivedQueries == []
    assert "usados_como_contexto" not in result.output.content


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
        FakeAIConfigurationService(),
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
        FakeAIConfigurationService(),
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


def test_mark_output_as_best_reindexes_context() -> None:
    """Selecting a preferred result should update the DAO and reindex context."""

    fake_input = FakeInputDAO()
    fake_output = FakeOutputDAO()
    context_service = FakeContextService()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        fake_output,
        FakeAIConfigurationService(),
        http_post=successful_http_post,
        context_service=context_service,
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
    updated = service.mark_output_as_best(result.output.outputId)

    assert updated.isBest is True
    assert fake_output.marked_best == [result.output.outputId]
    assert context_service.reindexed == 1


def test_mark_output_as_best_wraps_dao_errors() -> None:
    """DAO failures while marking the preferred result should bubble up as service errors."""

    fake_output = FakeOutputDAO()
    fake_output.fail_on_mark = True
    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        fake_output,
        FakeAIConfigurationService(),
        http_post=successful_http_post,
    )

    with pytest.raises(CardAIServiceError):
        service.mark_output_as_best(1)


def test_set_output_dde_generated_updates_flag() -> None:
    """Marking an output as DDE generated should delegate to the DAO."""

    fake_input = FakeInputDAO()
    fake_output = FakeOutputDAO()
    service = CardAIService(
        FakeCardDAO(),
        fake_input,
        fake_output,
        FakeAIConfigurationService(),
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
    updated = service.set_output_dde_generated(result.output.outputId, True)

    assert updated.ddeGenerated is True
    assert fake_output.marked_dde == [result.output.outputId]

    updated = service.set_output_dde_generated(result.output.outputId, False)
    assert updated.ddeGenerated is False


def test_set_output_dde_generated_wraps_dao_errors() -> None:
    """DAO failures when toggling the DDE flag should raise service errors."""

    fake_output = FakeOutputDAO()
    fake_output.fail_on_mark_dde = True
    service = CardAIService(
        FakeCardDAO(),
        FakeInputDAO(),
        fake_output,
        FakeAIConfigurationService(),
        http_post=successful_http_post,
    )

    with pytest.raises(CardAIServiceError):
        service.set_output_dde_generated(1, True)
