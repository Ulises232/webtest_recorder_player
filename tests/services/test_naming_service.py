"""Tests for the naming helpers."""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.services.naming_service import NamingService


def test_slugify_preserves_alphanumeric_and_uppercase() -> None:
    """Ensure the slug retains uppercase characters and digits."""

    service = NamingService()
    assert service.slugify_for_windows("TICKET-123 ABC") == "TICKET-123_ABC"


def test_slugify_removes_windows_invalid_characters() -> None:
    """Strip characters that Windows does not allow in file names."""

    service = NamingService()
    assert service.slugify_for_windows('Reporte:*?"<>|') == "Reporte"


def test_slugify_wraps_reserved_device_names() -> None:
    """Wrap reserved DOS device names with underscores to keep them valid."""

    service = NamingService()
    assert service.slugify_for_windows("con") == "_con_"
