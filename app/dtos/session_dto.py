"""Data transfer objects describing recorder sessions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SessionDTO:
    """Represent the information captured during a recording session."""

    title: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    base_url: str = ""

    def add_step(self, step: Dict[str, Any]) -> None:
        """Append a new step to the session sequence."""
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the session into a structure compatible with legacy flows."""
        return {"title": self.title, "steps": self.steps, "base": self.base_url}
