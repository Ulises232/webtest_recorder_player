"""Helper for generating DDE documents using the official OpenAI client."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

try:  # pragma: no cover - habilita ejecutar herramientas sin la dependencia instalada
    from openai import APIConnectionError, APIError, APITimeoutError, BadRequestError, OpenAI, RateLimitError
except ModuleNotFoundError:  # pragma: no cover
    class APIConnectionError(RuntimeError):
        """Fallback error used when the OpenAI SDK is missing."""

    class APITimeoutError(RuntimeError):
        """Fallback error used when the OpenAI SDK is missing."""

    class APIError(RuntimeError):
        """Fallback error used when the OpenAI SDK is missing."""

    class BadRequestError(RuntimeError):
        """Fallback error used when the OpenAI SDK is missing."""

    class RateLimitError(RuntimeError):
        """Fallback error used when the OpenAI SDK is missing."""

    class OpenAI:  # type: ignore[override]
        """Minimal stand-in that raises informative errors when used."""

        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError(
                "La dependencia 'openai' no está instalada. Añádela al entorno antes de llamar a generar_dde."
            )

from app.config.ai_config import AIConfiguration


LOGGER = logging.getLogger(__name__)


def _load_system_prompt(config: AIConfiguration) -> str:
    """Read the corporate YAML prompt content defined for DDE generation."""

    prompt_path = Path(config.get_system_prompt_path()).expanduser()
    if not prompt_path.is_absolute():
        prompt_path = Path.cwd() / prompt_path

    try:
        content = prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"No se encontró el archivo de prompt de sistema en '{prompt_path}'."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Ocurrió un error al leer el prompt de sistema en '{prompt_path}'."
        ) from exc

    if not content:
        raise RuntimeError(
            f"El archivo de prompt de sistema '{prompt_path}' está vacío y no puede utilizarse."
        )
    return content


def _ensure_openai_client(config: AIConfiguration) -> OpenAI:
    """Instantiate an OpenAI client using the configured API key."""

    api_key = config.get_api_key()
    if not api_key:
        raise RuntimeError(
            "No se encontró la variable de entorno OPENAI_API_KEY requerida para generar DDE."
        )
    return OpenAI(api_key=api_key)


def _render_user_prompt(datos: Dict[str, object]) -> str:
    """Format the provided DDE fields as a user prompt for the model."""

    lines = ["Genera un documento DDE en JSON estricto siguiendo el formato corporativo."]
    lines.append("Datos proporcionados para el caso actual:")
    for clave, valor in datos.items():
        if valor is None:
            continue
        texto = str(valor).strip()
        if not texto:
            continue
        lines.append(f"- {clave}: {texto}")
    return "\n".join(lines)


def generar_dde(datos: Dict[str, object], modo_prueba: bool = False) -> str:
    """Generar un documento DDE utilizando los modelos GPT-4o de OpenAI."""

    config = AIConfiguration()
    system_prompt = _load_system_prompt(config)
    client = _ensure_openai_client(config)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _render_user_prompt(datos)},
    ]

    payload = {
        "model": "gpt-4o-mini" if modo_prueba else "gpt-4-turbo",
        "messages": messages,
        "temperature": config.get_temperature(),
        "top_p": config.get_top_p(),
        "max_tokens": config.get_max_tokens(),
    }

    try:
        completion = client.chat.completions.create(timeout=180, **payload)
    except (APITimeoutError, APIConnectionError) as exc:  # pragma: no cover - errores de red
        LOGGER.warning("No fue posible contactar al endpoint de OpenAI: %s", exc)
        raise RuntimeError("No fue posible contactar al endpoint de OpenAI.") from exc
    except RateLimitError as exc:  # pragma: no cover - depende del límite del entorno
        LOGGER.warning("Se alcanzó el límite de peticiones permitido por OpenAI: %s", exc)
        raise RuntimeError("OpenAI alcanzó el límite de peticiones permitido.") from exc
    except BadRequestError as exc:  # pragma: no cover - entrada inválida
        LOGGER.warning("OpenAI rechazó la solicitud enviada: %s", exc)
        raise RuntimeError("La solicitud enviada a OpenAI es inválida.") from exc
    except APIError as exc:  # pragma: no cover - errores genéricos de la API
        LOGGER.warning("OpenAI devolvió un error inesperado: %s", exc)
        raise RuntimeError("OpenAI devolvió un error inesperado.") from exc

    try:
        contenido = completion.choices[0].message.content or ""
    except (IndexError, AttributeError) as exc:  # pragma: no cover - defensivo
        LOGGER.warning("La respuesta de OpenAI no contiene contenido utilizable: %s", exc)
        raise RuntimeError("La respuesta de OpenAI no contiene contenido utilizable.") from exc

    contenido = contenido.strip()
    try:
        json.loads(contenido)
    except json.JSONDecodeError as exc:
        LOGGER.warning("La respuesta del modelo no es JSON válido: %s", exc)
        raise RuntimeError("La respuesta del modelo no es JSON válido.") from exc

    return contenido


if __name__ == "__main__":  # pragma: no cover - ejemplo manual
    ejemplo = {
        "titulo": "EA-172 Ajuste de vencimientos",
        "descripcion": "El módulo de cartera no genera los vencimientos al actualizar fechas.",
        "analisis": "Se detectó que la rutina de cálculo ignora los contratos con pagos parciales.",
        "recomendaciones": "Agregar validaciones sobre los contratos con pagos vencidos.",
    }
    try:
        resultado = generar_dde(ejemplo, modo_prueba=True)
        print(resultado)
    except RuntimeError as error:
        print(f"Error al generar el DDE: {error}")
