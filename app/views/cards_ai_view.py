"""Build the UI that orchestrates card selection and AI generations."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403
from ttkbootstrap.widgets import DateEntry

from app.controllers.card_ai_controller import CardAIController
from app.dtos.card_ai_dto import CardAIGenerationResultDTO, CardAIHistoryEntryDTO, CardDTO


TYPE_CHOICES = ("INCIDENCIA", "MEJORA", "HU")
STATUS_CHOICES = ("pending", "in_progress", "done", "closed")


def _format_datetime(value: Optional[datetime]) -> str:
    """Return a friendly formatted datetime string."""

    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


def _calculate_completeness(fields: Dict[str, str]) -> int:
    """Compute the completeness percentage mirroring the service logic."""

    keys = ["descripcion", "analisis", "recomendaciones", "cosas_prevenir", "info_adicional"]
    values = [fields.get(key, "").strip() for key in keys]
    filled = sum(1 for value in values if value)
    return round(100 * filled / len(values)) if values else 0


def _progress_style(progress: tb.Progressbar, percentage: int) -> None:
    """Adjust the progress bar style according to the completion percentage."""

    if percentage < 34:
        progress.configure(bootstyle="danger")
    elif percentage < 67:
        progress.configure(bootstyle="warning")
    else:
        progress.configure(bootstyle="success")


def _export_json(content: Dict[str, object], parent: tk.Misc) -> None:
    """Prompt for a JSON path and save the provided document."""

    path = filedialog.asksaveasfilename(
        parent=parent,
        defaultextension=".json",
        filetypes=[("JSON", "*.json")],
        title="Exportar resultado a JSON",
    )
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(content, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        messagebox.showerror("Error", f"No se pudo exportar el JSON:\n{exc}")
    else:
        messagebox.showinfo("Exportado", f"Archivo guardado en:\n{path}")


def _export_markdown(content: Dict[str, object], parent: tk.Misc) -> None:
    """Transform the JSON into Markdown and persist it to disk."""

    path = filedialog.asksaveasfilename(
        parent=parent,
        defaultextension=".md",
        filetypes=[("Markdown", "*.md")],
        title="Exportar resultado a Markdown",
    )
    if not path:
        return
    try:
        lines: List[str] = ["# Documento generado"]
        for key, value in content.items():
            lines.append(f"\n## {key}")
            if isinstance(value, list):
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(str(value))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    except OSError as exc:
        messagebox.showerror("Error", f"No se pudo exportar el Markdown:\n{exc}")
    else:
        messagebox.showinfo("Exportado", f"Archivo guardado en:\n{path}")


def _export_docx(content: Dict[str, object], parent: tk.Misc) -> None:
    """Generate a minimal DOCX using python-docx if available."""

    try:
        from docx import Document  # type: ignore
    except ImportError:
        messagebox.showerror(
            "Dependencia faltante",
            "No se encontró la librería 'python-docx'. Instala la dependencia para exportar a DOCX.",
        )
        return

    path = filedialog.asksaveasfilename(
        parent=parent,
        defaultextension=".docx",
        filetypes=[("Documento Word", "*.docx")],
        title="Exportar resultado a DOCX",
    )
    if not path:
        return

    try:
        document = Document()
        document.add_heading("Documento DDE/HU", level=1)
        for key, value in content.items():
            document.add_heading(str(key), level=2)
            if isinstance(value, list):
                for item in value:
                    document.add_paragraph(str(item), style="List Bullet")
            else:
                document.add_paragraph(str(value))
        document.save(path)
    except Exception as exc:  # pragma: no cover - depende de la librería externa
        messagebox.showerror("Error", f"No se pudo exportar el DOCX:\n{exc}")
    else:
        messagebox.showinfo("Exportado", f"Archivo guardado en:\n{path}")


def _show_history(parent: tk.Misc, controller: CardAIController, card_id: int) -> None:
    """Display a modal window with the generation history for a card."""

    try:
        history = controller.list_history(card_id)
    except RuntimeError as exc:
        messagebox.showerror("Error", str(exc))
        return

    win = tb.Toplevel(parent)
    win.title("Historial de generación")
    win.geometry("820x520")
    win.transient(parent)
    win.grab_set()

    frame = tb.Frame(win, padding=12)
    frame.pack(fill=BOTH, expand=YES)

    columns = ("fecha", "modelo", "completitud")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
    tree.heading("fecha", text="Fecha")
    tree.heading("modelo", text="Modelo")
    tree.heading("completitud", text="Completitud")
    tree.column("fecha", width=180)
    tree.column("modelo", width=200)
    tree.column("completitud", width=120, anchor="center")

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=YES)
    scrollbar.pack(side=RIGHT, fill=Y)

    detail = tk.Text(win, height=10, wrap="word")
    detail.pack(fill=BOTH, expand=YES, padx=12, pady=(0, 12))

    entries_map: Dict[str, CardAIHistoryEntryDTO] = {}

    def on_select(event: tk.Event | None) -> None:
        """Render the JSON content for the selected history entry."""

        selection = tree.selection()
        if not selection:
            return
        item_id = selection[0]
        entry = entries_map.get(item_id)
        if not entry:
            return
        detail.configure(state="normal")
        detail.delete("1.0", "end")
        pretty = json.dumps(entry.output.content, ensure_ascii=False, indent=2)
        detail.insert("1.0", pretty)
        detail.configure(state="disabled")

    for idx, entry in enumerate(history, start=1):
        completeness = entry.input.completenessPct if entry.input else 0
        item_id = f"row-{idx}"
        tree.insert(
            "",
            "end",
            iid=item_id,
            values=(
                _format_datetime(entry.output.createdAt),
                entry.output.llmModel or "",
                f"{completeness}%",
            ),
        )
        entries_map[item_id] = entry

    tree.bind("<<TreeviewSelect>>", on_select)
    if history:
        first = tree.get_children("")
        if first:
            tree.selection_set(first[0])
            on_select(None)

    win.wait_window()


def _show_generation_result(
    parent: tk.Misc,
    controller: CardAIController,
    card: CardDTO,
    result: CardAIGenerationResultDTO,
) -> None:
    """Display the result window with export options."""

    win = tb.Toplevel(parent)
    win.title(f"Resultado para tarjeta {card.cardId}")
    win.geometry("880x620")
    win.transient(parent)
    win.grab_set()

    header = tb.Frame(win, padding=12)
    header.pack(fill=X)
    tb.Label(
        header,
        text=f"Tarjeta {card.cardId} - {card.title}",
        font=("Segoe UI", 12, "bold"),
    ).pack(anchor=W)
    tb.Label(
        header,
        text=f"Completitud: {result.completenessPct}% - Modelo: {result.output.llmModel or 'N/D'}",
        bootstyle=SECONDARY,
    ).pack(anchor=W, pady=(4, 0))

    text = tk.Text(win, wrap="word")
    text.pack(fill=BOTH, expand=YES, padx=12, pady=8)
    text.configure(state="normal")
    pretty = json.dumps(result.output.content, ensure_ascii=False, indent=2)
    text.insert("1.0", pretty)
    text.configure(state="disabled")

    actions = tb.Frame(win, padding=12)
    actions.pack(fill=X)

    tb.Button(
        actions,
        text="Exportar JSON",
        bootstyle=SECONDARY,
        command=lambda: _export_json(result.output.content, win),
    ).pack(side=LEFT)
    tb.Button(
        actions,
        text="Exportar Markdown",
        bootstyle=SECONDARY,
        command=lambda: _export_markdown(result.output.content, win),
    ).pack(side=LEFT, padx=6)
    tb.Button(
        actions,
        text="Exportar DOCX",
        bootstyle=SECONDARY,
        command=lambda: _export_docx(result.output.content, win),
    ).pack(side=LEFT, padx=6)

    tb.Button(
        actions,
        text="Historial",
        bootstyle=INFO,
        command=lambda: _show_history(parent, controller, card.cardId),
    ).pack(side=RIGHT)

    def regenerate() -> None:
        """Trigger a new generation using the stored input."""

        if not messagebox.askyesno("Regenerar", "¿Deseas generar nuevamente con los mismos datos?"):
            return
        try:
            new_result = controller.regenerate(result.input.inputId)
        except RuntimeError as exc:
            messagebox.showerror("Error", str(exc))
            return
        win.destroy()
        _show_generation_result(parent, controller, card, new_result)

    tb.Button(actions, text="Regenerar", bootstyle=PRIMARY, command=regenerate).pack(side=RIGHT, padx=(0, 8))

    win.wait_window()


def _open_capture_form(
    root: tk.Misc,
    controller: CardAIController,
    card: CardDTO,
) -> None:
    """Render the modal form that captures the generation inputs."""

    win = tb.Toplevel(root)
    win.title(f"Captura para tarjeta {card.cardId}")
    win.geometry("840x620")
    win.transient(root)
    win.grab_set()

    vars_data = {
        "tipo": tk.StringVar(value=card.cardType or TYPE_CHOICES[0]),
        "descripcion": tk.StringVar(value=""),
        "analisis": tk.StringVar(value=""),
        "recomendaciones": tk.StringVar(value=""),
        "cosas_prevenir": tk.StringVar(value=""),
        "info_adicional": tk.StringVar(value=""),
    }

    def _as_payload() -> Dict[str, object]:
        """Collect the current state of the form."""

        return {
            "cardId": card.cardId,
            "tipo": vars_data["tipo"].get(),
            "descripcion": descripcion.get("1.0", "end").strip(),
            "analisis": analisis.get("1.0", "end").strip(),
            "recomendaciones": recomendaciones.get("1.0", "end").strip(),
            "cosasPrevenir": prevenir.get("1.0", "end").strip(),
            "infoAdicional": adicional.get("1.0", "end").strip(),
        }

    def _update_progress(*_args: object) -> None:
        """Recalculate completeness when fields change."""

        payload = _as_payload()
        completeness = _calculate_completeness(
            {
                "descripcion": payload["descripcion"],
                "analisis": payload["analisis"],
                "recomendaciones": payload["recomendaciones"],
                "cosas_prevenir": payload["cosasPrevenir"],
                "info_adicional": payload["infoAdicional"],
            }
        )
        progress.configure(value=completeness)
        _progress_style(progress, completeness)
        status.set(f"Completitud estimada: {completeness}%")

    container = tb.Frame(win, padding=12)
    container.pack(fill=BOTH, expand=YES)

    tb.Label(
        container,
        text=f"Tarjeta {card.cardId}: {card.title}",
        font=("Segoe UI", 12, "bold"),
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    tb.Label(container, text="Tipo").grid(row=1, column=0, sticky="w")
    tipo_box = ttk.Combobox(container, values=list(TYPE_CHOICES), textvariable=vars_data["tipo"], state="readonly")
    tipo_box.grid(row=1, column=1, sticky="we")

    descripcion = tk.Text(container, height=5, wrap="word")
    analisis = tk.Text(container, height=5, wrap="word")
    recomendaciones = tk.Text(container, height=5, wrap="word")
    prevenir = tk.Text(container, height=5, wrap="word")
    adicional = tk.Text(container, height=4, wrap="word")

    labels = [
        ("Descripción", descripcion),
        ("Análisis", analisis),
        ("Recomendaciones", recomendaciones),
        ("Cosas a prevenir", prevenir),
        ("Información adicional", adicional),
    ]
    row = 2
    for label, widget in labels:
        tb.Label(container, text=label).grid(row=row, column=0, sticky="nw", pady=(8, 0))
        widget.grid(row=row, column=1, sticky="nsew", pady=(8, 0))
        row += 1

    container.grid_columnconfigure(1, weight=1)
    for idx in range(2, row):
        container.grid_rowconfigure(idx, weight=1)

    status = tk.StringVar(value="Completa los campos para mejorar el resultado.")
    progress = tb.Progressbar(container, maximum=100, bootstyle="danger")
    progress.grid(row=row, column=0, columnspan=2, sticky="we", pady=(12, 0))
    tb.Label(container, textvariable=status, bootstyle=SECONDARY).grid(row=row + 1, column=0, columnspan=2, sticky="w")

    buttons = tb.Frame(container)
    buttons.grid(row=row + 2, column=0, columnspan=2, sticky="we", pady=(12, 0))

    running = tk.BooleanVar(value=False)

    def _set_running(value: bool) -> None:
        """Enable or disable the action buttons."""

        if not buttons.winfo_exists():
            return

        running.set(value)
        state = tk.DISABLED if value else tk.NORMAL
        for button in buttons.winfo_children():
            try:
                button.configure(state=state)
            except tk.TclError:
                continue

    def _background_call(func: Callable[[], None]) -> None:
        """Execute the given callable in a worker thread."""

        def worker() -> None:
            try:
                func()
            finally:
                try:
                    win.after(0, lambda: _set_running(False))
                except tk.TclError:
                    _set_running(False)

        _set_running(True)
        threading.Thread(target=worker, daemon=True).start()

    def _save_draft() -> None:
        """Save the current content as draft."""

        payload = _as_payload()

        def _task() -> None:
            try:
                controller.save_draft(payload)
            except RuntimeError as exc:
                error_message = str(exc)
                win.after(
                    0,
                    lambda message=error_message: messagebox.showerror("Error", message),
                )
                return
            win.after(0, lambda: messagebox.showinfo("Guardado", "Se guardó el borrador correctamente."))

        _background_call(_task)

    def _generate() -> None:
        """Call the controller to generate the document."""

        payload = _as_payload()
        completeness = _calculate_completeness(
            {
                "descripcion": payload["descripcion"],
                "analisis": payload["analisis"],
                "recomendaciones": payload["recomendaciones"],
                "cosas_prevenir": payload["cosasPrevenir"],
                "info_adicional": payload["infoAdicional"],
            }
        )
        if completeness < 34:
            if not messagebox.askyesno(
                "Completitud baja",
                "La completitud es menor al 34%. ¿Deseas continuar de todos modos?",
            ):
                return

        def _task() -> None:
            try:
                result = controller.generate_document(payload)
            except RuntimeError as exc:
                error_message = str(exc)
                win.after(
                    0,
                    lambda message=error_message: messagebox.showerror("Error", message),
                )
                return
            win.after(0, lambda: (win.destroy(), _show_generation_result(root, controller, card, result)))

        _background_call(_task)

    tb.Button(buttons, text="Guardar borrador", bootstyle=SECONDARY, command=_save_draft).pack(side=LEFT)
    tb.Button(buttons, text="Generar (IA)", bootstyle=PRIMARY, command=_generate).pack(side=LEFT, padx=6)
    tb.Button(buttons, text="Cancelar", bootstyle=DANGER, command=win.destroy).pack(side=RIGHT)

    for widget in (descripcion, analisis, recomendaciones, prevenir, adicional):
        widget.bind("<KeyRelease>", _update_progress, add="+")

    _update_progress()
    win.wait_window()


def build_cards_ai_view(
    root: tk.Misc,
    parent: tb.Frame,
    controller: CardAIController,
    bind_mousewheel: Callable[[tk.Widget, Callable[..., None]], None],
) -> None:
    """Populate the cards AI assistant view inside the provided frame."""

    for widget in parent.winfo_children():
        widget.destroy()

    filters_frame = tb.Frame(parent, padding=12)
    filters_frame.pack(fill=X)

    tb.Label(filters_frame, text="Tipo").grid(row=0, column=0, sticky="w")
    tipo_var = tk.StringVar(value="")
    tipo_box = ttk.Combobox(filters_frame, values=("",) + TYPE_CHOICES, textvariable=tipo_var, width=16)
    tipo_box.grid(row=1, column=0, sticky="we", padx=(0, 10))

    tb.Label(filters_frame, text="Status").grid(row=0, column=1, sticky="w")
    status_var = tk.StringVar(value="")
    status_box = ttk.Combobox(filters_frame, values=("",) + STATUS_CHOICES, textvariable=status_var, width=16)
    status_box.grid(row=1, column=1, sticky="we", padx=(0, 10))

    tb.Label(filters_frame, text="Fecha inicio").grid(row=0, column=2, sticky="w")
    start_var = DateEntry(filters_frame, dateformat="%Y-%m-%d")
    start_var.grid(row=1, column=2, sticky="we", padx=(0, 10))
    start_var.entry.delete(0, tk.END)

    tb.Label(filters_frame, text="Fecha fin").grid(row=0, column=3, sticky="w")
    end_var = DateEntry(filters_frame, dateformat="%Y-%m-%d")
    end_var.grid(row=1, column=3, sticky="we", padx=(0, 10))
    end_var.entry.delete(0, tk.END)

    tb.Label(filters_frame, text="Buscar").grid(row=0, column=4, sticky="w")
    search_var = tk.StringVar(value="")
    search_entry = tb.Entry(filters_frame, textvariable=search_var)
    search_entry.grid(row=1, column=4, sticky="we")

    filters_frame.grid_columnconfigure(4, weight=1)

    table_frame = tb.Frame(parent, padding=(12, 0))
    table_frame.pack(fill=BOTH, expand=YES)

    columns = ("id", "titulo", "tipo", "status", "actualizado")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
    tree.heading("id", text="ID")
    tree.heading("titulo", text="Título")
    tree.heading("tipo", text="Tipo")
    tree.heading("status", text="Status")
    tree.heading("actualizado", text="Actualizado")
    tree.column("id", width=80, anchor="center")
    tree.column("titulo", width=360)
    tree.column("tipo", width=120)
    tree.column("status", width=120)
    tree.column("actualizado", width=160)

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=YES)
    scrollbar.pack(side=RIGHT, fill=Y)
    bind_mousewheel(tree, tree.yview)

    actions_frame = tb.Frame(parent, padding=12)
    actions_frame.pack(fill=X)
    status_label = tb.Label(actions_frame, text="Selecciona una tarjeta para comenzar.", bootstyle=SECONDARY)
    status_label.pack(side=LEFT)
    generate_button = tb.Button(
        actions_frame,
        text="Generar DDE/HU",
        bootstyle=PRIMARY,
        state=tk.DISABLED,
        command=lambda: _open_capture_form(root, controller, selected_card[0]) if selected_card else None,
    )
    generate_button.pack(side=RIGHT)

    selected_card: List[CardDTO] = []
    current_cards: List[CardDTO] = []

    def _parse_date(entry: DateEntry) -> Optional[datetime]:
        """Return the selected date or ``None`` when the field is empty."""

        value = entry.entry.get().strip()
        if not value:
            return None
        try:
            return datetime.strptime(value + " 00:00", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def _refresh() -> None:
        """Load the cards from the controller applying filters."""

        filters = {
            "tipo": tipo_var.get().strip() or None,
            "status": status_var.get().strip() or None,
            "fechaInicio": _parse_date(start_var),
            "fechaFin": _parse_date(end_var),
            "busqueda": search_var.get().strip() or None,
        }
        try:
            cards = controller.list_cards(filters)
        except RuntimeError as exc:
            messagebox.showerror("Error", str(exc))
            return

        current_cards[:] = cards
        selected_card.clear()
        generate_button.configure(state=tk.DISABLED)
        tree.delete(*tree.get_children(""))
        for card in cards:
            tree.insert(
                "",
                "end",
                iid=str(card.cardId),
                values=(
                    card.cardId,
                    card.title,
                    card.cardType,
                    card.status,
                    _format_datetime(card.updatedAt or card.createdAt),
                ),
            )
        status_label.configure(text=f"{len(cards)} tarjeta(s) encontradas.")

    def _on_select(event: tk.Event) -> None:
        """Enable the generate button when a card is selected."""

        selection = tree.selection()
        if not selection:
            selected_card.clear()
            generate_button.configure(state=tk.DISABLED)
            return
        card_id = int(selection[0])
        for card in current_cards:
            if card.cardId == card_id:
                selected_card[:] = [card]
                break
        generate_button.configure(state=tk.NORMAL if selected_card else tk.DISABLED)

    tree.bind("<<TreeviewSelect>>", _on_select)

    debounce_id = None

    def _schedule_refresh(*_args: object) -> None:
        """Apply debounce to the search entry."""

        nonlocal debounce_id
        if debounce_id is not None:
            parent.after_cancel(debounce_id)
        debounce_id = parent.after(300, _refresh)

    for widget in (tipo_box, status_box):
        widget.bind("<<ComboboxSelected>>", lambda *_: _refresh(), add="+")
    start_var.bind("<<DateEntrySelected>>", lambda *_: _refresh(), add="+")
    end_var.bind("<<DateEntrySelected>>", lambda *_: _refresh(), add="+")
    search_var.trace_add("write", lambda *_: _schedule_refresh())

    _refresh()

