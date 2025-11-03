"""DAO utilities for the ``dbo.ai_providers`` catalog."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Dict, List

if TYPE_CHECKING:  # pragma: no cover - solo para tipado
    import pymssql

from app.config.ai_config import AIConfiguration
from app.dtos.ai_settings_dto import AIProviderRecordDTO


class AIProviderDAOError(RuntimeError):
    """Raised when the provider catalog cannot be accessed."""


class AIProviderDAO:
    """Manage the catalog of AI providers configured in SQL Server."""

    DEFAULT_PROVIDERS: Dict[str, Dict[str, object]] = {
        "local": {
            "model_name": "qwen/qwen2.5-vl-7b",
            "base_url": "http://127.0.0.1:1234/v1",
            "favorite": True,
            "extra": {"label": "LM Studio (Local)"},
        },
        "openai_mini": {
            "model_name": "gpt-4o-mini",
            "favorite": False,
            "extra": {"label": "OpenAI GPT-4o mini"},
        },
        "openai_turbo": {
            "model_name": "gpt-4-turbo",
            "favorite": False,
            "extra": {"label": "OpenAI GPT-4 Turbo"},
        },
        "mistral": {
            "model_name": "mistral-large-latest",
            "base_url": "https://api.mistral.ai/v1",
            "favorite": False,
            "extra": {"label": "Mistral Large"},
        },
    }

    def __init__(
        self,
        connection_factory: Callable[[], "pymssql.Connection"],
        configuration: AIConfiguration | None = None,
    ) -> None:
        """Persist dependencies required to bootstrap the catalog."""

        self._connection_factory = connection_factory
        self._configuration = configuration or AIConfiguration()
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        """Create the catalog table and seed default providers if needed."""

        if self._schema_ready:
            return

        connection = self._connection_factory()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1
                    FROM sys.tables t
                    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
                    WHERE t.name = 'ai_providers' AND s.name = 'dbo'
                )
                BEGIN
                    CREATE TABLE dbo.ai_providers (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        provider_key VARCHAR(32) NOT NULL UNIQUE,
                        base_url NVARCHAR(2048) NULL,
                        api_key_enc NVARCHAR(MAX) NULL,
                        org_id NVARCHAR(255) NULL,
                        model_name NVARCHAR(255) NULL,
                        extra_json NVARCHAR(MAX) NULL,
                        updated_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
                        favorite BIT NOT NULL DEFAULT (0)
                    );
                END
                """
            )
            for provider_key, defaults in self.DEFAULT_PROVIDERS.items():
                cursor.execute(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM dbo.ai_providers WHERE provider_key = %s
                    )
                    BEGIN
                        INSERT INTO dbo.ai_providers (
                            provider_key,
                            base_url,
                            model_name,
                            extra_json,
                            favorite
                        )
                        VALUES (%s, %s, %s, %s, %s);
                    END
                    """,
                    (
                        provider_key,
                        provider_key,
                        defaults.get("base_url")
                        or (
                            self._configuration.get_api_url()
                            if provider_key == "local"
                            else None
                        ),
                        defaults.get("model_name"),
                        json.dumps(defaults.get("extra", {}), ensure_ascii=False),
                        1 if defaults.get("favorite") else 0,
                    ),
                )
            connection.commit()
        except Exception as exc:  # pragma: no cover - depende del controlador SQL
            try:
                connection.rollback()
            except Exception:  # pragma: no cover - depende del driver
                pass
            connection.close()
            raise AIProviderDAOError("No fue posible preparar la tabla dbo.ai_providers.") from exc
        finally:
            try:
                connection.close()
            except Exception:  # pragma: no cover - limpieza defensiva
                pass

        self._schema_ready = True

    def list_providers(self) -> List[AIProviderRecordDTO]:
        """Return all providers registered in SQL Server."""

        self._ensure_schema()
        connection = self._connection_factory()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT
                    provider_key,
                    base_url,
                    api_key_enc,
                    org_id,
                    model_name,
                    extra_json,
                    updated_at,
                    favorite
                FROM dbo.ai_providers
                ORDER BY provider_key ASC;
                """
            )
            rows = cursor.fetchall()
        except Exception as exc:  # pragma: no cover - depende del driver
            connection.close()
            raise AIProviderDAOError("No fue posible recuperar los proveedores de IA.") from exc

        connection.close()
        providers: List[AIProviderRecordDTO] = []
        for row in rows:
            extra_raw = row[5] or "{}"
            try:
                extra_parsed = json.loads(extra_raw)
            except json.JSONDecodeError:
                extra_parsed = {}
            updated_at = row[6]
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            providers.append(
                AIProviderRecordDTO(
                    providerKey=str(row[0]),
                    baseUrl=row[1],
                    apiKeyEncrypted=row[2],
                    orgId=row[3],
                    modelName=row[4],
                    extra=extra_parsed,
                    updatedAt=updated_at,
                    favorite=bool(row[7]),
                )
            )

        return providers
