"""Centralized helpers to resolve database settings from the environment."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Union


class DatabaseConfiguration:
    """Load SQL Server connection details from environment variables and .env files.

    Args:
        env_files: Optional iterable with names or paths of files containing key-value
            pairs (``KEY=VALUE``) to merge into the environment. Relative paths are
            resolved from the repository root.
        environ: Optional mapping used instead of ``os.environ``. Intended for tests.
    """

    DEFAULT_ENV_FILES: tuple[str, ...] = (".env",)
    SQLSERVER_KEYS: tuple[str, ...] = ("SQLSERVER_CONNECTION_STRING", "BRANCH_HISTORY_DB_URL")
    BACKEND_KEY = "BRANCH_HISTORY_BACKEND"
    SQLSERVER_BACKEND = "sqlserver"

    def __init__(
        self,
        env_files: Optional[Iterable[Union[str, Path]]] = None,
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Persist the environment data used to resolve configuration values."""
        self._env_files = tuple(env_files) if env_files is not None else self.DEFAULT_ENV_FILES
        self._base_environ: MutableMapping[str, str] = dict(environ) if environ is not None else dict(os.environ)
        self._file_values = self._load_env_files()
        self._merged_env = self._merge_environment()

    def _merge_environment(self) -> Dict[str, str]:
        """Combine values from .env files with the active environment.

        Returns:
            A dictionary containing the merged environment where operating system
            variables override the values defined in .env files.
        """

        merged: Dict[str, str] = dict(self._file_values)
        merged.update(self._base_environ)
        return merged

    def _load_env_files(self) -> Dict[str, str]:
        """Read the configured .env files and return their key-value pairs.

        Returns:
            A dictionary with the aggregated values from the configured .env files.
        """

        values: Dict[str, str] = {}
        root_dir = Path(__file__).resolve().parents[2]
        for candidate in self._env_files:
            path = Path(candidate)
            if not path.is_absolute():
                path = root_dir / path
            if not path.exists():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, raw_value = line.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                value = raw_value.strip().strip('"').strip("'")
                values[key] = value
        return values

    def get_connection_string(self) -> Optional[str]:
        """Return the SQL Server connection string if it is defined.

        Returns:
            The first non-empty connection string found in the known environment keys
            or ``None`` when no value is configured.
        """

        for key in self.SQLSERVER_KEYS:
            candidate = self._merged_env.get(key, "").strip()
            if candidate:
                return candidate
        return None

    def is_sqlserver_backend(self) -> bool:
        """Determine whether the configured backend corresponds to SQL Server.

        Returns:
            ``True`` when the backend is unset or equals ``sqlserver``. ``False`` when
            a different backend is explicitly configured.
        """

        backend = self._merged_env.get(self.BACKEND_KEY, "").strip().lower()
        if not backend:
            return True
        return backend == self.SQLSERVER_BACKEND

    def export(self) -> Dict[str, str]:
        """Expose the merged environment values for additional consumers.

        Returns:
            A dictionary combining .env entries with the current process environment.
        """

        return dict(self._merged_env)
