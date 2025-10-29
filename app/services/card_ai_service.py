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

from app.config.ai_config import AIConfiguration
from app.daos.card_ai_input_dao import CardAIInputDAO, CardAIInputDAOError
from app.daos.card_ai_output_dao import CardAIOutputDAO, CardAIOutputDAOError
from app.daos.card_dao import CardDAO, CardDAOError
from app.dtos.card_ai_dto import (
    CardAIHistoryEntryDTO,
    CardAIInputDTO,
    CardAIRequestDTO,
    CardAIGenerationResultDTO,
    CardDTO,
    CardFiltersDTO,
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
        configuration: Optional[AIConfiguration] = None,
        http_post: Optional[Callable[..., requests.Response]] = None,
        system_prompt_loader: Optional[Callable[[], str]] = None,
        context_service: Optional["RAGContextService"] = None,
    ) -> None:
        """Store dependencies used by the service."""

        self._card_dao = card_dao
        self._input_dao = input_dao
        self._output_dao = output_dao
        self._config = configuration or AIConfiguration()
        self._http_post = http_post or requests.post
        self._system_prompt_loader: Callable[[], str] = (
            system_prompt_loader or self._load_system_prompt_from_file
        )
        self._context_service = context_service

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

    def _call_llm(self, prompt: str, context: str = "") -> Dict[str, object]:
        """Send the completion request to the configured LLM."""

        headers = {"Content-Type": "application/json"}
        token = self._config.get_api_key()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            headers["Authorization"] = "Bearer local"

        try:
            system_prompt = self._system_prompt_loader()
        except CardAIServiceError:
            raise
        except Exception as exc:  # pragma: no cover - fallback ante errores inesperados
            raise CardAIServiceError(
                "No fue posible cargar el prompt de sistema solicitado."
            ) from exc

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
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._config.get_model_name(),
            "messages": messages,
            "temperature": self._config.get_temperature(),
            "top_p": self._config.get_top_p(),
            "max_tokens": self._config.get_max_tokens(),
        }

        try:
            response = self._http_post(
                self._config.get_api_url(),
                headers=headers,
                json=payload,
                timeout=180000,
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

    def generate_document(self, payload: CardAIRequestDTO) -> CardAIGenerationResultDTO:
        """Persist the prompt, invoke the LLM and store the resulting JSON."""

        try:
            titulo = self._card_dao.get_card_title(payload.cardId)
        except CardDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

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
        if self._context_service:
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
        llm_response = self._call_llm(prompt, context_text)

        try:
            content = llm_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CardAIServiceError("La respuesta del modelo no contiene contenido utilizable.") from exc

        try:
            content_json = json.loads(content)
        except ValueError as exc:
            raise CardAIServiceError("El modelo no devolvió un JSON válido.") from exc

        if context_titles:
            content_json["usados_como_contexto"] = context_titles

        try:
            output_dto = self._output_dao.create_output(
                payload.cardId,
                input_dto.inputId,
                llm_response.get("id"),
                llm_response.get("model"),
                llm_response.get("usage"),
                content_json,
            )
        except CardAIOutputDAOError as exc:
            raise CardAIServiceError(str(exc)) from exc

        return CardAIGenerationResultDTO(input=input_dto, output=output_dto, completenessPct=completeness)

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

