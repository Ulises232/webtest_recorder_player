"""Unit tests for the CardAIExportService module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.dtos.card_ai_dto import CardAIOutputDTO, CardDTO
from app.services.card_ai_export_service import CardAIExportFormat, CardAIExportService


def _build_card(
    card_id: int,
    company_name: str,
    sprint_name: str,
    ticket: str,
) -> CardDTO:
    """Return a card DTO populated with the minimum required fields."""

    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return CardDTO(
        cardId=card_id,
        title="Tarjeta de prueba",
        cardType="INCIDENCIA",
        status="pending",
        createdAt=timestamp,
        updatedAt=timestamp,
        ticketId=ticket,
        branchKey="feature/test",
        sprintId=1 if sprint_name else None,
        sprintName=sprint_name,
        companyId=1 if company_name else None,
        companyName=company_name,
    )


def _build_output(card_id: int, content: dict) -> CardAIOutputDTO:
    """Return an output DTO with default metadata and dynamic content."""

    timestamp = datetime(2024, 1, 2, tzinfo=timezone.utc)
    return CardAIOutputDTO(
        outputId=1,
        cardId=card_id,
        inputId=None,
        llmId="llm-local",
        llmModel="gpt-test",
        llmUsage={},
        content=content,
        createdAt=timestamp,
        isBest=False,
        ddeGenerated=False,
    )


def test_export_json_uses_company_and_sprint_directories(tmp_path: Path) -> None:
    """JSON exports must follow Company/Sprint/Ticket.json layout."""

    card = _build_card(1, "Activa", "Sprint 36", "ECL-1")
    output = _build_output(card.cardId, {"descripcion": "Contenido"})
    service = CardAIExportService(base_directory=tmp_path)

    path = service.export_output(card, output, CardAIExportFormat.JSON)

    expected = tmp_path / "Activa" / "Sprint_36" / "ECL-1.json"
    assert path == expected
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["descripcion"] == "Contenido"


def test_export_without_sprint_stores_under_company(tmp_path: Path) -> None:
    """Cards without sprint use only the company folder."""

    card = _build_card(2, "Sistemas Premium", "", "EA-172")
    output = _build_output(card.cardId, {"detalle": "Algo"})
    service = CardAIExportService(base_directory=tmp_path)

    path = service.export_output(card, output, CardAIExportFormat.MARKDOWN)

    expected = tmp_path / "Sistemas_Premium" / "EA-172.md"
    assert path == expected
    assert "## detalle" in path.read_text(encoding="utf-8")


def test_export_html_generates_template_file(tmp_path: Path) -> None:
    """HTML exports should render the configured template."""

    card = _build_card(3, "Licen Corp", "Sprint Especial", "LIC-9")
    output = _build_output(
        card.cardId,
        {
            "titulo": "Titulo de prueba",
            "descripcion": "Descripcion extendida",
            "criterios_aceptacion": ["Caso 1", "Caso 2"],
        },
    )
    service = CardAIExportService(base_directory=tmp_path)

    path = service.export_output(card, output, CardAIExportFormat.HTML)

    expected = tmp_path / "Licen_Corp" / "Sprint_Especial" / "LIC-9.html"
    assert path == expected
    content = path.read_text(encoding="utf-8")
    assert "Descripcion extendida" in content
    assert "<li>Caso 1</li>" in content
