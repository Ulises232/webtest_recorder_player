"""Unified client to generate DDE documents through multiple LLM providers."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

try:  # pragma: no cover - compatibility with multiple OpenAI SDK versions
    from openai import APIStatusError, OpenAI, OpenAIError, RateLimitError
except ImportError:  # pragma: no cover - fallback for legacy SDKs
    from openai import OpenAI  # type: ignore

    APIStatusError = None  # type: ignore[assignment]
    RateLimitError = None  # type: ignore[assignment]

    class OpenAIError(Exception):  # type: ignore[override]
        """Generic OpenAI SDK error wrapper when specific classes are missing."""

        pass


logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "app" / "prompts" / "system_prompt.yaml"
)
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_TOKENS = 2500
DEFAULT_TEMPERATURE = 0.2
MAX_RETRIES = 3
BACKOFF_FACTOR = 2
_CORRECTION_PROMPT = (
    "Corrige la respuesta anterior para que sea JSON válido. Devuelve únicamente el JSON sin formato Markdown."
)


class DDEClientError(RuntimeError):
    """Raised when the DDE client cannot obtain a valid JSON response."""


@dataclass(frozen=True)
class LLMConfiguration:
    """Store configuration parameters shared across providers."""

    timeout: float
    max_tokens: int
    temperature: float
    system_prompt: str


class DDEClient:
    """Expose a single entry-point to request DDE documents from multiple LLM providers."""

    def __init__(self, system_prompt_path: Optional[Path] = None) -> None:
        """Load configuration from environment variables and cache the system prompt."""

        self._config = self._build_configuration(system_prompt_path)
        self._openai_client: Optional[OpenAI] = None
        self._provider_map: Dict[str, Callable[[List[Dict[str, str]]], str]] = {
            "openai_turbo": self._call_openai_turbo,
            "openai_mini": self._call_openai_mini,
            "mistral": self._call_mistral,
            "local": self._call_local,
        }

    def generar_dde(self, datos: Dict[str, Any], provider: str = "openai_turbo") -> str:
        """Generate a DDE JSON document using the specified provider."""

        provider_key = provider.lower()
        if provider_key not in self._provider_map:
            raise DDEClientError(f"Proveedor no soportado: {provider}")

        messages = self._build_messages(datos)
        raw_content = self._provider_map[provider_key](messages)
        return self._ensure_json_response(raw_content, messages, provider_key)

    def _build_configuration(self, system_prompt_path: Optional[Path]) -> LLMConfiguration:
        """Return the configuration object populated from environment variables."""

        timeout = self._read_float_env("LLM_TIMEOUT", DEFAULT_TIMEOUT)
        max_tokens = self._read_int_env("LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS)
        temperature = self._read_float_env("LLM_TEMPERATURE", DEFAULT_TEMPERATURE)
        system_prompt = self._load_system_prompt(system_prompt_path)
        return LLMConfiguration(timeout=timeout, max_tokens=max_tokens, temperature=temperature, system_prompt=system_prompt)

    def _read_int_env(self, name: str, default: int) -> int:
        """Return an integer value from environment variables with fallback."""

        value = os.getenv(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning("Valor inválido para %s=%s. Se utilizará el valor por defecto %s.", name, value, default)
            return default

    def _read_float_env(self, name: str, default: float) -> float:
        """Return a float value from environment variables with fallback."""

        value = os.getenv(name)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            logger.warning("Valor inválido para %s=%s. Se utilizará el valor por defecto %s.", name, value, default)
            return default

    def _load_system_prompt(self, system_prompt_path: Optional[Path]) -> str:
        """Load the shared system prompt text used across providers."""

        path = system_prompt_path or DEFAULT_SYSTEM_PROMPT_PATH
        if not path.exists():
            raise DDEClientError(f"No se encontró el archivo de system prompt en {path}.")
        try:
            content = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise DDEClientError(f"No fue posible leer el system prompt en '{path}'.") from exc
        except OSError as exc:
            raise DDEClientError(f"Error al abrir el archivo de system prompt '{path}'.") from exc
        if not content:
            raise DDEClientError(f"El archivo de system prompt '{path}' está vacío.")
        return content

    def _build_messages(self, datos: Dict[str, Any]) -> List[Dict[str, str]]:
        """Construct the chat messages payload shared by all providers."""

        user_content = json.dumps(datos, ensure_ascii=False, indent=2)
        return [
            {"role": "system", "content": self._config.system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _ensure_json_response(
        self,
        content: str,
        base_messages: List[Dict[str, str]],
        provider_key: str,
        allow_retry: bool = True,
    ) -> str:
        """Validate and optionally request a correction when the JSON is invalid."""

        cleaned = self._clean_json_text(content)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            if not allow_retry:
                raise DDEClientError("El modelo no devolvió JSON válido tras la corrección.")
            logger.warning("Respuesta JSON inválida recibida de %s. Solicitando corrección.", provider_key)
            correction_messages = base_messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": _CORRECTION_PROMPT},
            ]
            corrected = self._provider_map[provider_key](correction_messages)
            return self._ensure_json_response(corrected, base_messages, provider_key, allow_retry=False)
        return json.dumps(parsed, ensure_ascii=False, indent=2)

    def _clean_json_text(self, content: str) -> str:
        """Remove markdown fences and trim whitespace from a JSON-like response."""

        cleaned = content.strip().replace("\uFEFF", "")
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        return cleaned.strip()

    def _call_openai_turbo(self, messages: List[Dict[str, str]]) -> str:
        """Invoke OpenAI using the gpt-4-turbo model."""

        return self._call_openai_model("gpt-4-turbo", messages)

    def _call_openai_mini(self, messages: List[Dict[str, str]]) -> str:
        """Invoke OpenAI using the gpt-4o-mini model."""

        return self._call_openai_model("gpt-4o-mini", messages)

    def _call_openai_model(self, model: str, messages: List[Dict[str, str]]) -> str:
        """Execute an OpenAI chat completion with retries on recoverable errors."""

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise DDEClientError("Falta la variable de entorno OPENAI_API_KEY.")
        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=api_key)

        def operation() -> str:
            response = self._openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
            return self._extract_message_content(response, provider="openai")

        return self._execute_with_retry(operation, provider="openai")

    def _call_mistral(self, messages: List[Dict[str, str]]) -> str:
        """Call Mistral's chat completion endpoint using HTTP requests."""

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise DDEClientError("Falta la variable de entorno MISTRAL_API_KEY.")
        url = "https://api.mistral.ai/v1/chat/completions"
        payload = {
            "model": "mistral-large-latest",
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        return self._post_with_retry(url, payload, headers, provider="mistral")

    def _call_local(self, messages: List[Dict[str, str]]) -> str:
        """Call a local OpenAI-compatible endpoint exposed by LM Studio or similar host."""

        base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:1234/v1")
        model = os.getenv("LOCAL_LLM_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        return self._post_with_retry(url, payload, headers, provider="local")

    def _execute_with_retry(self, operation: Callable[[], str], provider: str) -> str:
        """Execute an operation applying exponential backoff for transient errors."""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return operation()
            except Exception as exc:  # pragma: no cover - relies on external SDK behavior
                if not self._is_retryable_exception(exc):
                    logger.warning("Error definitivo en proveedor %s: %s", provider, exc)
                    raise DDEClientError(str(exc)) from exc
                if attempt == MAX_RETRIES:
                    logger.warning("Se agotaron los reintentos con %s: %s", provider, exc)
                    raise DDEClientError("El proveedor no respondió exitosamente tras múltiples intentos.") from exc
                sleep_time = self._backoff_seconds(attempt)
                logger.warning(
                    "Error transitorio con %s (intento %s/%s): %s. Reintentando en %.1fs.",
                    provider,
                    attempt,
                    MAX_RETRIES,
                    exc,
                    sleep_time,
                )
                time.sleep(sleep_time)
        raise DDEClientError("No se pudo completar la operación solicitada.")

    def _is_retryable_exception(self, exc: Exception) -> bool:
        """Determine whether the received exception is retryable."""

        if APIStatusError is not None and isinstance(exc, APIStatusError):  # type: ignore[arg-type]
            return getattr(exc, "status_code", 0) in {429, 500, 502, 503, 504}
        if RateLimitError is not None and isinstance(exc, RateLimitError):  # type: ignore[arg-type]
            return True
        if isinstance(exc, OpenAIError):
            status = getattr(exc, "status_code", None)
            return status in {429, 500, 502, 503, 504}
        if isinstance(exc, requests.HTTPError):
            status = exc.response.status_code if exc.response else None
            return status in {429, 500, 502, 503, 504}
        if isinstance(exc, requests.RequestException):
            return True
        return False

    def _backoff_seconds(self, attempt: int) -> float:
        """Return the waiting time before the next retry using exponential backoff."""

        return BACKOFF_FACTOR ** (attempt - 1)

    def _post_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        provider: str,
    ) -> str:
        """Send an HTTP POST applying retries for 429/5xx responses."""

        def operation() -> str:
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._config.timeout,
                )
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise exc
            except requests.RequestException as exc:
                raise exc
            try:
                data = response.json()
            except ValueError as exc:
                logger.warning("El proveedor %s devolvió una respuesta no JSON: %s", provider, exc)
                raise DDEClientError("El proveedor devolvió un payload inválido.") from exc
            return self._extract_message_content(data, provider=provider)

        return self._execute_with_retry(operation, provider=provider)

    def _extract_message_content(self, response: Any, provider: str) -> str:
        """Extract the assistant message content from provider responses."""

        if hasattr(response, "choices"):
            choices = getattr(response, "choices")
        else:
            choices = response.get("choices") if isinstance(response, dict) else None
        if not choices:
            raise DDEClientError(f"El proveedor {provider} no devolvió 'choices'.")
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is None and isinstance(first_choice, dict):
            message = first_choice.get("message")
        if not message:
            raise DDEClientError(f"El proveedor {provider} no devolvió el mensaje de la respuesta.")
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        if not content:
            raise DDEClientError(f"El proveedor {provider} no devolvió contenido en la respuesta.")
        if isinstance(content, list):
            content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        return str(content)


