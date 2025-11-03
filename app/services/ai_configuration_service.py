"""Service that consolidates AI provider configuration data."""

from __future__ import annotations

import base64
import os
from typing import Dict, List, Optional

from app.config.ai_config import AIConfiguration
from app.daos.ai_provider_dao import AIProviderDAO, AIProviderDAOError
from app.daos.ai_settings_dao import AISettingsDAO, AISettingsDAOError
from app.dtos.ai_settings_dto import (
    AIProviderRuntimeDTO,
    AIProviderRecordDTO,
    AISettingsRecordDTO,
    ResolvedAIConfigurationDTO,
)


class AIConfigurationServiceError(RuntimeError):
    """Raised when the AI configuration cannot be resolved."""


class AIConfigurationService:
    """Expose helpers to retrieve providers and resolve runtime settings."""

    LOCAL_KEY = "local"
    OPENAI_KEYS = {"openai_mini", "openai_turbo"}
    MISTRAL_KEY = "mistral"

    def __init__(
        self,
        settings_dao: AISettingsDAO,
        provider_dao: AIProviderDAO,
        configuration: Optional[AIConfiguration] = None,
        secret_key: Optional[str] = None,
    ) -> None:
        """Persist dependencies required to resolve configuration data."""

        self._settings_dao = settings_dao
        self._provider_dao = provider_dao
        self._configuration = configuration or AIConfiguration()
        self._secret_key = secret_key or os.getenv("AI_SECRET_KEY", "")

    def list_providers(self) -> List[AIProviderRuntimeDTO]:
        """Return all configured providers with decrypted credentials."""

        records = self._get_provider_records()
        providers: List[AIProviderRuntimeDTO] = []
        for record in records:
            providers.append(self._record_to_runtime(record))
        providers.sort(key=lambda item: (not item.favorite, item.displayName.lower()))
        return providers

    def get_default_provider_key(self) -> str:
        """Return the provider key that should be preselected by default."""

        providers = self.list_providers()
        favorite = next((item for item in providers if item.favorite), None)
        if favorite:
            return favorite.providerKey

        settings = self._get_settings()
        fallback = next(
            (item for item in providers if item.providerKey == settings.activeProvider),
            None,
        )
        if fallback:
            return fallback.providerKey

        if providers:
            return providers[0].providerKey

        return self.LOCAL_KEY

    def resolve_configuration(
        self, selected_provider: Optional[str] = None
    ) -> ResolvedAIConfigurationDTO:
        """Combine provider data with global settings for runtime usage."""

        providers = self.list_providers()
        settings = self._get_settings()

        provider = self._select_provider(providers, settings, selected_provider)
        base_url = provider.baseUrl
        if not base_url and provider.providerKey == self.LOCAL_KEY:
            base_url = self._configuration.get_api_url()
        if not base_url and provider.providerKey == self.MISTRAL_KEY:
            base_url = "https://api.mistral.ai/v1"

        temperature = settings.temperature or self._configuration.get_temperature()
        max_tokens = settings.maxTokens or self._configuration.get_max_tokens()
        timeout_seconds = settings.timeoutSeconds or 180
        top_p = self._configuration.get_top_p()

        return ResolvedAIConfigurationDTO(
            providerKey=provider.providerKey,
            displayName=provider.displayName,
            baseUrl=base_url,
            apiKey=provider.apiKey,
            orgId=provider.orgId,
            modelName=provider.modelName or self._configuration.get_model_name(),
            temperature=temperature,
            topP=top_p,
            maxTokens=max_tokens,
            timeoutSeconds=timeout_seconds,
            useRagLocal=settings.useRagLocal,
            extra=provider.extra,
        )

    def _select_provider(
        self,
        providers: List[AIProviderRuntimeDTO],
        settings: AISettingsRecordDTO,
        selected_provider: Optional[str],
    ) -> AIProviderRuntimeDTO:
        """Choose the runtime provider considering the different fallbacks."""

        provider_map: Dict[str, AIProviderRuntimeDTO] = {
            provider.providerKey: provider for provider in providers
        }

        if selected_provider and selected_provider in provider_map:
            return provider_map[selected_provider]

        favorite = next((item for item in providers if item.favorite), None)
        if favorite:
            return favorite

        if settings.activeProvider in provider_map:
            return provider_map[settings.activeProvider]

        if providers:
            return providers[0]

        return AIProviderRuntimeDTO(
            providerKey=self.LOCAL_KEY,
            displayName="Local",
            baseUrl=self._configuration.get_api_url(),
            apiKey=self._configuration.get_api_key(),
            orgId=None,
            modelName=self._configuration.get_model_name(),
            extra={},
            favorite=True,
        )

    def _get_provider_records(self) -> List[AIProviderRecordDTO]:
        """Retrieve provider rows from the DAO and wrap errors consistently."""

        try:
            return self._provider_dao.list_providers()
        except AIProviderDAOError as exc:  # pragma: no cover - dependencias externas
            raise AIConfigurationServiceError(str(exc)) from exc

    def _get_settings(self) -> AISettingsRecordDTO:
        """Retrieve global AI settings handling DAO errors uniformly."""

        try:
            return self._settings_dao.get_settings()
        except AISettingsDAOError as exc:  # pragma: no cover - dependencias externas
            raise AIConfigurationServiceError(str(exc)) from exc

    def _record_to_runtime(self, record: AIProviderRecordDTO) -> AIProviderRuntimeDTO:
        """Decrypt a provider record and normalize display metadata."""

        decrypted_key = self._decrypt_api_key(record.apiKeyEncrypted)
        display_name = str(record.extra.get("label") or record.providerKey)
        base_url = record.baseUrl
        if not base_url and record.providerKey == self.LOCAL_KEY:
            base_url = self._configuration.get_api_url()
        if not base_url and record.providerKey == self.MISTRAL_KEY:
            base_url = "https://api.mistral.ai/v1"

        return AIProviderRuntimeDTO(
            providerKey=record.providerKey,
            displayName=display_name,
            baseUrl=base_url,
            apiKey=decrypted_key,
            orgId=record.orgId,
            modelName=record.modelName or self._configuration.get_model_name(),
            extra=record.extra,
            favorite=record.favorite,
        )

    def _decrypt_api_key(self, encrypted: Optional[str]) -> Optional[str]:
        """Attempt to decode the stored API key using a best-effort strategy."""

        if not encrypted:
            return None

        token = encrypted.strip()
        if not token:
            return None

        try:
            decoded = base64.b64decode(token).decode("utf-8")
        except Exception:  # pragma: no cover - depende del formato almacenado
            decoded = token

        if not self._secret_key:
            return decoded

        secret_bytes = self._secret_key.encode("utf-8")
        decoded_bytes = decoded.encode("utf-8")
        xored = bytes(
            byte ^ secret_bytes[index % len(secret_bytes)]
            for index, byte in enumerate(decoded_bytes)
        )
        try:
            return xored.decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover - depende de la clave guardada
            return decoded
