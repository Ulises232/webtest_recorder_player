"""Data access layer for managing persisted history entries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List


class HistoryDAO:
    """Provide CRUD-style operations for JSON based histories."""

    def __init__(self, file_path: Path) -> None:
        """Initialize the DAO with the path of the JSON history file."""
        self.file_path = file_path

    def read(self) -> List[str]:
        """Read the persisted history entries from disk."""
        if not self.file_path.exists():
            return []
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def write(self, entries: List[str]) -> None:
        """Persist the provided history entries to disk."""
        parent = self.file_path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
