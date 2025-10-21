"""Helpers to resolve shared storage directories for the desktop app."""

import os
from pathlib import Path


APP_FOLDER_NAME = "WebRecord"
LEGACY_APP_FOLDER_NAME = "ForgeBuild"
SESSIONS_FOLDER_NAME = "sessions"
EVIDENCE_FOLDER_NAME = "evidencia"
LOGIN_CACHE_FILENAME = "login_cache.json"


def _resolveAppDataBase() -> Path:
    """Return the root AppData directory on the current system."""

    base_path = os.environ.get("APPDATA")
    if base_path:
        return Path(base_path)
    return Path.home() / "AppData" / "Roaming"


def getAppDataRoot() -> Path:
    """Return the base directory inside AppData reserved for the app."""

    return _resolveAppDataBase() / APP_FOLDER_NAME


def getForgeBuildRoot() -> Path:
    """Return the legacy ForgeBuild directory inside AppData."""

    return _resolveAppDataBase() / LEGACY_APP_FOLDER_NAME


def getSessionsDirectory(create: bool = True) -> Path:
    """Return the folder used to store generated session documents."""

    directory = getAppDataRoot() / SESSIONS_FOLDER_NAME
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def getEvidenceDirectory(create: bool = True) -> Path:
    """Return the folder that keeps evidence assets like screenshots."""

    directory = getAppDataRoot() / EVIDENCE_FOLDER_NAME
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def getLoginCachePath(create_parent: bool = True) -> Path:
    """Return the path for the cached login credentials JSON file."""

    path = getForgeBuildRoot() / LOGIN_CACHE_FILENAME
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path
