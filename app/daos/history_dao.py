"""Data access layer for reading and writing history information."""

from pathlib import Path
from typing import List
import json

from app.dtos.history_entry import HistoryEntry


class FileHistoryDAO:
    """Provide CRUD-like helpers for list-based history files."""

    def __init__(self, file_path: Path, capacity: int = 15) -> None:
        """Store the location of the history file and its max capacity."""
        self.file_path = file_path
        self.capacity = capacity

    def load(self, default_value: str) -> List[HistoryEntry]:
        """Load the history from disk returning DTO instances."""
        if not self.file_path.exists():
            return [HistoryEntry(default_value)]
        try:
            raw_data = json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return [HistoryEntry(default_value)]
        if not isinstance(raw_data, list) or not raw_data:
            return [HistoryEntry(default_value)]
        return [HistoryEntry(str(item)) for item in raw_data]

    def save(self, value: str) -> None:
        """Insert a new value on top of the history file."""
        clean_value = value.strip()
        if not clean_value:
            return
        history = [entry.value for entry in self.load(clean_value)]
        if any(item.lower() == clean_value.lower() for item in history):
            return
        updated = [clean_value] + [item for item in history if item.lower() != clean_value.lower()]
        updated = updated[: self.capacity]
        try:
            self.file_path.write_text(
                json.dumps(updated, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return
