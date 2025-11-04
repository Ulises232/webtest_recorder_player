"""Business logic for generating DDE/HU documents using the local LLM."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

try:  # pragma: no cover - fallback for environments without requests installed
    import requests
except ModuleNotFoundError:  # pragma: no cover
    from types import SimpleNamespace

    class _RequestsFallbackError(Exception):
        """Raised when the optional `requests` dependency is missing."""

        pass

    def _missing_post(*_args, **_kwargs):  # type: ignore[override]
        raise _RequestsFallbackError("La dependencia 'requests' no está instalada.")

    requests = SimpleNamespace(  # type: ignore[assignment]
        RequestException=_RequestsFallbackError,
        post=_missing_post,
    )

try:  # pragma: no cover - la librería openai es opcional
    from openai import OpenAI  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - depende del entorno
    OpenAI = None  # type: ignore[assignment]

from app.config.ai_config import AIConfiguration
from app.daos.ai_request_log_dao import AIRequestLogDAO, AIRequestLogDAOError
from app.daos.card_ai_input_dao import CardAIInputDAO, CardAIInputDAOError
from app.daos.card_ai_output_dao import CardAIOutputDAO, CardAIOutputDAOError
from app.daos.card_dao import CardDAO, CardDAOError
from app.dtos.ai_settings_dto import AIProviderRuntimeDTO, ResolvedAIConfigurationDTO
from app.dtos.card_ai_dto import (
    CardAIHistoryEntryDTO,
    CardAIInputDTO,
    CardAIRequestDTO,
    CardAIGenerationResultDTO,
    CardAIOutputDTO,
    CardDTO,
    CardFiltersDTO,
)
from app.services.ai_configuration_service import (
    AIConfigurationService,
    AIConfigurationServiceError,
)

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from app.services.rag_context_service import RAGContextService


logger = logging.getLogger(__name__)


class CardAIServiceError(RuntimeError):
    """Raised when the AI assistant cannot complete an operation."""


class CardAIService:
    """Coordinate DAOs and the LLM endpoint to build DDE/HU documents."""

    def __init__(
        self,
        card_dao: CardDAO,
        input_dao: CardAIInputDAO,
        output_dao: CardAIOutputDAO,
        request_log_dao: AIRequestLogDAO,
        configuration_service: AIConfigurationService,
        configuration: Optional[AIConfiguration] = None,
        http_post: Optional[Callable[..., requests.Response]] = None,
        system_prompt_loader: Optional[Callable[[], str]] = None,
        context_service: Optional["RAGContextService"] = None,
        openai_client_factory: Optional[
            Callable[[str, Optional[str], Optional[str], int], object]
        ] = None,
    ) -> None:
        """Store dependencies used by the service."""

        if configuration_service is None:
            raise ValueError("configuration_service es requerido")

        self._card_dao = card_dao
        self._input_dao = input_dao
        self._output_dao = output_dao
        self._request_log_dao = request_log_dao
        self._config = configuration or AIConfiguration()
        self._http_post = http_post or requests.post
        self._system_prompt_loader: Callable[[], str] = (
            system_prompt_loader or self._load_system_prompt_from_file
        )
        self._context_service = context_service
        self._configuration_service = configuration_service
        self._openai_client_factory: Callable[
            [str, Optional[str], Optional[str], int], object
        ] = openai_client_factory or self._default_openai_client_factory

    @staticmethod
    def calculate_completeness(payload: CardAIRequestDTO) -> int:
        """Return the completeness percentage for the provided payload."""

        fields = [
            payload.descripcion,
            payload.analisis,
            payload.recomendaciones,
            payload.cosasPrevenir,
            payload.infoAdicional,
        ]
        filled = sum(1 for field in fields if field and str(field).strip())
        return round(100 * filled / len(fields)) if fields else 0

    def list_cards(self, filters: CardFiltersDTO, limit: int = 200) -> List[CardDTO]:
        """Expose the card catalog for the view layer."""

        try:
            return self._card_dao.list_cards(filters, limit=limit)
        except CardDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def list_providers(self) -> List[AIProviderRuntimeDTO]:
        """Expose the configured AI providers to the presentation layer."""

        try:
            return self._configuration_service.list_providers()
        except AIConfigurationServiceError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def get_default_provider_key(self) -> str:
        """Return the provider key that should be selected by default."""

        try:
            return self._configuration_service.get_default_provider_key()
        except AIConfigurationServiceError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def list_inputs(self, card_id: int, limit: int = 50) -> List[CardAIInputDTO]:
        """Return previous inputs associated with a card."""

        try:
            return self._input_dao.list_by_card(card_id, limit=limit)
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def list_history(self, card_id: int, limit: int = 20) -> List[CardAIHistoryEntryDTO]:
        """Return combined input/output history for a card."""

        try:
            outputs = self._output_dao.list_by_card(card_id, limit=limit)
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        history: List[CardAIHistoryEntryDTO] = []
        for output in outputs:
            input_dto: Optional[CardAIInputDTO] = None
            if output.inputId is not None:
                try:
                    input_dto = self._input_dao.get_input(output.inputId)
                except CardAIInputDAOError as exc:
                    logger.error("No fue posible recuperar la captura %s: %s", output.inputId, exc)
            history.append(CardAIHistoryEntryDTO(output=output, input=input_dto))
        return history

    def delete_output(self, output_id: int) -> None:
        """Remove a stored output document from the database."""

        try:
            self._output_dao.delete_output(output_id)
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def mark_output_as_best(self, output_id: int) -> CardAIOutputDTO:
        """Flag an output as the preferred response for its card."""

        try:
            updated = self._output_dao.mark_best_output(output_id)
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        if self._context_service:
            try:
                self._context_service.index_from_database()
            except Exception as exc:  # pragma: no cover - depende de servicios opcionales
                logger.warning("No fue posible reindexar el contexto tras marcar favorito: %s", exc)

        return updated

    def clear_output_best_flag(self, output_id: int) -> CardAIOutputDTO:
        """Remove the preferred flag from the selected output."""

        try:
            updated = self._output_dao.clear_best_output(output_id)
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        if self._context_service:
            try:
                self._context_service.index_from_database()
            except Exception as exc:  # pragma: no cover - depende de servicios opcionales
                logger.warning(
                    "No fue posible reindexar el contexto tras quitar favorito: %s",
                    exc,
                )

        return updated

    def set_output_dde_generated(self, output_id: int, generated: bool) -> CardAIOutputDTO:
        """Update the flag that tracks whether the output produced a DDE."""

        try:
            return self._output_dao.mark_dde_generated(output_id, generated)
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def save_draft(self, payload: CardAIRequestDTO) -> CardAIInputDTO:
        """Persist the provided data as draft without contacting the LLM."""

        completeness = self.calculate_completeness(payload)
        try:
            return self._input_dao.create_input(
                payload.cardId,
                payload.tipo,
                payload.descripcion,
                payload.analisis,
                payload.recomendaciones,
                payload.cosasPrevenir,
                payload.infoAdicional,
                completeness,
                True,
            )
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

    def _build_user_prompt(
        self,
        tipo: str,
        titulo_card: str,
        payload: CardAIRequestDTO,
    ) -> str:
        """Return the message sent to the LLM following the requested format."""

        data = {
            "descripcion": payload.descripcion or "",
            "analisis": payload.analisis or "",
            "recomendaciones": payload.recomendaciones or "",
            "cosas_prevenir": payload.cosasPrevenir or "",
            "info_adicional": payload.infoAdicional or "",
        }
        base_prompt = (
            "Genera un documento formal alineado con el estándar corporativo de Sistemas Premium.\n\n"
            "Datos de entrada:\n"
            f"- Tipo requerido: {tipo}\n"
            f"- Título de la tarjeta: {titulo_card}\n"
            f"- Descripción: {data['descripcion']}\n"
            f"- Análisis: {data['analisis']}\n"
            f"- Recomendaciones: {data['recomendaciones']}\n"
            f"- Riesgos o puntos a prevenir: {data['cosas_prevenir']}\n"
            f"- Información adicional: {data['info_adicional']}\n\n"
            "Estructura estricta del JSON de salida:\n"
            "{\n"
            "  \"titulo\": string,\n"
            "  \"fecha\": string,\n"
            "  \"hora_inicio\": string,\n"
            "  \"hora_fin\": string,\n"
            "  \"lugar\": \"Sistemas Premium\",\n"
            f"  \"tipo\": \"{tipo}\",\n"
            "  \"descripcion\": string,\n"
            "  \"que_necesitas\": string,\n"
            "  \"para_que_lo_necesitas\": string,\n"
            "  \"como_lo_necesitas\": string,\n"
            "  \"requerimientos_funcionales\": string[],\n"
            "  \"requerimientos_especiales\": string[],\n"
            "  \"criterios_aceptacion\": string[]\n"
            "}\n"
            "Entrega únicamente el JSON final"
        )
        return base_prompt

    @staticmethod
    def _build_context_message(context: str) -> str:
        """Compose the extended context instructions for the LLM conversation."""

        cleaned_context = context.strip()
        return (
            "Contexto extendido recuperado del historial de DDE/HU previos:\n"
            f"{cleaned_context}\n\n"
            "Integra la información anterior únicamente como referencia técnica; evita copiarla textualmente y prioriza la coherencia con el nuevo caso."
        )

    def _build_messages(
        self, system_prompt: str, user_prompt: str, context: str
    ) -> List[Dict[str, str]]:
        """Compose the chat messages sent to any provider."""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        if context.strip():
            messages.append(
                {
                    "role": "assistant",
                    "content": self._build_context_message(context),
                }
            )
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _call_llm(
        self, messages: List[Dict[str, str]], configuration: ResolvedAIConfigurationDTO
    ) -> Dict[str, object]:
        """Invoke the configured provider using the resolved configuration."""

        provider_key = configuration.providerKey
        if provider_key == AIConfigurationService.LOCAL_KEY:
            return self._invoke_local(messages, configuration)
        if provider_key in AIConfigurationService.OPENAI_KEYS:
            return self._invoke_openai(messages, configuration)
        if provider_key == AIConfigurationService.MISTRAL_KEY:
            return self._invoke_mistral(messages, configuration)
        raise CardAIServiceError(f"Proveedor de IA desconocido: {provider_key}")

    def _build_request_audit_payload(
        self,
        payload: CardAIRequestDTO,
        configuration: ResolvedAIConfigurationDTO,
        messages: List[Dict[str, str]],
        context_titles: List[str],
        use_rag: bool,
    ) -> Dict[str, object]:
        """Compose the metadata stored for auditing each AI invocation."""

        return {
            "cardId": payload.cardId,
            "tipo": payload.tipo,
            "providerKey": configuration.providerKey,
            "modelName": configuration.modelName,
            "temperature": configuration.temperature,
            "topP": configuration.topP,
            "maxTokens": configuration.maxTokens,
            "messages": messages,
            "useRag": use_rag,
            "contextTitles": context_titles,
        }

    def generate_document(self, payload: CardAIRequestDTO) -> CardAIGenerationResultDTO:
        """Persist the prompt, invoke the LLM and store the resulting JSON."""

        try:
            titulo = self._card_dao.get_card_title(payload.cardId)
        except CardDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        try:
            resolved_configuration = self._configuration_service.resolve_configuration(
                payload.providerKey
            )
        except AIConfigurationServiceError as exc:
            raise CardAIServiceError(str(exc)) from exc

        try:
            system_prompt = self._system_prompt_loader()
        except CardAIServiceError:
            raise
        except Exception as exc:  # pragma: no cover - depende del sistema de archivos
            raise CardAIServiceError(
                "No fue posible cargar el prompt de sistema solicitado."
            ) from exc

        completeness = self.calculate_completeness(payload)
        try:
            input_dto = self._input_dao.create_input(
                payload.cardId,
                payload.tipo,
                payload.descripcion,
                payload.analisis,
                payload.recomendaciones,
                payload.cosasPrevenir,
                payload.infoAdicional,
                completeness,
                False,
            )
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        prompt = self._build_user_prompt(payload.tipo, titulo, payload)
        context_text = ""
        context_titles: List[str] = []
        use_rag = (
            resolved_configuration.providerKey == AIConfigurationService.LOCAL_KEY
            and resolved_configuration.useRagLocal
            and self._context_service is not None
        )
        if use_rag:
            query_parts = [
                titulo,
                payload.descripcion or "",
                payload.analisis or "",
                payload.recomendaciones or "",
                payload.cosasPrevenir or "",
            ]
            query = " ".join(part for part in query_parts if part).strip()
            if query:
                try:
                    context_text, context_titles = self._context_service.search_context(query)
                except Exception as exc:  # pragma: no cover - depende de librerías opcionales
                    logger.warning("No fue posible recuperar contexto previo: %s", exc)
        messages = self._build_messages(system_prompt, prompt, context_text)
        request_audit_payload = self._build_request_audit_payload(
            payload,
            resolved_configuration,
            messages,
            context_titles,
            use_rag,
        )
        request_payload_serialized = self._serialize_for_log(request_audit_payload)
        response_payload_serialized: Optional[str] = None
        normalized_content: Optional[str] = None

        try:
            llm_response = self._call_llm(messages, resolved_configuration)
        except CardAIServiceError as exc:
            self._log_ai_interaction(
                payload.cardId,
                input_dto.inputId,
                resolved_configuration,
                request_payload_serialized,
                None,
                None,
                False,
                str(exc),
            )
            raise

        response_payload_serialized = self._serialize_for_log(llm_response)
        raw_content: Optional[str] = None
        try:
            raw_content = self._extract_response_content(llm_response)
            normalized_content = self._normalize_json_content(raw_content)
            content_json = json.loads(normalized_content)
        except CardAIServiceError as exc:
            self._log_ai_interaction(
                payload.cardId,
                input_dto.inputId,
                resolved_configuration,
                request_payload_serialized,
                response_payload_serialized,
                normalized_content or raw_content,
                False,
                str(exc),
            )
            raise
        except ValueError as exc:
            error = CardAIServiceError("El modelo no devolvió un JSON válido.")
            self._log_ai_interaction(
                payload.cardId,
                input_dto.inputId,
                resolved_configuration,
                request_payload_serialized,
                response_payload_serialized,
                normalized_content or raw_content,
                False,
                str(error),
            )
            raise error from exc

        if context_titles:
            content_json["usados_como_contexto"] = context_titles

        self._log_ai_interaction(
            payload.cardId,
            input_dto.inputId,
            resolved_configuration,
            request_payload_serialized,
            response_payload_serialized,
            normalized_content,
            True,
            None,
        )

        try:
            output_dto = self._output_dao.create_output(
                payload.cardId,
                input_dto.inputId,
                llm_response.get("id"),
                llm_response.get("model") or resolved_configuration.modelName,
                llm_response.get("usage"),
                content_json,
            )
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        return CardAIGenerationResultDTO(input=input_dto, output=output_dto, completenessPct=completeness)

    def _extract_response_content(self, response: Dict[str, object]) -> str:
        """Return the assistant message content from a chat completion response."""

        try:
            return str(response["choices"][0]["message"]["content"])  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            raise CardAIServiceError(
                "La respuesta del modelo no contiene contenido utilizable."
            ) from exc

    def _invoke_local(
        self, messages: List[Dict[str, str]], configuration: ResolvedAIConfigurationDTO
    ) -> Dict[str, object]:
        """Send the request to a local OpenAI-compatible endpoint."""

        base_url = configuration.baseUrl or self._config.get_api_url()
        if not base_url:
            raise CardAIServiceError(
                "No se encontró la URL base para el proveedor local configurado."
            )
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if configuration.apiKey:
            headers["Authorization"] = f"Bearer {configuration.apiKey}"

        payload = {
            "model": configuration.modelName,
            "messages": messages,
            "temperature": configuration.temperature,
            "top_p": configuration.topP,
            "max_tokens": configuration.maxTokens,
            "stream": False,
        }

        try:
            response = self._http_post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=max(configuration.timeoutSeconds, 1),
            )
        except requests.RequestException as exc:
            raise CardAIServiceError(f"No fue posible contactar al modelo: {exc}") from exc

        if not response.ok:
            raise CardAIServiceError(
                f"Error del modelo {response.status_code}: {response.text.strip()[:200]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise CardAIServiceError("La respuesta del modelo no es JSON válido.") from exc

    def _invoke_mistral(
        self, messages: List[Dict[str, str]], configuration: ResolvedAIConfigurationDTO
    ) -> Dict[str, object]:
        """Send the request to the Mistral HTTP API."""

        if not configuration.apiKey:
            raise CardAIServiceError("No se encontró la API key para el proveedor Mistral.")
        base_url = configuration.baseUrl or "https://api.mistral.ai/v1"
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {configuration.apiKey}",
        }
        payload = {
            "model": configuration.modelName,
            "messages": messages,
            "temperature": configuration.temperature,
            "max_tokens": configuration.maxTokens,
            "response_format": { "type": "json_object" },
        }

        try:
            response = self._http_post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=max(configuration.timeoutSeconds, 1),
            )
        except requests.RequestException as exc:
            raise CardAIServiceError(f"No fue posible contactar al modelo: {exc}") from exc

        if not response.ok:
            raise CardAIServiceError(
                f"Error del modelo {response.status_code}: {response.text.strip()[:200]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise CardAIServiceError("La respuesta del modelo no es JSON válido.") from exc

    def _invoke_openai(
        self, messages: List[Dict[str, str]], configuration: ResolvedAIConfigurationDTO
    ) -> Dict[str, object]:
        """Send the request using the official OpenAI SDK."""

        if OpenAI is None and self._openai_client_factory is self._default_openai_client_factory:  # pragma: no cover - depende del entorno
            raise CardAIServiceError(
                "La librería 'openai' no está instalada en el entorno actual."
            )
        if not configuration.apiKey:
            raise CardAIServiceError("No se encontró la API key para el proveedor OpenAI.")

        client = self._openai_client_factory(
            configuration.apiKey,
            configuration.baseUrl,
            configuration.orgId,
            max(configuration.timeoutSeconds, 1),
        )

        try:
            response = client.chat.completions.create(  # type: ignore[attr-defined]
                model=configuration.modelName,
                messages=messages,
                temperature=configuration.temperature,
                top_p=configuration.topP,
                max_tokens=configuration.maxTokens,
            )
        except Exception as exc:  # pragma: no cover - depende del SDK remoto
            raise CardAIServiceError(f"No fue posible contactar a OpenAI: {exc}") from exc

        return self._normalize_openai_response(response)

    def _normalize_openai_response(self, response: object) -> Dict[str, object]:
        """Convert OpenAI SDK responses into plain dictionaries."""

        if isinstance(response, dict):
            return response

        for attribute in ("model_dump", "to_dict", "dict"):
            candidate = getattr(response, attribute, None)
            if candidate is None:
                continue
            try:
                data = candidate()
            except TypeError:
                data = candidate(exclude_none=False)
            if isinstance(data, dict):
                return data

        raise CardAIServiceError("La respuesta de OpenAI no se puede serializar como diccionario.")

    def _default_openai_client_factory(
        self,
        api_key: str,
        base_url: Optional[str],
        org_id: Optional[str],
        timeout_seconds: int,
    ) -> object:
        """Instantiate the OpenAI client handling optional parameters."""

        if OpenAI is None:  # pragma: no cover - depende del entorno
            raise CardAIServiceError(
                "La librería 'openai' no está instalada en el entorno actual."
            )

        client = OpenAI(api_key=api_key, organization=org_id, base_url=base_url)
        try:
            if timeout_seconds and hasattr(client, "with_options"):
                return client.with_options(timeout=timeout_seconds)
        except Exception:  # pragma: no cover - depende del SDK
            pass
        return client

    def _normalize_json_content(self, raw_content: str) -> str:
        """Remove markdown code fences from the JSON block returned by the LLM.

        Args:
            raw_content: Texto crudo devuelto dentro del mensaje del asistente.

        Returns:
            Cadena lista para ser interpretada como JSON.
        """

        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
            cleaned = cleaned.lstrip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.lstrip("\n\r ")
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        return cleaned.strip()

    def _serialize_for_log(self, data: object) -> str:
        """Serialize arbitrary data to JSON for audit storage."""

        return json.dumps(data, ensure_ascii=False, default=str)

    def _log_ai_interaction(
        self,
        card_id: int,
        input_id: Optional[int],
        configuration: ResolvedAIConfigurationDTO,
        request_payload: str,
        response_payload: Optional[str],
        response_content: Optional[str],
        is_valid_json: bool,
        error_message: Optional[str],
    ) -> None:
        """Persist an audit entry capturing the LLM request and response."""

        try:
            self._request_log_dao.create_log(
                card_id=card_id,
                input_id=input_id,
                provider_key=configuration.providerKey,
                model_name=configuration.modelName,
                request_payload=request_payload,
                response_payload=response_payload,
                response_content=response_content,
                is_valid_json=is_valid_json,
                error_message=error_message,
            )
        except AIRequestLogDAOError as exc:  # pragma: no cover - depende de SQL Server
            logger.warning("No fue posible registrar la petición de IA: %s", exc)

    def regenerate_from_input(self, input_id: int) -> CardAIGenerationResultDTO:
        """Trigger a new generation using the stored input fields."""

        try:
            input_dto = self._input_dao.get_input(input_id)
        except CardAIInputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        if not input_dto:
            raise CardAIServiceError("La captura solicitada no existe.")

        payload = CardAIRequestDTO(
            cardId=input_dto.cardId,
            tipo=input_dto.tipo,
            descripcion=input_dto.descripcion,
            analisis=input_dto.analisis,
            recomendaciones=input_dto.recomendaciones,
            cosasPrevenir=input_dto.cosasPrevenir,
            infoAdicional=input_dto.infoAdicional,
            forceSaveInputs=True,
        )
        return self.generate_document(payload)

    def _load_system_prompt_from_file(self) -> str:
        """Read the corporate system prompt from the configured file path."""

        prompt_path = Path(self._config.get_system_prompt_path()).expanduser()
        if not prompt_path.is_absolute():
            prompt_path = Path.cwd() / prompt_path

        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise CardAIServiceError(
                f"No fue posible leer el prompt de sistema en '{prompt_path}'."
            ) from exc
        except OSError as exc:
            raise CardAIServiceError(
                f"Ocurrió un error al leer el prompt de sistema en '{prompt_path}'."
            ) from exc

        if not content:
            raise CardAIServiceError(
                f"El archivo de prompt de sistema '{prompt_path}' está vacío."
            )

        return content