if __name__ == "__main__":
    """Provide a simple manual usage example when the module is executed directly."""

    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependencia opcional
        load_dotenv = None

    if load_dotenv:
        load_dotenv()

    example_datos: Dict[str, Any] = {
        "tipo": "DDE",
        "titulo": "Ajustes en validaciones CFDI pagos",
        "fecha": "2025-11-03",
        "hora_inicio": "15:00",
        "hora_fin": "16:30",
        "lugar": "Sistemas Premium",
        "que_necesitas": "Mejorar validación de reglas fiscales CFDI 4.0.",
        "para_que": "Reducir errores de timbrado y rechazos PAC.",
        "como": "Validar totales antes de enviar a timbrar.",
        "requerimientos_funcionales": [
            "Validar RFC emisor/receptor",
            "Comparar totales CFDI vs BD",
        ],
        "requerimientos_especiales": ["Compatibilidad SmartWeb/PAX"],
        "criterios_aceptacion": [
            "Errores < 1%",
            "CFDI válidos en primera emisión",
        ],
        "anexos": ["Flujo BPMN CFDI pagos"],
    }

    client = DDEClient()
    for provider in ("openai_turbo", "openai_mini", "mistral", "local"):
        print(f"=== {provider.upper()} ===")
        try:
            print(client.generar_dde(example_datos, provider=provider))
        except DDEClientError as error:
            print(f"Error con {provider}: {error}")
