"""Data transfer objects for AI request audit records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AIRequestLogDTO:
    """Represent a stored AI request/response audit entry."""

    logId: int
    cardId: Optional[int]
    inputId: Optional[int]
    providerKey: str
    modelName: Optional[str]
    requestPayload: str
    responsePayload: Optional[str]
    responseContent: Optional[str]
    isValidJson: bool
    errorMessage: Optional[str]
    createdAt: datetime
