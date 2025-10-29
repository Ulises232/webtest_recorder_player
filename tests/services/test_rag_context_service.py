"""Unit tests for the TF-IDF based RAG context service."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import List

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from app.daos.card_ai_output_dao import CardAIOutputDAOError
from app.dtos.card_ai_dto import CardAIContextDocumentDTO
from app.services.rag_context_service import (
    RAGContextService,
    RAGContextServiceError,
)


class _SuccessfulDAO:
    """Provide predetermined documents for the RAG service tests."""

    def list_recent_outputs_for_context(self, limit: int = 500) -> List[CardAIContextDocumentDTO]:
        """Return a static set of documents regardless of the requested limit."""

        return [
            CardAIContextDocumentDTO(
                outputId=1,
                cardId=10,
                cardTitle="EA-100 Error al iniciar sesión",
                content={
                    "titulo": "Error al autenticar",
                    "descripcion": "El módulo de login rechaza credenciales válidas",
                    "requerimientos_funcionales": [
                        "Registrar intentos fallidos",
                        "Permitir autenticación con correo corporativo",
                    ],
                    "criterios_aceptacion": [
                        "Se valida que el usuario pueda iniciar sesión",
                    ],
                },
            ),
            CardAIContextDocumentDTO(
                outputId=2,
                cardId=11,
                cardTitle="EA-101 Mejorar desempeño del listado",
                content={
                    "titulo": "Optimización de consultas",
                    "descripcion": "La página tarda más de 8 segundos en mostrar datos",
                    "requerimientos_funcionales": [
                        "Implementar índices en la tabla principal",
                    ],
                    "criterios_aceptacion": [
                        "La carga ocurre en menos de 3 segundos",
                    ],
                },
            ),
        ]


class _FailingDAO:
    """Simulate an error when the DAO tries to fetch documents."""

    def list_recent_outputs_for_context(self, limit: int = 500) -> List[CardAIContextDocumentDTO]:
        """Raise the DAO error to propagate it to the service."""

        raise CardAIOutputDAOError("sql down")


class _EmptyDAO:
    """Return no documents to exercise the empty index branch."""

    def list_recent_outputs_for_context(self, limit: int = 500) -> List[CardAIContextDocumentDTO]:
        """Return an empty list ignoring the requested limit."""

        return []


def test_index_and_search_returns_relevant_documents() -> None:
    """The TF-IDF index should return the closest snippets for the query."""

    service = RAGContextService(_SuccessfulDAO())
    indexed = service.index_from_database()
    assert indexed == 2

    context, titles = service.search_context("problema login credenciales")
    assert "Error al autenticar" in context
    assert titles[0] == "Error al autenticar"


def test_index_handles_empty_queries_and_documents() -> None:
    """The service should return empty results when no tokens are available."""

    service = RAGContextService(_SuccessfulDAO())
    service.index_from_database()

    empty_context, empty_titles = service.search_context("   ")
    assert empty_context == ""
    assert empty_titles == []

    service = RAGContextService(_EmptyDAO())
    service.index_from_database()
    context, titles = service.search_context("login")
    assert context == ""
    assert titles == []


def test_index_propagates_dao_errors() -> None:
    """Any DAO error must be wrapped into the service exception."""

    service = RAGContextService(_FailingDAO())
    with pytest.raises(RAGContextServiceError):
        service.index_from_database()
