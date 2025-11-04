"""Validate the HTML export helpers used by the cards AI export service."""

import pytest


_ = pytest.importorskip("ttkbootstrap")

from app.services.card_ai_export_service import CardAIExportService


def test_build_html_document_injects_text_and_lists(tmp_path) -> None:
    """The HTML export should render strings, lists and fallbacks correctly."""

    content = {
        "titulo": "REQ-001 - Ajuste de timbrado",
        "tipo": "MEJORA",
        "fecha": "2024-06-03",
        "hora_inicio": "09:00",
        "hora_fin": "10:30",
        "lugar": "Sistemas Premium",
        "que_necesitas": "Actualizar el motor de timbrado.\nCon compatibilidad con PAC.",
        "para_que_lo_necesitas": "Garantizar el timbrado oportuno de CFDI.",
        "como_lo_necesitas": "Implementar validaciones adicionales en el proceso.",
        "requerimientos_funcionales": [
            "El sistema debe recalcular impuestos antes de timbrar.",
            "Registrar bitacora de timbres rechazados.",
        ],
        "requerimientos_especiales": ["Compatibilidad con PAC autorizado"],
        "criterios_aceptacion": ["Se timbran CFDI de prueba sin errores."],
    }

    service = CardAIExportService(base_directory=tmp_path)
    template = service._load_html_template()
    html = service._fill_html_template(template, content)

    assert "2024-06-03" in html
    assert "09:00" in html and "10:30" in html
    assert "Actualizar el motor de timbrado.<br />Con compatibilidad con PAC." in html
    assert "<li>El sistema debe recalcular impuestos antes de timbrar.</li>" in html
    assert "&nbsp;" in html  # los campos sin datos mantienen el espacio duro
