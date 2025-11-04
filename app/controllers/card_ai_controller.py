"""Controller orchestrating the cards AI assistant interactions."""

from __future__ import annotations

from typing import Dict, List, Optional

from app.dtos.ai_settings_dto import AIProviderRuntimeDTO
from app.dtos.card_ai_dto import (
    CardAIHistoryEntryDTO,
    CardAIInputDTO,
    CardAIGenerationResultDTO,
    CardAIOutputDTO,
    CardDTO,
    CardFiltersDTO,
    CatalogOptionDTO,
    card_ai_request_from_dict,
)
from app.services.card_ai_service import CardAIService, CardAIServiceError


class CardAIController:
    """Expose a simplified API tailored for the Tkinter views."""

    def __init__(self, service: CardAIService) -> None:
        """Store the service that performs the heavy lifting."""

        self._service = service

    def list_cards(self, filters: Dict[str, object]) -> List[CardDTO]:
        """Return cards matching the filters provided by the view."""

        best_selection = None
        best_filter = (
            str(filters.get("estadoMejor")).strip().lower() if filters.get("estadoMejor") else ""
        )
        if best_filter.startswith("con"):
            best_selection = True
        elif best_filter.startswith("sin"):
            best_selection = False

        dde_generated = None
        dde_filter = (
            str(filters.get("estadoDde")).strip().lower() if filters.get("estadoDde") else ""
        )
        if dde_filter.startswith("con"):
            dde_generated = True
        elif dde_filter.startswith("sin"):
            dde_generated = False

        incident_type_id: Optional[int] = None
        if "tipoId" in filters:
            try:
                incident_type_id = int(filters["tipoId"]) if filters["tipoId"] is not None else None
            except (TypeError, ValueError):
                incident_type_id = None
        elif filters.get("tipo"):
            try:
                incident_type_id = int(filters["tipo"])
            except (TypeError, ValueError):
                incident_type_id = None

        company_id: Optional[int] = None
        if "empresaId" in filters:
            try:
                company_id = int(filters["empresaId"]) if filters["empresaId"] is not None else None
            except (TypeError, ValueError):
                company_id = None

        dto = CardFiltersDTO(
            cardType=str(filters.get("tipo")) if filters.get("tipo") else None,
            status=str(filters.get("status")) if filters.get("status") else None,
            startDate=filters.get("fechaInicio"),
            endDate=filters.get("fechaFin"),
            searchText=str(filters.get("busqueda")) if filters.get("busqueda") else None,
            bestSelection=best_selection,
            ddeGenerated=dde_generated,
            incidentTypeId=incident_type_id,
            companyId=company_id,
        )
        try:
            return self._service.list_cards(dto)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def list_providers(self) -> List[AIProviderRuntimeDTO]:
        """Expose the configured AI providers."""

        try:
            return self._service.list_providers()
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def get_default_provider_key(self) -> str:
        """Return the provider key selected by default."""

        try:
            return self._service.get_default_provider_key()
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def save_draft(self, payload: Dict[str, object]) -> CardAIInputDTO:
        """Persist a new draft entry for the selected card."""

        dto = card_ai_request_from_dict(payload)
        try:
            return self._service.save_draft(dto)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def generate_document(self, payload: Dict[str, object]) -> CardAIGenerationResultDTO:
        """Trigger a new generation and persist the resulting document."""

        dto = card_ai_request_from_dict(payload)
        try:
            return self._service.generate_document(dto)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def regenerate(self, input_id: int) -> CardAIGenerationResultDTO:
        """Trigger a new generation using a stored input identifier."""

        try:
            return self._service.regenerate_from_input(input_id)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def list_inputs(self, card_id: int, limit: int = 50) -> List[CardAIInputDTO]:
        """Return the captured inputs for a card."""

        try:
            return self._service.list_inputs(card_id, limit=limit)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def list_history(self, card_id: int, limit: int = 20) -> List[CardAIHistoryEntryDTO]:
        """Return the output history for a card."""

        try:
            return self._service.list_history(card_id, limit=limit)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def delete_output(self, output_id: int) -> None:
        """Remove a stored output entry from the history."""

        try:
            self._service.delete_output(output_id)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def mark_output_as_best(self, output_id: int) -> CardAIOutputDTO:
        """Mark the selected output as the preferred document."""

        try:
            return self._service.mark_output_as_best(output_id)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def clear_output_best_flag(self, output_id: int) -> CardAIOutputDTO:
        """Remove the preferred flag from the selected output."""

        try:
            return self._service.clear_output_best_flag(output_id)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def mark_output_dde_generated(self, output_id: int, generated: bool) -> CardAIOutputDTO:
        """Toggle the DDE generated flag for the selected output."""

        try:
            return self._service.set_output_dde_generated(output_id, generated)
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def list_incidence_types(self) -> List[CatalogOptionDTO]:
        """Expose the catalog of incident types."""

        try:
            return self._service.list_incidence_types()
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def list_companies(self) -> List[CatalogOptionDTO]:
        """Expose the catalog of companies."""

        try:
            return self._service.list_companies()
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

    def list_statuses(self) -> List[str]:
        """Expose the distinct card statuses."""

        try:
            return self._service.list_statuses()
        except CardAIServiceError as exc:
            raise RuntimeError(str(exc)) from exc

