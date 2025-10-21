"""Data Transfer Objects used across the desktop recorder application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class HistoryEntry:
    """Represent a single history value persisted in the database."""

    entryId: Optional[int]
    category: str
    value: str
    createdAt: Optional[datetime]
