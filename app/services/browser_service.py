"""Utilities for delegating browser interactions from the controllers."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class BrowserService:
    """Handle browser resolution and process launching details."""

    def __init__(self, default_profile: str = "Default") -> None:
        """Configure the service with the default Chrome profile name."""
        self.default_profile = default_profile

    def find_chrome_executable(self) -> Optional[str]:
        """Locate the Chrome executable on the host system."""
        candidates = [
            Path(r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"),
            Path(r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"),
        ]
        which = shutil.which("chrome")
        if which:
            candidates.append(Path(which))
        for candidate in candidates:
            if candidate and candidate.exists():
                return str(candidate)
        return None

    def open_with_profile(self, url: str, profile_dir: Optional[str] = None) -> Tuple[bool, str]:
        """Launch Chrome with the requested profile pointing to the provided URL."""
        profile = profile_dir or self.default_profile
        executable = self.find_chrome_executable()
        if not executable:
            return False, "No se encontró chrome.exe"
        args = [executable, f"--profile-directory={profile}", url]
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, ""
        except Exception as exc:
            return False, str(exc)
