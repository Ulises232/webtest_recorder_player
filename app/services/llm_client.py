"""HTTP client to interact with the local LM Studio endpoint."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Mapping, Optional

try:  # pragma: no cover - dependencia opcional en pruebas
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - entornos sin requests
    requests = None  # type: ignore

from app.dtos.card_ai_dto import LLMGenerationResponse


class LLMClientError(RuntimeError):
    """Raised when the LLM endpoint cannot process a request."""


class LocalLLMClient:
    """Small wrapper around the OpenAI-compatible LM Studio endpoint."""

    DEFAULT_URL = "http://127.0.0.1:1234/v1/chat/completions"
    DEFAULT_MODEL = "qwen/qwen2.5-vl-7b"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: int = 180,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Store configuration for subsequent invocations."""

        self._endpoint = (endpoint or os.getenv("LM_URL") or self.DEFAULT_URL).strip()
        self._model = (model or os.getenv("LM_MODEL") or self.DEFAULT_MODEL).strip()
        self._api_key = (api_key or os.getenv("LM_API_KEY") or "local").strip()
        self._timeout = timeout_seconds
        if session is not None:
            self._session = session
        elif requests is not None:
            self._session = requests.Session()
        else:  # pragma: no cover - depende del entorno de ejecución
            self._session = None

    def generateJson(self, prompt: str) -> LLMGenerationResponse:
        """Request a JSON-formatted completion from the language model."""

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.35,
            "top_p": 0.9,
            "max_tokens": 3000,
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        if self._session is None:  # pragma: no cover - depende del entorno
            raise LLMClientError(
                "La dependencia 'requests' no está instalada. Ejecuta 'pip install requests' para habilitar el cliente LLM."
            )

        try:
            response = self._session.post(
                self._endpoint,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=self._timeout,
            )
        except Exception as exc:  # pragma: no cover - depende del driver HTTP
            raise LLMClientError("No fue posible contactar al servicio de lenguaje natural.") from exc

        if not response.ok:
            raise LLMClientError(
                f"El servicio de lenguaje natural respondió con código {response.status_code}."
            )

        try:
            data: Mapping[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            raise LLMClientError("La respuesta del modelo no es un JSON válido.") from exc

        try:
            choices = data["choices"]
            first = choices[0]
            message = first["message"]
            content_raw = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("La respuesta del modelo no contiene el contenido esperado.") from exc

        if isinstance(content_raw, (str, bytes)):
            content_text = content_raw.decode("utf-8") if isinstance(content_raw, bytes) else content_raw
            try:
                content = json.loads(content_text)
            except json.JSONDecodeError as exc:
                raise LLMClientError("El modelo no devolvió un JSON válido en el contenido.") from exc
        elif isinstance(content_raw, Mapping):
            content = dict(content_raw)
        else:
            raise LLMClientError("El contenido devuelto por el modelo tiene un formato desconocido.")

        usage = {}
        if isinstance(data.get("usage"), Mapping):
            usage = dict(data["usage"])

        return LLMGenerationResponse(
            llmId=str(data.get("id")) if data.get("id") else None,
            model=str(data.get("model")) if data.get("model") else self._model,
            usage=usage,
            content=content,
        )


__all__ = ["LocalLLMClient", "LLMClientError"]
