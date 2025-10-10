"""Helpers to generate filesystem friendly names."""

import re


class NamingService:
    """Apply transformations to keep filenames compatible with Windows."""

    def slugify_for_windows(self, name: str) -> str:
        """Return a sanitized slug valid for Windows file systems."""
        clean_name = (name or "").strip()
        clean_name = re.sub(r'[<>:"/\\|?*\\x00-\\x1F]', "", clean_name)
        clean_name = re.sub(r"\\s+", "_", clean_name)
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
        if clean_name.upper() in reserved:
            clean_name = f"_{clean_name}_"
        return clean_name.rstrip(". ")[:80]
