"""Validate the HTML export helpers used by the cards AI view."""

import pytest


_ = pytest.importorskip("ttkbootstrap")

from app.views.cards_ai_view import _build_html_document


def test_build_html_document_injects_text_and_lists() -> None:
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
            "Registrar bitácora de timbres rechazados.",
        ],
        "requerimientos_especiales": ["Compatibilidad con PAC autorizado"],
        "criterios_aceptacion": ["Se timbran CFDI de prueba sin errores."],
    }

    html = _build_html_document(content)

    assert "REQ-001 - Ajuste de timbrado" in html
    assert "MEJORA" in html
    assert "2024-06-03" in html
    assert "09:00" in html and "10:30" in html
    assert "<br />" in html  # salto de línea convertido en etiqueta HTML
    assert "<li>El sistema debe recalcular impuestos antes de timbrar.</li>" in html
    assert "&nbsp;" not in html  # todos los campos con datos deben evitar el espacio duro
