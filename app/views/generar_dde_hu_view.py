"""User interface for the DDE/HU generator powered by a local LLM."""

from __future__ import annotations

import json
import threading
from queue import Empty, Queue
from typing import Callable, Dict, List, Optional
import tkinter as tk
from tkinter import filedialog, ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403

from app.controllers.cards_controller import CardsController, CardsControllerError
from app.dtos.card_ai_dto import CardAIInputPayload, CardFilters


TYPE_OPTIONS = ["", "INCIDENCIA", "MEJORA", "HU"]
STATUS_OPTIONS = ["", "pending", "in_progress", "done", "closed"]


def buildGenerarDdeHuView(
    root: tk.Misc,
    parent: tb.Frame,
    controller: CardsController,
    messagebox_service,
    bind_mousewheel: Callable[[tk.Widget, Callable[..., None]], None],
) -> None:
    """Render the AI-assisted document generator inside ``parent``."""

    Messagebox = messagebox_service

    for child in parent.winfo_children():
        child.destroy()

    selected_card_id = tk.IntVar(value=0)
    status_var = tk.StringVar(value="Listo para iniciar.")
    completeness_var = tk.IntVar(value=0)

    cards_data: List[Dict[str, object]] = []
    history_data: List[Dict[str, object]] = []
    current_result: Optional[Dict[str, object]] = None
    ui_queue: Queue[Callable[[], None]] = Queue()

    def _dispatch_to_ui(callback: Callable[[], None]) -> None:
        """Enqueue a callback to run on the Tkinter thread."""

        ui_queue.put(callback)

    def _process_ui_queue() -> None:
        """Execute callbacks produced by background workers."""

        while True:
            try:
                callback = ui_queue.get_nowait()
            except Empty:
                break
            try:
                callback()
            except Exception as exc:  # pragma: no cover - safeguard for UI callbacks
                Messagebox.showerror(
                    "Generar DDE/HU",
                    f"Ocurrió un error al actualizar la interfaz:\n{exc}",
                )
        root.after(50, _process_ui_queue)

    root.after(50, _process_ui_queue)

    container = tb.Panedwindow(parent, orient="horizontal")
    container.pack(fill=BOTH, expand=YES)

    list_frame = tb.Frame(container, padding=10)
    form_frame = tb.Frame(container, padding=10)
    container.add(list_frame, weight=1)
    container.add(form_frame, weight=2)

    # --- Card filters and listing ---
    tb.Label(list_frame, text="Tarjetas", font=("Segoe UI", 12, "bold")).pack(anchor=W)
    filters_frame = tb.Frame(list_frame)
    filters_frame.pack(fill=X, pady=(6, 8))

    tb.Label(filters_frame, text="Tipo").grid(row=0, column=0, sticky="w")
    tipo_var = tk.StringVar(value="")
    tipo_combo = tb.Combobox(filters_frame, textvariable=tipo_var, values=TYPE_OPTIONS, state="readonly")
    tipo_combo.grid(row=1, column=0, sticky="we", padx=(0, 6))

    tb.Label(filters_frame, text="Status").grid(row=0, column=1, sticky="w")
    status_filter_var = tk.StringVar(value="")
    status_combo = tb.Combobox(filters_frame, textvariable=status_filter_var, values=STATUS_OPTIONS, state="readonly")
    status_combo.grid(row=1, column=1, sticky="we", padx=(0, 6))

    tb.Label(filters_frame, text="Buscar").grid(row=0, column=2, sticky="w")
    search_var = tk.StringVar(value="")
    search_entry = tb.Entry(filters_frame, textvariable=search_var)
    search_entry.grid(row=1, column=2, sticky="we")

    for column in range(3):
        filters_frame.grid_columnconfigure(column, weight=1)

    cards_tree = ttk.Treeview(list_frame, show="headings", columns=("id", "title", "tipo", "status", "fecha"), height=18)
    cards_tree.heading("id", text="ID")
    cards_tree.heading("title", text="Título")
    cards_tree.heading("tipo", text="Tipo")
    cards_tree.heading("status", text="Status")
    cards_tree.heading("fecha", text="Fecha")
    cards_tree.column("id", width=70, anchor="center")
    cards_tree.column("title", width=220, anchor="w")
    cards_tree.column("tipo", width=110, anchor="center")
    cards_tree.column("status", width=120, anchor="center")
    cards_tree.column("fecha", width=140, anchor="center")
    cards_tree.pack(fill=BOTH, expand=YES)

    cards_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=cards_tree.yview)
    cards_tree.configure(yscrollcommand=cards_scroll.set)
    cards_scroll.pack(fill=Y, side=RIGHT)
    bind_mousewheel(cards_tree, cards_tree.yview)

    def _refresh_cards_async() -> None:
        """Load cards from the controller in a background thread."""

        status_var.set("Cargando tarjetas...")

        selected_tipo = tipo_var.get() or None
        selected_status = status_filter_var.get() or None
        search_text = search_var.get() or ""
        local_filters = CardFilters(
            tipo=selected_tipo,
            status=selected_status,
            startDate=None,
            endDate=None,
            searchText=search_text,
        )

        def worker(filters: CardFilters) -> None:
            nonlocal cards_data
            try:
                result = controller.listCards(filters)
            except CardsControllerError as exc:
                error_message = str(exc)
                _dispatch_to_ui(lambda msg=error_message: Messagebox.showerror("Tarjetas", msg))
                _dispatch_to_ui(lambda: status_var.set("No fue posible cargar las tarjetas."))
                return

            def apply() -> None:
                nonlocal cards_data
                cards_data = []
                cards_tree.delete(*cards_tree.get_children())
                for card in result:
                    cards_data.append(
                        {
                            "id": card.cardId,
                            "title": card.title,
                            "tipo": card.tipo,
                            "status": card.status,
                            "fecha": card.createdAt,
                        }
                    )
                    fecha_txt = card.createdAt.astimezone().strftime("%Y-%m-%d %H:%M") if card.createdAt else ""
                    cards_tree.insert("", "end", values=(card.cardId, card.title, card.tipo, card.status, fecha_txt))
                status_var.set(f"Tarjetas cargadas: {len(cards_data)}")

            _dispatch_to_ui(apply)

        threading.Thread(target=worker, args=(local_filters,), daemon=True).start()

    def _on_search_change(*_) -> None:
        """Debounce the search field updates."""

        if hasattr(_on_search_change, "_after_id") and _on_search_change._after_id:
            root.after_cancel(_on_search_change._after_id)
        _on_search_change._after_id = root.after(300, _refresh_cards_async)

    _on_search_change._after_id = None  # type: ignore[attr-defined]

    tipo_combo.bind("<<ComboboxSelected>>", lambda _: _refresh_cards_async())
    status_combo.bind("<<ComboboxSelected>>", lambda _: _refresh_cards_async())
    search_var.trace_add("write", _on_search_change)

    # --- Form definition ---
    header = tb.Frame(form_frame)
    header.pack(fill=X)
    tb.Label(header, text="Generar DDE/HU", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
    tb.Label(header, textvariable=status_var, bootstyle=SECONDARY).pack(side=RIGHT)

    form_fields = tb.Labelframe(form_frame, text="Captura", padding=10)
    form_fields.pack(fill=BOTH, expand=YES, pady=(8, 0))

    tb.Label(form_fields, text="Tipo").grid(row=0, column=0, sticky="w", pady=(0, 4))
    tipo_form_var = tk.StringVar(value="HU")
    tipo_form_combo = tb.Combobox(form_fields, textvariable=tipo_form_var, values=TYPE_OPTIONS, state="readonly")
    tipo_form_combo.grid(row=0, column=1, sticky="w", padx=(0, 6))

    completeness_label = tb.Label(form_fields, text="Completitud: 0%", bootstyle=DANGER)
    completeness_label.grid(row=0, column=2, sticky="e", padx=(20, 0))

    text_fields: Dict[str, tk.Text] = {}

    def _add_text_row(row: int, label: str, key: str) -> None:
        """Create a labeled Text widget bound to a payload key."""

        tb.Label(form_fields, text=label).grid(row=row, column=0, columnspan=3, sticky="w", pady=(6, 2))
        widget = tk.Text(form_fields, height=4, wrap="word")
        widget.configure(font=("Segoe UI", 10))
        widget.grid(row=row + 1, column=0, columnspan=3, sticky="nsew", pady=(0, 6))
        form_fields.grid_rowconfigure(row + 1, weight=1)
        text_fields[key] = widget
        bind_mousewheel(widget, widget.yview)
        widget.bind("<KeyRelease>", lambda _e: _update_completeness())

    _add_text_row(1, "Descripción del Problema", "analisisDescProblema")
    _add_text_row(3, "Revisión del Sistema", "analisisRevisionSistema")
    _add_text_row(5, "Análisis de Datos", "analisisDatos")
    _add_text_row(7, "Comparación con Reglas Establecidas", "analisisCompReglas")
    _add_text_row(9, "Investigación y Diagnóstico", "recoInvestigacion")
    _add_text_row(11, "Solución Temporal", "recoSolucionTemporal")
    _add_text_row(13, "Implementación de Mejoras", "recoImplMejoras")
    _add_text_row(15, "Comunicación con Stakeholders", "recoComStakeholders")
    _add_text_row(17, "Documentación", "recoDocumentacion")

    def _clear_form() -> None:
        """Reset the capture fields to their defaults."""

        tipo_form_var.set("HU")
        for widget in text_fields.values():
            widget.delete("1.0", tk.END)
        completeness_var.set(0)
        completeness_label.configure(text="Completitud: 0%", bootstyle=DANGER)

    def _set_form_from_payload(payload: CardAIInputPayload) -> None:
        """Populate the form widgets from an existing payload."""

        tipo_form_var.set((payload.tipo or "HU").upper())
        text_fields["analisisDescProblema"].delete("1.0", tk.END)
        text_fields["analisisDescProblema"].insert(tk.END, payload.analisisDescProblema or "")
        text_fields["analisisRevisionSistema"].delete("1.0", tk.END)
        text_fields["analisisRevisionSistema"].insert(tk.END, payload.analisisRevisionSistema or "")
        text_fields["analisisDatos"].delete("1.0", tk.END)
        text_fields["analisisDatos"].insert(tk.END, payload.analisisDatos or "")
        text_fields["analisisCompReglas"].delete("1.0", tk.END)
        text_fields["analisisCompReglas"].insert(tk.END, payload.analisisCompReglas or "")
        text_fields["recoInvestigacion"].delete("1.0", tk.END)
        text_fields["recoInvestigacion"].insert(tk.END, payload.recoInvestigacion or "")
        text_fields["recoSolucionTemporal"].delete("1.0", tk.END)
        text_fields["recoSolucionTemporal"].insert(tk.END, payload.recoSolucionTemporal or "")
        text_fields["recoImplMejoras"].delete("1.0", tk.END)
        text_fields["recoImplMejoras"].insert(tk.END, payload.recoImplMejoras or "")
        text_fields["recoComStakeholders"].delete("1.0", tk.END)
        text_fields["recoComStakeholders"].insert(tk.END, payload.recoComStakeholders or "")
        text_fields["recoDocumentacion"].delete("1.0", tk.END)
        text_fields["recoDocumentacion"].insert(tk.END, payload.recoDocumentacion or "")
        _update_completeness()

    def _gather_payload() -> Optional[CardAIInputPayload]:
        """Collect current form values into a payload object."""

        card_id = selected_card_id.get()
        if not card_id:
            Messagebox.showwarning("Generar", "Selecciona una tarjeta antes de capturar información.")
            return None
        payload = CardAIInputPayload(
            cardId=card_id,
            tipo=tipo_form_var.get() or "HU",
            analisisDescProblema=text_fields["analisisDescProblema"].get("1.0", tk.END).strip(),
            analisisRevisionSistema=text_fields["analisisRevisionSistema"].get("1.0", tk.END).strip(),
            analisisDatos=text_fields["analisisDatos"].get("1.0", tk.END).strip(),
            analisisCompReglas=text_fields["analisisCompReglas"].get("1.0", tk.END).strip(),
            recoInvestigacion=text_fields["recoInvestigacion"].get("1.0", tk.END).strip(),
            recoSolucionTemporal=text_fields["recoSolucionTemporal"].get("1.0", tk.END).strip(),
            recoImplMejoras=text_fields["recoImplMejoras"].get("1.0", tk.END).strip(),
            recoComStakeholders=text_fields["recoComStakeholders"].get("1.0", tk.END).strip(),
            recoDocumentacion=text_fields["recoDocumentacion"].get("1.0", tk.END).strip(),
        )
        return payload

    def _update_completeness(*_) -> None:
        """Refresh the completeness indicator according to form data."""

        if not selected_card_id.get():
            completeness_label.configure(text="Completitud: 0%", bootstyle=DANGER)
            completeness_var.set(0)
            return
        payload = CardAIInputPayload(
            cardId=selected_card_id.get(),
            tipo=tipo_form_var.get() or "HU",
            analisisDescProblema=text_fields["analisisDescProblema"].get("1.0", tk.END).strip(),
            analisisRevisionSistema=text_fields["analisisRevisionSistema"].get("1.0", tk.END).strip(),
            analisisDatos=text_fields["analisisDatos"].get("1.0", tk.END).strip(),
            analisisCompReglas=text_fields["analisisCompReglas"].get("1.0", tk.END).strip(),
            recoInvestigacion=text_fields["recoInvestigacion"].get("1.0", tk.END).strip(),
            recoSolucionTemporal=text_fields["recoSolucionTemporal"].get("1.0", tk.END).strip(),
            recoImplMejoras=text_fields["recoImplMejoras"].get("1.0", tk.END).strip(),
            recoComStakeholders=text_fields["recoComStakeholders"].get("1.0", tk.END).strip(),
            recoDocumentacion=text_fields["recoDocumentacion"].get("1.0", tk.END).strip(),
        )
        pct = controller.calculateCompleteness(payload)
        completeness_var.set(pct)
        bootstyle = DANGER
        if pct >= 67:
            bootstyle = SUCCESS
        elif pct >= 34:
            bootstyle = WARNING
        completeness_label.configure(text=f"Completitud: {pct}%", bootstyle=bootstyle)

    tipo_form_combo.bind("<<ComboboxSelected>>", _update_completeness)

    # --- Result preview and history ---
    result_frame = tb.Labelframe(form_frame, text="Resultado", padding=10)
    result_frame.pack(fill=BOTH, expand=YES, pady=(8, 0))

    result_text = tk.Text(result_frame, height=12, wrap="word")
    result_text.configure(font=("Consolas", 10))
    result_text.pack(fill=BOTH, expand=YES, side=LEFT)
    bind_mousewheel(result_text, result_text.yview)

    history_frame = tb.Frame(result_frame, padding=(6, 0))
    history_frame.pack(fill=Y, side=RIGHT)

    tb.Label(history_frame, text="Historial", font=("Segoe UI", 10, "bold")).pack(anchor=W)
    history_tree = ttk.Treeview(history_frame, show="headings", columns=("id", "fecha", "modelo", "input"), height=12)
    history_tree.heading("id", text="Output")
    history_tree.heading("fecha", text="Fecha")
    history_tree.heading("modelo", text="Modelo")
    history_tree.heading("input", text="Input")
    history_tree.column("id", width=80, anchor="center")
    history_tree.column("fecha", width=140, anchor="center")
    history_tree.column("modelo", width=120, anchor="center")
    history_tree.column("input", width=80, anchor="center")
    history_tree.pack(fill=BOTH, expand=YES)
    bind_mousewheel(history_tree, history_tree.yview)

    history_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=history_tree.yview)
    history_tree.configure(yscrollcommand=history_scroll.set)
    history_scroll.pack(fill=Y, side=RIGHT)

    def _display_result(data: Optional[Dict[str, object]]) -> None:
        """Show the JSON result in the preview widget."""

        nonlocal current_result
        current_result = data
        result_text.delete("1.0", tk.END)
        if not data:
            return
        try:
            pretty = json.dumps(data, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            pretty = str(data)
        result_text.insert(tk.END, pretty)

    def _load_history(card_id: int) -> None:
        """Fetch history entries for the selected card."""

        history_tree.delete(*history_tree.get_children())
        history_data.clear()

        def worker() -> None:
            try:
                outputs = controller.listOutputs(card_id)
            except CardsControllerError as exc:
                error_message = str(exc)
                _dispatch_to_ui(lambda msg=error_message: Messagebox.showerror("Historial", msg))
                return

            def apply() -> None:
                history_tree.delete(*history_tree.get_children())
                history_data.clear()
                for output in outputs:
                    created_txt = output.createdAt.astimezone().strftime("%Y-%m-%d %H:%M") if output.createdAt else ""
                    history_tree.insert(
                        "",
                        "end",
                        values=(output.outputId or "", created_txt, output.llmModel or "", output.inputId or ""),
                    )
                    history_data.append(
                        {
                            "outputId": output.outputId,
                            "inputId": output.inputId,
                            "content": output.content,
                        }
                    )

            _dispatch_to_ui(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _on_card_selected(_event=None) -> None:
        """React when the user selects a different card."""

        selection = cards_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        values = cards_tree.item(item_id, "values")
        if not values:
            return
        card_id = int(values[0])
        selected_card_id.set(card_id)
        status_var.set(f"Tarjeta seleccionada: {card_id}")
        _clear_form()
        _display_result(None)
        _load_history(card_id)

        def worker() -> None:
            try:
                latest = controller.loadLatestInput(card_id)
            except CardsControllerError as exc:
                error_message = str(exc)
                _dispatch_to_ui(lambda msg=error_message: Messagebox.showerror("Entradas", msg))
                return

            if latest is None:
                return

            payload = CardAIInputPayload(
                cardId=card_id,
                tipo=latest.tipo,
                analisisDescProblema=latest.analisisDescProblema,
                analisisRevisionSistema=latest.analisisRevisionSistema,
                analisisDatos=latest.analisisDatos,
                analisisCompReglas=latest.analisisCompReglas,
                recoInvestigacion=latest.recoInvestigacion,
                recoSolucionTemporal=latest.recoSolucionTemporal,
                recoImplMejoras=latest.recoImplMejoras,
                recoComStakeholders=latest.recoComStakeholders,
                recoDocumentacion=latest.recoDocumentacion,
            )

            _dispatch_to_ui(lambda: _set_form_from_payload(payload))

        threading.Thread(target=worker, daemon=True).start()

    cards_tree.bind("<<TreeviewSelect>>", _on_card_selected)

    def _save_draft() -> None:
        """Persist the captured inputs as a draft."""

        payload = _gather_payload()
        if payload is None:
            return

        status_var.set("Guardando borrador...")

        def worker() -> None:
            try:
                record = controller.saveDraft(payload)
            except CardsControllerError as exc:
                error_message = str(exc)
                _dispatch_to_ui(lambda msg=error_message: Messagebox.showerror("Borrador", msg))
                _dispatch_to_ui(lambda: status_var.set("Error al guardar el borrador."))
                return
            _dispatch_to_ui(lambda: status_var.set(f"Borrador guardado #{record.inputId}."))

        threading.Thread(target=worker, daemon=True).start()

    def _generate_document() -> None:
        """Call the LLM and display the generated document."""

        payload = _gather_payload()
        if payload is None:
            return
        pct = controller.calculateCompleteness(payload)
        if pct < 34:
            if not Messagebox.askyesno(
                "Baja completitud",
                "La captura tiene menos del 34% de completitud. ¿Deseas generar de todos modos?",
            ):
                return

        status_var.set("Generando documento con IA...")

        def worker() -> None:
            try:
                result = controller.generateDocument(payload)
            except CardsControllerError as exc:
                error_message = str(exc)
                _dispatch_to_ui(lambda msg=error_message: Messagebox.showerror("Generar", msg))
                _dispatch_to_ui(lambda: status_var.set("Error al generar el documento."))
                return

            def apply() -> None:
                status_var.set("Documento generado correctamente.")
                _display_result(result.outputRecord.content)
                _load_history(payload.cardId)
                _update_completeness()

            _dispatch_to_ui(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _regenerate_from_history() -> None:
        """Re-launch the LLM based on the selected history entry."""

        selection = history_tree.selection()
        if not selection:
            Messagebox.showinfo("Historial", "Selecciona un resultado para regenerar.")
            return
        item = selection[0]
        values = history_tree.item(item, "values")
        if not values:
            return
        input_id = values[3]
        if not input_id:
            Messagebox.showwarning("Historial", "El elemento seleccionado no tiene entradas asociadas.")
            return
        try:
            input_id_int = int(input_id)
        except ValueError:
            Messagebox.showwarning("Historial", "El identificador de entrada es inválido.")
            return

        status_var.set("Regenerando documento...")

        def worker() -> None:
            try:
                result = controller.regenerateFromInput(input_id_int)
            except CardsControllerError as exc:
                error_message = str(exc)
                _dispatch_to_ui(lambda msg=error_message: Messagebox.showerror("Regenerar", msg))
                _dispatch_to_ui(lambda: status_var.set("Error al regenerar el documento."))
                return

            def apply() -> None:
                status_var.set("Documento regenerado correctamente.")
                _display_result(result.outputRecord.content)
                _load_history(result.inputRecord.cardId)

            _dispatch_to_ui(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _on_history_select(_event=None) -> None:
        """Show the JSON for the selected history row."""

        selection = history_tree.selection()
        if not selection:
            return
        index = history_tree.index(selection[0])
        if 0 <= index < len(history_data):
            _display_result(history_data[index]["content"])

    history_tree.bind("<<TreeviewSelect>>", _on_history_select)

    def _export_json() -> None:
        """Save the current JSON result to disk."""

        if not current_result:
            Messagebox.showinfo("Exportar", "No hay un resultado para exportar.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar resultado",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(current_result, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            Messagebox.showerror("Exportar", f"No fue posible guardar el archivo:\n{exc}")
            return
        Messagebox.showinfo("Exportar", f"Resultado guardado en:\n{path}")

    buttons = tb.Frame(form_frame)
    buttons.pack(fill=X, pady=(10, 0))
    tb.Button(buttons, text="Guardar borrador", bootstyle=SECONDARY, command=_save_draft).pack(side=LEFT)
    tb.Button(buttons, text="Generar", bootstyle=PRIMARY, command=_generate_document).pack(side=LEFT, padx=(10, 0))
    tb.Button(buttons, text="Regenerar", bootstyle=INFO, command=_regenerate_from_history).pack(side=LEFT, padx=(10, 0))
    tb.Button(buttons, text="Exportar JSON", bootstyle=SUCCESS, command=_export_json).pack(side=LEFT, padx=(10, 0))
    tb.Button(buttons, text="Limpiar", bootstyle=LIGHT, command=_clear_form).pack(side=LEFT, padx=(10, 0))

    _refresh_cards_async()


build_generar_dde_hu_view = buildGenerarDdeHuView


__all__ = ["buildGenerarDdeHuView", "build_generar_dde_hu_view"]
