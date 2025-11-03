"""Data transfer objects describing AI provider configuration records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class AIProviderRecordDTO:
    """Represent a provider row as stored in the database."""

    providerKey: str
    baseUrl: Optional[str]
    apiKeyEncrypted: Optional[str]
    orgId: Optional[str]
    modelName: Optional[str]
    extra: Dict[str, object]
    updatedAt: Optional[datetime]
    favorite: bool


@dataclass
class AISettingsRecordDTO:
    """Represent the global AI settings persisted in SQL Server."""

    activeProvider: str
    temperature: float
    maxTokens: int
    timeoutSeconds: int
    useRagLocal: bool
    updatedAt: Optional[datetime]


@dataclass
class AIProviderRuntimeDTO:
    """Expose a decrypted provider ready for runtime consumption."""

    providerKey: str
    displayName: str
    baseUrl: Optional[str]
    apiKey: Optional[str]
    orgId: Optional[str]
    modelName: str
    extra: Dict[str, object]
    favorite: bool


@dataclass
class ResolvedAIConfigurationDTO:
    """Aggregate provider and global settings for an invocation."""

    providerKey: str
    displayName: str
    baseUrl: Optional[str]
    apiKey: Optional[str]
    orgId: Optional[str]
    modelName: str
    temperature: float
    topP: float
    maxTokens: int
    timeoutSeconds: int
    useRagLocal: bool
    extra: Dict[str, object]
