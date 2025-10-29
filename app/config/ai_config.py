"""Configuration helper for the local language model endpoint."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, MutableMapping, Optional


@dataclass
class AIConfiguration:
    """Resolve connection parameters for the AI generation endpoint."""

    DEFAULT_URL: str = "http://127.0.0.1:1234/v1/chat/completions"
    DEFAULT_MODEL: str = "qwen/qwen2.5-vl-7b"
    DEFAULT_TEMPERATURE: float = 0.35
    DEFAULT_TOP_P: float = 0.9
    DEFAULT_MAX_TOKENS: int = 3000

    def __init__(self, environ: Optional[Mapping[str, str]] = None) -> None:
        """Persist the environment mapping used to read configuration values."""

        self._environ: MutableMapping[str, str] = (
            dict(environ) if environ is not None else dict(os.environ)
        )

    def get_api_url(self) -> str:
        """Return the base URL for the chat completions endpoint."""

        return self._environ.get("LM_URL", self.DEFAULT_URL).strip() or self.DEFAULT_URL

    def get_model_name(self) -> str:
        """Return the model identifier provided to the LLM endpoint."""

        return self._environ.get("LM_MODEL", self.DEFAULT_MODEL).strip() or self.DEFAULT_MODEL

    def get_api_key(self) -> Optional[str]:
        """Expose the optional API key forwarded as bearer token."""

        token = self._environ.get("LM_API_KEY", "").strip()
        return token or None

    def get_temperature(self) -> float:
        """Return the sampling temperature configured for generations."""

        raw = self._environ.get("LM_TEMPERATURE")
        if raw is None:
            return self.DEFAULT_TEMPERATURE
        try:
            return float(raw)
        except ValueError:
            return self.DEFAULT_TEMPERATURE

    def get_top_p(self) -> float:
        """Return the nucleus sampling value used when contacting the LLM."""

        raw = self._environ.get("LM_TOP_P")
        if raw is None:
            return self.DEFAULT_TOP_P
        try:
            return float(raw)
        except ValueError:
            return self.DEFAULT_TOP_P

    def get_max_tokens(self) -> int:
        """Return the maximum amount of tokens allowed per completion."""

        raw = self._environ.get("LM_MAX_TOKENS")
        if raw is None:
            return self.DEFAULT_MAX_TOKENS
        try:
            return int(raw)
        except ValueError:
            return self.DEFAULT_MAX_TOKENS

