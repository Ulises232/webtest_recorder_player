"""Utilities to assemble prompts for the card AI generator."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping


def buildUserPrompt(tipo: str, tituloCard: str, inputs: Any) -> str:
    """Create the prompt sent to the language model."""

    if inputs is None:
        data: Mapping[str, Any] = {}
    elif is_dataclass(inputs):
        data = asdict(inputs)
    elif isinstance(inputs, Mapping):
        data = inputs
    else:
        data = {}

    def _value(key: str) -> str:
        """Return a safe string value for the given key."""

        raw = data.get(key, "") if isinstance(data, Mapping) else ""
        return str(raw or "").strip()

    analisis = (
        "### Análisis\n"
        f"1. Descripción del Problema: {_value('analisisDescProblema')}\n"
        f"2. Revisión del Sistema: {_value('analisisRevisionSistema')}\n"
        f"3. Análisis de Datos: {_value('analisisDatos')}\n"
        f"4. Comparación con Reglas Establecidas: {_value('analisisCompReglas')}"
    )

    recomendacion = (
        "### Recomendación\n"
        f"1. Investigación y Diagnóstico: {_value('recoInvestigacion')}\n"
        f"2. Solución Temporal: {_value('recoSolucionTemporal')}\n"
        f"3. Implementación de Mejoras: {_value('recoImplMejoras')}\n"
        f"4. Comunicación con los Stakeholders: {_value('recoComStakeholders')}\n"
        f"5. Documentación: {_value('recoDocumentacion')}"
    )

    instruccion_salida = (
        "Genera la respuesta **en JSON** con el siguiente esquema de claves EXACTAS:\n"
        "{\n"
        '  "titulo": string,\n'
        '  "fecha": string,\n'
        '  "hora_inicio": string,\n'
        '  "hora_fin": string,\n'
        '  "lugar": string,\n'
        '  "encabezado_tipo": string,\n'
        '  "descripcion": string,\n'
        '  "que_necesitas": string,\n'
        '  "para_que": string,\n'
        '  "como_necesitas": string,\n'
        '  "requerimientos_funcionales": string[],\n'
        '  "requerimientos_especiales": string[],\n'
        '  "criterios_aceptacion": string[]\n'
        "}\n"
        "Devuelve SOLO el JSON, sin texto adicional."
    )

    encabezado = f"{(tipo or '').strip()}: {tituloCard}".strip()

    return f"{encabezado}\n\n{analisis}\n\n{recomendacion}\n\n{instruccion_salida}\n"


__all__ = ["buildUserPrompt"]
