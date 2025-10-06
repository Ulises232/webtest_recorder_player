"""Utilities for producing safe filenames across the application."""
from __future__ import annotations

import re


def slugify_for_windows(name: str) -> str:
    """Convert any string into a filesystem friendly slug."""
    clean = (name or "").strip()
    clean = re.sub(r'[<>:"/\\\\|?*\\\\x00-\\\\x1F]', "", clean)
    clean = re.sub(r"\\s+", "_", clean)
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    if clean.upper() in reserved:
        clean = f"_{clean}_"
    return clean.rstrip(". ")[:80]
