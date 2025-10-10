"""Data Transfer Objects used across the desktop recorder application."""

from dataclasses import dataclass


@dataclass
class HistoryEntry:
    """Represent a single string value stored in a history file."""

    value: str
