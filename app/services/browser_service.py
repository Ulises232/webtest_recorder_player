"""Utilities for interacting with the local Chrome installation."""

from pathlib import Path
from typing import Optional, Tuple
import shutil
import subprocess


class BrowserService:
    """Handle launching Chrome with predefined profiles."""

    def find_chrome(self) -> Optional[Path]:
        """Locate the Chrome executable in the current system."""
        candidates = [
            Path(r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
            Path(r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"),
            Path(shutil.which("chrome") or ""),
        ]
        for candidate in candidates:
            if candidate and candidate.exists():
                return candidate
        return None

    def open_with_profile(self, url: str, profile_dir: str = "Default") -> Tuple[bool, str]:
        """Start Chrome with a specific profile returning success information."""
        executable = self.find_chrome()
        if not executable:
            return False, "No se encontró chrome.exe"
        args = [str(executable), f"--profile-directory={profile_dir}", url]
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as error:  # pragma: no cover - relies on OS interaction
            return False, str(error)
        return True, ""
