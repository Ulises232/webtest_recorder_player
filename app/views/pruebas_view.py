"""UI components for the 'Pruebas' workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional
import os
import time
import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403
from ttkbootstrap.widgets import DateEntry

from app.dtos.card_ai_dto import CardDTO
from app.dtos.session_dto import SessionDTO, SessionEvidenceDTO


@dataclass
class PruebasViewContext:
    """Expose helper controls from the tests view."""

    buttons: tb.Frame
    notebook: tb.Notebook
    dashboardTab: tk.Widget
    sessionTab: tk.Widget

    def _is_session_tab_active(self) -> bool:
        """Return whether the evidence workflow tab is active."""

        try:
            return self.notebook.index(self.notebook.select()) == self.notebook.index(self.sessionTab)
        except Exception:
            return False

    def show_controls(self) -> None:
        """Display the bottom buttons for the tests workflow."""

        if not self._is_session_tab_active():
            return
        try:
            self.buttons.pack(fill=tk.X)
        except Exception:
            pass

    def hide_controls(self) -> None:
        """Hide the bottom buttons for the tests workflow."""

        try:
            self.buttons.pack_forget()
        except Exception:
            pass

    def refresh_controls_visibility(self) -> None:
        """Synchronize the visibility of the bottom buttons with the active tab."""

        if self._is_session_tab_active():
            self.show_controls()
        else:
            self.hide_controls()

    def select_dashboard(self) -> None:
        """Activate the dashboard tab listing existing sessions."""

        try:
            self.notebook.select(self.dashboardTab)
        except Exception:
            pass
        self.refresh_controls_visibility()

    def select_session_tab(self) -> None:
        """Activate the evidence workflow tab."""

        try:
            self.notebook.select(self.sessionTab)
        except Exception:
            pass
        self.refresh_controls_visibility()


def _format_card_datetime(value: Optional[datetime]) -> str:
    """Return a friendly formatted datetime string for the cards dashboard."""

    if not value:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


def build_pruebas_view(
    root: tk.Misc,
    parent: tb.Frame,
    controller,
    messagebox_service,
    bind_mousewheel: Callable[[tk.Widget, Callable[..., None]], None],
    format_elapsed: Callable[[Optional[int]], str],
    format_timestamp: Callable[[Optional[object]], str],
    select_region_overlay: Callable,
    build_word_fn: Callable,
    import_steps_fn: Callable,
    open_capture_editor_fn: Callable,
) -> PruebasViewContext:
    """Render the tests workflow inside the given frame."""

    Messagebox = messagebox_service
    status = tb.StringVar(value="Listo.")

    dashboard_edit_state: Dict[str, Optional[int]] = {"sessionId": None}

    def _is_dashboard_editing() -> bool:
        """Return whether a session loaded from the dashboard is being edited."""

        return bool(dashboard_edit_state.get("sessionId"))

    def _save_loaded_session_changes() -> None:
        """Persist metadata updates for the session opened from the dashboard."""

        session_id = dashboard_edit_state.get("sessionId")
        if not session_id:
            Messagebox.showinfo("Sesión", "Selecciona una sesión del tablero antes de guardar.")
            return
        error_msg = controller.sessions.update_session_details(
            session_id,
            base_var.get().strip(),
            url_var.get().strip(),
            doc_var.get().strip(),
            ev_var.get().strip(),
        )
        if error_msg:
            Messagebox.showerror("Sesión", error_msg)
            return
        prev_base["val"] = controller.naming.slugify_for_windows(base_var.get() or "reporte")
        session["title"] = (base_var.get() or session.get("title", "")).strip() or session.get("title", "")
        session_saved["val"] = True
        status.set("💾 Sesión actualizada desde el editor.")
        _refresh_cards_table()

    notebook = tb.Notebook(parent, bootstyle="secondary")
    notebook.pack(fill=BOTH, expand=YES)

    dashboard_tab = tb.Frame(notebook, padding=16)
    session_tab = tb.Frame(notebook)
    notebook.add(dashboard_tab, text="Sesiones")
    notebook.add(session_tab, text="Evidencias")

    parent = session_tab

    card1 = tb.Labelframe(parent, text="Datos generales", bootstyle=SECONDARY, padding=12)
    card1.pack(fill=X, pady=(0,12)); card1.columnconfigure(1, weight=1)
    
    tb.Label(card1, text="Nombre base").grid(row=0, column=0, sticky=W, pady=(2,2))
    base_var = tb.StringVar(value="reporte"); tb.Entry(card1, textvariable=base_var).grid(row=0, column=1, sticky=EW, padx=(10,0))
    
    tb.Label(card1, text="URL inicial").grid(row=2, column=0, sticky=W, pady=(10,2))
    urls = controller.history.load_history(controller.URL_HISTORY_CATEGORY, controller.DEFAULT_URL)
    url_var = tb.StringVar(value=urls[0] if urls else controller.DEFAULT_URL)
    tb.Combobox(card1, textvariable=url_var, values=urls, width=56, bootstyle="light").grid(row=2, column=1, sticky=EW, pady=(10,2))

    btn_save_session = tb.Button(
        card1,
        text="Actualizar sesión",
        bootstyle=SUCCESS,
        command=_save_loaded_session_changes,
        state="disabled",
    )
    btn_save_session.grid(row=4, column=1, sticky=E, pady=(12, 0))
    
    card2 = tb.Labelframe(parent, text="Salidas", bootstyle=SECONDARY, padding=12)
    card2.pack(fill=X, pady=(0,12)); card2.columnconfigure(1, weight=1)
    
    tb.Label(card2, text="Documento (DOCX)").grid(row=0, column=0, sticky=W)
    doc_var = tb.StringVar(); tb.Entry(card2, textvariable=doc_var).grid(row=0, column=1, sticky=EW, padx=(10,0) , pady=(2,2))
    
    tb.Label(card2, text="Carpeta evidencias").grid(row=1, column=0, sticky=W, pady=(6,0))
    ev_var = tb.StringVar(); tb.Entry(card2, textvariable=ev_var).grid(row=1, column=1, sticky=EW, padx=(10,0) , pady=(2,2))
    
    sessions_dir = controller.sessions.getSessionsDirectory()
    evidence_dir = controller.sessions.getEvidenceDirectory()

    style = tb.Style()
    style.configure(
        "CartoonAccent.TButton",
        font=("Segoe UI", 11, "bold"),
        foreground="#ffffff",
        background="#6C63FF",
        padding=(18, 10),
        borderwidth=0,
    )
    style.map(
        "CartoonAccent.TButton",
        background=[
            ("active", "#867DFF"),
            ("pressed", "#5548d9"),
            ("disabled", "#B8B3FF"),
        ],
        foreground=[("disabled", "#E9E7FF")],
    )
    style.configure(
        "CartoonAccentSlim.TButton",
        font=("Segoe UI", 10, "bold"),
        foreground="#ffffff",
        background="#6C63FF",
        padding=(12, 6),
        borderwidth=0,
    )
    style.map(
        "CartoonAccentSlim.TButton",
        background=[
            ("active", "#867DFF"),
            ("pressed", "#5548d9"),
            ("disabled", "#B8B3FF"),
        ],
        foreground=[("disabled", "#E9E7FF")],
    )
    style.configure(
        "CartoonGhost.TButton",
        font=("Segoe UI", 11, "bold"),
        foreground="#414561",
        background="#FFFFFF",
        bordercolor="#FFC542",
        focusthickness=3,
        focuscolor="#FFC542",
        padding=(18, 10),
    )
    style.map(
        "CartoonGhost.TButton",
        background=[("active", "#FFF4CC"), ("pressed", "#FFE08A")],
        foreground=[("active", "#2b2f4c"), ("pressed", "#1f2238")],
    )

    cards_controller = getattr(controller, "cardsAI", None)

    dashboard_header = tb.Frame(dashboard_tab)
    dashboard_header.pack(fill=X, pady=(0, 16))
    tb.Label(
        dashboard_header,
        text="Tarjetas disponibles",
        font=("Segoe UI", 16, "bold"),
    ).pack(side=LEFT)

    def _get_current_username() -> str:
        """Return the username of the authenticated operator."""

        return controller.auth.get_authenticated_username().strip()

    def _prepare_new_session_form() -> None:
        """Reset the inputs before creating a new session."""

        try:
            base_var.set("reporte")
        except Exception:
            pass
        default_url = controller.DEFAULT_URL
        urls = controller.history.load_history(controller.URL_HISTORY_CATEGORY, default_url)
        try:
            url_var.set(urls[0] if urls else default_url)
        except Exception:
            pass
        refresh_paths()
        session["cardId"] = None
        session["ticketId"] = None
        status.set("🆕 Prepara una nueva sesión de evidencias.")

    def _open_new_session_tab() -> None:
        """Navigate to the evidence tab to start a new session."""

        _prepare_new_session_form()
        notebook.select(session_tab)

    tb.Button(
        dashboard_header,
        text="🔄 Actualizar",
        style="CartoonGhost.TButton",
        command=lambda: _refresh_cards_table(),
        compound=LEFT,
    ).pack(side=RIGHT)
    tb.Button(
        dashboard_header,
        text="✨ Sesión manual",
        style="CartoonAccent.TButton",
        command=_open_new_session_tab,
        compound=LEFT,
    ).pack(side=RIGHT, padx=(0, 8))

    filters_frame = tb.Frame(dashboard_tab, padding=(0, 0, 0, 12))
    filters_frame.pack(fill=X)

    incident_type_options = []
    if cards_controller:
        try:
            incident_type_options = cards_controller.list_incidence_types()
        except RuntimeError as exc:
            Messagebox.showwarning("Tarjetas", f"No fue posible cargar los tipos de incidente\n{exc}")
            incident_type_options = []
    status_options = []
    if cards_controller:
        try:
            status_options = cards_controller.list_statuses()
        except RuntimeError as exc:
            Messagebox.showwarning("Tarjetas", f"No fue posible cargar los estatus\n{exc}")
            status_options = []
    company_options = []
    if cards_controller:
        try:
            company_options = cards_controller.list_companies()
        except RuntimeError as exc:
            Messagebox.showwarning("Tarjetas", f"No fue posible cargar las empresas\n{exc}")
            company_options = []

    incident_type_map = {option.name: option.optionId for option in incident_type_options}
    incident_type_values = [""] + [option.name for option in incident_type_options]
    status_values = [""] + status_options
    company_map = {option.name: option.optionId for option in company_options}
    company_values = [""] + [option.name for option in company_options]

    tb.Label(filters_frame, text="Tipo incidente").grid(row=0, column=0, sticky="w")
    tipo_var = tk.StringVar(value="")
    tipo_box = ttk.Combobox(
        filters_frame,
        values=incident_type_values,
        textvariable=tipo_var,
        width=18,
        state="readonly",
    )
    tipo_box.grid(row=1, column=0, sticky="we", padx=(0, 10))
    if incident_type_values:
        tipo_box.current(0)

    tb.Label(filters_frame, text="Status").grid(row=0, column=1, sticky="w")
    status_var = tk.StringVar(value="")
    status_box = ttk.Combobox(
        filters_frame,
        values=status_values,
        textvariable=status_var,
        width=16,
        state="readonly",
    )
    status_box.grid(row=1, column=1, sticky="we", padx=(0, 10))
    if status_values:
        status_box.current(0)

    tb.Label(filters_frame, text="Empresa").grid(row=0, column=2, sticky="w")
    company_var = tk.StringVar(value="")
    company_box = ttk.Combobox(
        filters_frame,
        values=company_values,
        textvariable=company_var,
        width=22,
        state="readonly",
    )
    company_box.grid(row=1, column=2, sticky="we", padx=(0, 10))
    if company_values:
        company_box.current(0)

    tb.Label(filters_frame, text="Fecha inicio").grid(row=0, column=3, sticky="w")
    start_var = DateEntry(filters_frame, dateformat="%Y-%m-%d")
    start_var.grid(row=1, column=3, sticky="we", padx=(0, 10))
    start_var.entry.delete(0, tk.END)

    tb.Label(filters_frame, text="Fecha fin").grid(row=0, column=4, sticky="w")
    end_var = DateEntry(filters_frame, dateformat="%Y-%m-%d")
    end_var.grid(row=1, column=4, sticky="we", padx=(0, 10))
    end_var.entry.delete(0, tk.END)

    tb.Label(filters_frame, text="Buscar").grid(row=0, column=5, sticky="w")
    search_var = tk.StringVar(value="")
    search_entry = tb.Entry(filters_frame, textvariable=search_var)
    search_entry.grid(row=1, column=5, sticky="we")

    filters_frame.grid_columnconfigure(5, weight=1)

    tests_filter_var = tk.StringVar(value="Todas")

    table_frame = tb.Frame(dashboard_tab, padding=(0, 0, 0, 12))
    table_frame.pack(fill=BOTH, expand=YES)

    columns_config: Dict[str, Dict[str, object]] = {
        "ticket": {"text": "Ticket", "width": 110, "anchor": "center"},
        "titulo": {"text": "Titulo", "width": 360, "stretch": True},
        "tipo": {"text": "Tipo incidente", "width": 180},
        "status": {"text": "Status", "width": 140},
        "empresa": {"text": "Empresa", "width": 200},
        "actualizado": {"text": "Actualizado", "width": 160, "anchor": "center"},
        "pruebas": {"text": "Pruebas generadas", "width": 160, "anchor": "center"},
    }
    columns = tuple(columns_config.keys())
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
    tree["displaycolumns"] = columns

    active_sort: Dict[str, Optional[str]] = {"column": None, "direction": None}
    column_vars: Dict[str, tk.BooleanVar] = {}
    selected_card: List[CardDTO] = []
    current_cards: List[CardDTO] = []
    generate_tests_button: Optional[tb.Button] = None
    cards_status_label: Optional[tb.Label] = None
    debounce_id: Optional[str] = None

    for column_name, column_config in columns_config.items():
        tree.heading(column_name, text=column_config["text"], command=lambda col=column_name: _sort_cards_tree(col))
        tree.column(
            column_name,
            width=int(column_config.get("width", 120)),
            anchor=column_config.get("anchor", tk.W),
            stretch=bool(column_config.get("stretch", False)),
        )
    tree.tag_configure("pruebas", background="#e6f4ea")

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=YES)
    scrollbar.pack(side=RIGHT, fill=Y)
    bind_mousewheel(tree, tree.yview)

    def _coerce_sort_value(value: str, column: str) -> object:
        """Return a comparable value for sorting operations."""

        if column == "actualizado" and value:
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M")
            except ValueError:
                return value
        if column == "ticket":
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        normalized = str(value).strip().lower()
        if normalized in {"si", "no"}:
            return 1 if normalized == "si" else 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return normalized

    def _sort_cards_tree(column: str, force_direction: Optional[str] = None) -> None:
        """Sort the tree rows using the provided column."""

        direction = force_direction
        if direction is None:
            if active_sort["column"] == column and active_sort["direction"] == "asc":
                direction = "desc"
            else:
                direction = "asc"
        active_sort["column"] = column
        active_sort["direction"] = direction
        items = [(tree.set(item_id, column), item_id) for item_id in tree.get_children("")]
        reverse = direction == "desc"
        try:
            items.sort(key=lambda item: _coerce_sort_value(item[0], column), reverse=reverse)
        except TypeError:
            items.sort(key=lambda item: str(item[0]).lower(), reverse=reverse)
        for index, (_, item_id) in enumerate(items):
            tree.move(item_id, "", index)

    def _parse_date(entry: DateEntry) -> Optional[datetime]:
        """Return the selected date or `None` when the field is empty."""

        value = entry.entry.get().strip()
        if not value:
            return None
        try:
            return datetime.strptime(value + " 00:00", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def _refresh_cards_table() -> None:
        """Load the cards from the controller applying filters."""

        if cards_controller is None:
            if cards_status_label is not None:
                cards_status_label.configure(text="Controlador de tarjetas no disponible.")
            status.set("⚠️ No fue posible acceder al listado de tarjetas.")
            return

        selected_type = tipo_var.get().strip()
        selected_status = status_var.get().strip()
        selected_company = company_var.get().strip()
        filters: Dict[str, object] = {
            "fechaInicio": _parse_date(start_var),
            "fechaFin": _parse_date(end_var),
            "busqueda": search_var.get().strip() or None,
        }
        tests_filter_value = tests_filter_var.get().strip().lower()
        if tests_filter_value and tests_filter_value != "todas":
            filters["estadoPruebas"] = tests_filter_var.get()
        if selected_type:
            filters["tipoId"] = incident_type_map.get(selected_type)
        if selected_status:
            filters["status"] = selected_status
        if selected_company:
            filters["empresaId"] = company_map.get(selected_company)
        try:
            cards = cards_controller.list_cards(filters)
        except RuntimeError as exc:
            Messagebox.showerror("Tarjetas", str(exc))
            return

        current_cards[:] = cards
        selected_card.clear()
        tree.delete(*tree.get_children(""))

        for card in cards:
            tags_list: List[str] = []
            if card.hasTestsGenerated:
                tags_list.append("pruebas")
            formatted_date = _format_card_datetime(card.updatedAt or card.createdAt)
            tree.insert(
                "",
                "end",
                iid=str(card.cardId),
                values=(
                    card.ticketId or str(card.cardId),
                    card.title,
                    card.incidentTypeName or "",
                    card.status,
                    card.companyName or "",
                    formatted_date,
                    "Si" if card.hasTestsGenerated else "No",
                ),
                tags=tuple(tags_list),
            )
        if active_sort["column"] and active_sort["direction"]:
            _sort_cards_tree(active_sort["column"], force_direction=active_sort["direction"])
        if generate_tests_button is not None:
            generate_tests_button.configure(state=tk.DISABLED)
        if cards_status_label is not None:
            cards_status_label.configure(text=f"{len(cards)} tarjeta(s) encontradas.")
        status.set(f"🗂️ {len(cards)} tarjeta(s) encontradas.")

    def _on_card_select(_event: tk.Event) -> None:
        """Enable actions when a card row is selected."""

        selection = tree.selection()
        if not selection:
            selected_card.clear()
            if generate_tests_button is not None:
                generate_tests_button.configure(state=tk.DISABLED)
            return
        try:
            card_id = int(selection[0])
        except ValueError:
            selected_card.clear()
            if generate_tests_button is not None:
                generate_tests_button.configure(state=tk.DISABLED)
            return
        for card in current_cards:
            if card.cardId == card_id:
                selected_card[:] = [card]
                break
        state = tk.NORMAL if selected_card else tk.DISABLED
        if generate_tests_button is not None:
            generate_tests_button.configure(state=state)

    def _toggle_column(column: str) -> None:
        """Hide or show the requested column ensuring at least one stays visible."""

        visible_columns = [name for name in columns if column_vars[name].get()]
        if not visible_columns:
            column_vars[column].set(True)
            Messagebox.showinfo("Columnas", "Debe permanecer al menos una columna visible.")
            return
        tree["displaycolumns"] = visible_columns

    def _schedule_cards_refresh(*_args: object) -> None:
        """Apply debounce to the search entry."""

        nonlocal debounce_id
        if debounce_id is not None:
            dashboard_tab.after_cancel(debounce_id)
        debounce_id = dashboard_tab.after(300, _refresh_cards_table)

    def _prepare_card_session() -> None:
        """Prepare the evidence session inputs based on the selected card."""

        if not selected_card:
            Messagebox.showwarning("Tarjetas", "Selecciona una tarjeta para continuar.")
            return
        card = selected_card[0]
        existing_session, lookup_error = controller.sessions.find_session_by_card(card.cardId)
        if lookup_error:
            Messagebox.showerror("Sesión", lookup_error)
            return
        if existing_session:
            status.set(f"ℹ️ Reutilizando la sesión existente para {card.ticketId or card.cardId}.")
            _open_session_editor(existing_session)
            return
        if session_state["active"]:
            Messagebox.showwarning("Sesión", "Termina la sesión activa antes de iniciar otra.")
            return
        ticket_slug = controller.naming.slugify_for_windows(card.ticketId or "")
        fallback_slug = controller.naming.slugify_for_windows(f"card-{card.cardId}")
        card_base = ticket_slug or fallback_slug or f"card-{card.cardId}"
        previous_auto_state = auto_paths_state.get("enabled", True)
        auto_paths_state["enabled"] = True
        try:
            base_var.set(card_base)
        finally:
            auto_paths_state["enabled"] = previous_auto_state
        prev_base["val"] = controller.naming.slugify_for_windows(base_var.get() or card_base)
        session["title"] = card.title or session.get("title", "Incidencia")
        session["cardId"] = card.cardId
        session["ticketId"] = card.ticketId
        session_saved["val"] = False
        status.set(f"🧪 Preparando sesión para la tarjeta {card.ticketId or card.cardId}.")
        if cards_status_label is not None:
            cards_status_label.configure(text=f"Tarjeta seleccionada: {card.ticketId or card.cardId}")
        notebook.select(session_tab)
        notebook.focus_set()
        if Messagebox.askyesno("Sesión", f"¿Deseas iniciar una sesión de evidencias para '{card.title}' ahora?"):
            start_evidence_session()

    actions_frame = tb.Frame(dashboard_tab, padding=(0, 12, 0, 0))
    actions_frame.pack(fill=X)
    cards_status_label = tb.Label(actions_frame, text="Selecciona una tarjeta para comenzar.", bootstyle=SECONDARY)
    cards_status_label.pack(side=LEFT)

    column_button = ttk.Menubutton(actions_frame, text="Columnas")
    column_menu = tk.Menu(column_button, tearoff=False)
    column_button["menu"] = column_menu
    for column_name, column_config in columns_config.items():
        var = tk.BooleanVar(value=True)
        column_vars[column_name] = var
        column_menu.add_checkbutton(
            label=column_config["text"],
            variable=var,
            command=lambda col=column_name: _toggle_column(col),
        )

    generate_tests_button = tb.Button(
        actions_frame,
        text="Generar pruebas",
        bootstyle=PRIMARY,
        state=tk.DISABLED,
        command=_prepare_card_session,
    )
    generate_tests_button.pack(side=RIGHT)
    column_button.pack(side=RIGHT, padx=(0, 6))

    tree.bind("<<TreeviewSelect>>", _on_card_select)

    for widget in (tipo_box, status_box, company_box):
        widget.bind("<<ComboboxSelected>>", lambda *_: _refresh_cards_table(), add="+")
    start_var.bind("<<DateEntrySelected>>", lambda *_: _refresh_cards_table(), add="+")
    end_var.bind("<<DateEntrySelected>>", lambda *_: _refresh_cards_table(), add="+")
    search_var.trace_add("write", lambda *_: _schedule_cards_refresh())

    tb.Label(filters_frame, text="Pruebas generadas").grid(row=2, column=0, sticky="w", pady=(8, 0))
    tests_filter_box = ttk.Combobox(
        filters_frame,
        values=("Todas", "Con pruebas generadas", "Sin pruebas generadas"),
        textvariable=tests_filter_var,
        state="readonly",
        width=22,
    )
    tests_filter_box.grid(row=3, column=0, sticky="we", padx=(0, 10))
    tests_filter_box.current(0)

    tests_filter_box.bind("<<ComboboxSelected>>", lambda *_: _refresh_cards_table(), add="+")
    _refresh_cards_table()

    def _map_evidence_to_step(evidence: SessionEvidenceDTO) -> Dict[str, object]:
        """Translate a persisted evidence to the in-memory representation."""

        shots: List[str] = []
        for asset in sorted(evidence.assets or [], key=lambda item: item.position):
            if asset.filePath:
                shots.append(asset.filePath)
        if evidence.filePath:
            if not shots:
                shots.append(evidence.filePath)
            elif evidence.filePath not in shots:
                shots.insert(0, evidence.filePath)
        return {
            "id": evidence.evidenceId,
            "cmd": evidence.fileName or "Evidencia",
            "shots": shots,
            "desc": evidence.description or "",
            "consideraciones": evidence.considerations or "",
            "observacion": evidence.observations or "",
            "createdAt": evidence.createdAt,
            "elapsedSinceStart": evidence.elapsedSinceSessionStartSeconds,
            "elapsedSincePrevious": evidence.elapsedSincePreviousEvidenceSeconds,
        }

    def _populate_session_from_evidences(evidences: List[SessionEvidenceDTO]) -> None:
        """Replace the in-memory steps with evidences pulled from storage."""

        session["steps"].clear()
        for evidence in evidences:
            session["steps"].append(_map_evidence_to_step(evidence))
        _refresh_evidence_tree()

    def _clear_dashboard_edit_mode() -> None:
        """Disable dashboard-specific editing controls and reset labels."""

        if not dashboard_edit_state.get("sessionId"):
            return
        dashboard_edit_state["sessionId"] = None
        session["cardId"] = None
        session["ticketId"] = None
        try:
            controller.sessions.clear_active_session()
        except Exception:
            pass
        try:
            btn_save_session.configure(state="disabled")
        except Exception:
            pass
        try:
            btn_session_start.configure(text="Iniciar sesión")
        except Exception:
            pass

    def _open_session_editor(session_obj: SessionDTO) -> None:
        """Load the session into the evidence tab for inline editing."""

        current_username = _get_current_username()
        if not current_username or session_obj.username.lower() != current_username.lower():
            Messagebox.showwarning("Sesión", "Solo el usuario que creó la sesión puede editarla.")
            return

        if _is_dashboard_editing():
            _clear_dashboard_edit_mode()

        session_payload, evidences, error = controller.sessions.activate_session_for_dashboard_edit(session_obj.sessionId or 0)
        if error:
            Messagebox.showerror("Sesión", error)
            return

        loaded_session = session_payload or session_obj
        dashboard_edit_state["sessionId"] = loaded_session.sessionId

        auto_paths_state["enabled"] = False
        try:
            base_var.set(loaded_session.name or "")
            url_var.set(loaded_session.initialUrl or "")
            doc_var.set(loaded_session.docxUrl or "")
            ev_var.set(loaded_session.evidencesUrl or "")
        finally:
            auto_paths_state["enabled"] = True

        prev_base["val"] = controller.naming.slugify_for_windows(base_var.get() or "reporte")
        session["title"] = loaded_session.name or ""
        session["sessionId"] = loaded_session.sessionId
        session["cardId"] = loaded_session.cardId
        _populate_session_from_evidences(evidences)
        session_saved["val"] = True

        _cancel_timer()
        session_state.update({"active": True, "paused": True, "timerJob": None})
        timer_var.set(format_elapsed(loaded_session.durationSeconds or 0))

        try:
            btn_session_start.configure(state="disabled", text="Sesión cargada")
            btn_session_pause.configure(state="disabled", text="Pausar sesión")
            btn_session_finish.configure(state="disabled")
            btn_save_session.configure(state="normal")
        except Exception:
            pass

        status.set(f"✏️ Editando la sesión '{loaded_session.name}'.")
        notebook.select(session_tab)
        notebook.focus_set()

    def _confirm_delete_session(session_obj) -> None:
        """Ask for confirmation before removing the session."""

        current_username = _get_current_username()
        if not current_username or session_obj.username.lower() != current_username.lower():
            Messagebox.showwarning("Sesión", "Solo el usuario que creó la sesión puede eliminarla.")
            return
        if not Messagebox.askyesno("Sesión", f"¿Eliminar la sesión '{session_obj.name}'? Esta acción no se puede deshacer."):
            return
        error = controller.sessions.delete_session(session_obj.sessionId or 0)
        if error:
            Messagebox.showerror("Sesión", error)
            return
        status.set("🗑️ Sesión eliminada.")
        _refresh_cards_table()

    def _handle_download(session_obj) -> None:
        """Placeholder action for the future download workflow."""

        Messagebox.showinfo(
            "Descarga",
            "La descarga de sesiones estará disponible próximamente.",
        )

    _refresh_cards_table()

    auto_paths_state = {"enabled": True}

    def refresh_paths(*_args: object) -> None:
        """Compute default output locations when the base name changes."""

        if not auto_paths_state.get("enabled", True):
            return
        base = controller.naming.slugify_for_windows(base_var.get() or "reporte")
        final = f"{base}"
        doc_var.set(str(sessions_dir / f"{final}.docx"))
        ev_var.set(str(evidence_dir / final))

    base_var.trace_add("write", refresh_paths)
    refresh_paths()

    prev_base = {"val": controller.naming.slugify_for_windows(base_var.get() or "reporte")}

    def _on_base_change(*_args: object) -> None:
        """Synchronize caches and optionally clear history when the base changes."""

        new_base = controller.naming.slugify_for_windows(base_var.get() or "reporte")
        old_base = prev_base["val"]
        if not old_base or new_base == old_base:
            return
        if not auto_paths_state.get("enabled", True):
            prev_base["val"] = new_base
            return
        ev_old = evidence_dir / old_base
        has_hist = bool(session.get("steps")) if isinstance(session, dict) else False
        has_old_dir = ev_old.exists()
        if has_hist or has_old_dir:
            if Messagebox.askyesno(
                "Cambio de nombre",
                f"Se cambió el nombre base de '{old_base}' a '{new_base}'. ¿Limpiar historial en la GUI? (Las evidencias en disco no se tocan)",
            ):
                _clear_evidence_for(old_base, also_clear_session=True)
                status.set(f"🧹 Historial limpiado. Evidencias en disco conservadas para: {old_base}")
            prev_base["val"] = new_base
    
    base_var.trace_add("write", _on_base_change)
    
    status_bar = tb.Label(root, textvariable=status, bootstyle=INFO, anchor=W, padding=(16,6)); status_bar.pack(fill=X)
    
    session_saved = {"val": False}
    
    session = {"title": "Incidencia", "steps": [], "sessionId": None, "cardId": None, "ticketId": None}
    session_state = {"active": False, "paused": False, "timerJob": None}
    timer_var = tk.StringVar(value=format_elapsed(0))
    evidence_tree_ref: dict[str, Optional[ttk.Treeview]] = {"tree": None}
    _monitor_index = {"val": None}
    
    def _cancel_timer() -> None:
        """Stop the scheduled timer update if present."""
    
        job = session_state.get("timerJob")
        if job is None:
            return
        try:
            root.after_cancel(job)
        except Exception:
            pass
        session_state["timerJob"] = None
    
    def _refresh_timer_label() -> None:
        """Update the timer label based on the service value."""
    
        timer_var.set(format_elapsed(controller.sessions.get_session_elapsed_seconds()))
    
    def _schedule_timer_tick() -> None:
        """Reschedule the timer update when the session is running."""
    
        _cancel_timer()
        _refresh_timer_label()
        if session_state["active"] and not session_state["paused"]:
            session_state["timerJob"] = root.after(1000, _schedule_timer_tick)
    
    def _refresh_evidence_tree() -> None:
        """Render the evidence rows in the treeview widget."""

        tree = evidence_tree_ref.get("tree")
        if not isinstance(tree, ttk.Treeview):
            return
        tree.delete(*tree.get_children())
        for idx, step in enumerate(session.get("steps", []), start=1):
            shots = step.get("shots") or [""]
            primary_shot = shots[0] if shots else ""
            values = (
                idx,
                step.get("cmd", ""),
                os.path.basename(primary_shot) if primary_shot else "",
                step.get("desc", ""),
                format_timestamp(step.get("createdAt")),
                format_elapsed(step.get("elapsedSincePrevious")),
            )
            tree.insert("", "end", iid=str(idx - 1), values=values)

    def _get_selected_step_index(show_warning: bool = True) -> Optional[int]:
        """Return the index of the evidence currently selected in the grid."""

        tree = evidence_tree_ref.get("tree")
        if not isinstance(tree, ttk.Treeview):
            return None
        selection = tree.selection()
        if not selection:
            if show_warning:
                Messagebox.showwarning("Evidencias", "Selecciona una evidencia para continuar.")
            return None
        try:
            index = int(selection[0])
        except ValueError:
            if show_warning:
                Messagebox.showwarning("Evidencias", "La evidencia seleccionada no es válida.")
            return None
        steps = session.get("steps", [])
        if index < 0 or index >= len(steps):
            if show_warning:
                Messagebox.showwarning("Evidencias", "No se encontró la evidencia seleccionada.")
            return None
        return index
    
    def _ensure_session_active(show_warning: bool = True) -> bool:
        """Check that a session is active and optionally show a warning."""
    
        if session_state["active"]:
            return True
        if show_warning:
            Messagebox.showwarning("Sesión", "Inicia una sesión de evidencias antes de continuar.")
        return False
    
    def _ensure_session_running() -> bool:
        """Verify that the session is active and not paused."""
    
        if not _ensure_session_active(True):
            return False
        if session_state["paused"]:
            Messagebox.showwarning("Sesión", "Reanuda la sesión para continuar capturando evidencias.")
            return False
        return True
    
    def _update_session_outputs(*_args: object) -> None:
        """Propagate the current output paths to the controller."""
    
        if not session_state["active"]:
            return
        error = controller.sessions.update_active_session_outputs(doc_var.get(), ev_var.get())
        if error:
            status.set(f"⚠️ {error}")
    
    doc_var.trace_add("write", _update_session_outputs)
    ev_var.trace_add("write", _update_session_outputs)
    
    def _show_elapsed_message() -> None:
        """Display the elapsed time in a dialog."""
    
        _refresh_timer_label()
        Messagebox.showinfo("Sesión", f"Tiempo transcurrido: {format_elapsed(controller.sessions.get_session_elapsed_seconds())}")
    
    def start_evidence_session() -> None:
        """Start a new evidence session and reset the UI state."""

        if _is_dashboard_editing():
            if not Messagebox.askyesno(
                "Sesión",
                "Se descartará la edición de la sesión cargada desde el tablero. ¿Continuar?",
            ):
                return
            _clear_dashboard_edit_mode()
            _cancel_timer()
            session_state.update({"active": False, "paused": False, "timerJob": None})
            session["steps"].clear()
            session_saved["val"] = False
            _refresh_evidence_tree()
            timer_var.set(format_elapsed(0))
        if session_state["active"]:
            Messagebox.showwarning("Sesión", "Ya hay una sesión activa en curso.")
            return

        base_name = controller.naming.slugify_for_windows(base_var.get() or "reporte") or "reporte"
        session_title = (base_var.get() or "Incidencia").strip() or base_name
        session["title"] = session_title
    
        doc_path = Path(doc_var.get())
        evidence_path = Path(ev_var.get())
        try:
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            Messagebox.showerror("Sesión", f"No fue posible preparar las carpetas de salida: {exc}")
            return
    
        session_obj, error = controller.sessions.begin_evidence_session(
            session_title,
            (url_var.get() or controller.DEFAULT_URL).strip() or controller.DEFAULT_URL,
            str(doc_path),
            str(evidence_path),
            session.get("cardId"),
        )
        if error:
            Messagebox.showerror("Sesión", error)
            return
    
        session_state.update({"active": True, "paused": False, "timerJob": None})
        session["sessionId"] = session_obj.sessionId if session_obj else None
        session["steps"].clear()
        session_saved["val"] = False
        _refresh_evidence_tree()
        _schedule_timer_tick()
        status.set("⏱️ Sesión iniciada.")
        _update_session_outputs()
        try:
            btn_session_start.configure(state="disabled")
            btn_session_pause.configure(state="normal", text="Pausar sesión")
            btn_session_finish.configure(state="normal")
        except Exception:
            pass
    
    def pause_or_resume_session() -> None:
        """Toggle the pause state for the active session."""
    
        if not _ensure_session_active(True):
            return
        if session_state["paused"]:
            error = controller.sessions.resume_evidence_session()
            if error:
                Messagebox.showerror("Sesión", error)
                return
            session_state["paused"] = False
            status.set("▶️ Sesión reanudada.")
            btn_session_pause.configure(text="Pausar sesión")
            _schedule_timer_tick()
            return
    
        error = controller.sessions.pause_evidence_session()
        if error:
            Messagebox.showerror("Sesión", error)
            return
        session_state["paused"] = True
        status.set("⏸️ Sesión en pausa.")
        _cancel_timer()
        _refresh_timer_label()
        btn_session_pause.configure(text="Reanudar sesión")
    
    def finish_evidence_session() -> None:
        """Finalize the active session and reset controls."""
    
        if not session_state["active"]:
            Messagebox.showwarning("Sesión", "No hay una sesión activa.")
            return
        if session_state["paused"]:
            Messagebox.showwarning("Sesión", "Reanuda la sesión antes de finalizarla.")
            return
        if not Messagebox.askyesno("Sesión", "¿Deseas finalizar la sesión actual?"):
            return
    
        session_obj, error = controller.sessions.finalize_evidence_session()
        if error:
            Messagebox.showerror("Sesión", error)
            return
    
        session_state.update({"active": False, "paused": False, "timerJob": None})
        _cancel_timer()
        final_elapsed = session_obj.durationSeconds if session_obj else controller.sessions.get_session_elapsed_seconds()
        timer_var.set(format_elapsed(final_elapsed))
        status.set("✅ Sesión finalizada.")
        try:
            btn_session_start.configure(state="normal")
            btn_session_pause.configure(state="disabled", text="Pausar sesión")
            btn_session_finish.configure(state="disabled")
        except Exception:
            pass
    
    def edit_selected_evidence() -> None:
        """Open the evidence details modal for the selected row."""

        if not _ensure_session_active(True):
            return
        index = _get_selected_step_index(True)
        if index is None:
            return
        _open_evidence_details_modal(index)

    session_card = tb.Labelframe(parent, text="Sesión de evidencias", bootstyle=SECONDARY, padding=12)
    session_card.pack(fill=BOTH, expand=YES, pady=(0,12))
    session_card.columnconfigure(0, weight=1)
    
    timer_row = tb.Frame(session_card)
    timer_row.pack(fill=X, pady=(0,10))
    tb.Label(timer_row, text="Tiempo transcurrido:", font=("Segoe UI", 11, "bold")).pack(side=LEFT)
    tb.Label(timer_row, textvariable=timer_var, font=("Consolas", 16, "bold"), bootstyle=SUCCESS).pack(side=LEFT, padx=(12, 0))
    tb.Button(timer_row, text="🕒 Mostrar tiempo", command=_show_elapsed_message, bootstyle=SECONDARY).pack(side=LEFT, padx=10)
    btn_session_finish = tb.Button(timer_row, text="Finalizar sesión", command=finish_evidence_session, bootstyle=DANGER, state="disabled")
    btn_session_finish.pack(side=RIGHT, padx=(0, 0))
    btn_session_pause = tb.Button(timer_row, text="Pausar sesión", command=pause_or_resume_session, bootstyle=WARNING, state="disabled")
    btn_session_pause.pack(side=RIGHT, padx=10)
    btn_session_start = tb.Button(timer_row, text="Iniciar sesión", command=start_evidence_session, bootstyle=SUCCESS)
    btn_session_start.pack(side=RIGHT, padx=10)
    
    evidence_frame = tb.Frame(session_card)
    evidence_frame.pack(fill=BOTH, expand=YES)
    columns = ("#", "Tipo", "Archivo", "Descripción", "Creado", "Δ desde anterior")
    evidence_tree = ttk.Treeview(evidence_frame, columns=columns, show="headings", height=8)
    for col, heading in zip(columns, ("#", "Tipo", "Archivo", "Descripción", "Creado", "Δ desde anterior")):
        evidence_tree.heading(col, text=heading)
    evidence_tree.column("#", width=50, anchor="center")
    evidence_tree.column("Tipo", width=120, anchor="w")
    evidence_tree.column("Archivo", width=220, anchor="w")
    evidence_tree.column("Descripción", width=280, anchor="w")
    evidence_tree.column("Creado", width=160, anchor="center")
    evidence_tree.column("Δ desde anterior", width=140, anchor="center")
    vsb_evidence = ttk.Scrollbar(evidence_frame, orient="vertical", command=evidence_tree.yview)
    evidence_tree.configure(yscrollcommand=vsb_evidence.set)
    evidence_tree.pack(side=LEFT, fill=BOTH, expand=YES)
    vsb_evidence.pack(side=RIGHT, fill=Y)
    evidence_tree.bind("<Double-1>", lambda _event: edit_selected_evidence())
    bind_mousewheel(evidence_tree, evidence_tree.yview)
    evidence_tree_ref["tree"] = evidence_tree
    _refresh_evidence_tree()
    
    evidence_actions = tb.Frame(session_card)
    evidence_actions.pack(fill=X, pady=(8,0))
    tb.Button(evidence_actions, text="Editar evidencia", command=edit_selected_evidence, bootstyle=PRIMARY).pack(side=LEFT)
    
    def ensure_mss():
        """Auto-generated docstring for `ensure_mss`."""
        try:
            import mss, mss.tools
            return True
        except Exception:
            Messagebox.showerror( "SNAP","Falta el paquete 'mss'. Instala:\n\npip install mss")
            return False
    
    def select_monitor_modal(master, monitors):
        """Auto-generated docstring for `select_monitor_modal`."""
        win = tb.Toplevel(master); win.title("Seleccionar monitor"); win.transient(master); win.grab_set()
        frm = tb.Frame(win, padding=15); frm.pack(fill=BOTH, expand=YES)
        tb.Label(frm, text="Elige el monitor", font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0,8))
        options = []
        for idx, mon in enumerate(monitors, start=0):
            if idx == 0: label = f"Todos (desktop completo)  {mon.get('width','?')}x{mon.get('height','?')}"
            else: label = f"Monitor {idx}  ({mon.get('left','?')},{mon.get('top','?')})  {mon.get('width','?')}x{mon.get('height','?')}"
            options.append(label)
        sel = tb.Combobox(frm, values=options, state="readonly", width=60); sel.pack(fill=X); sel.current(1 if len(monitors) > 1 else 0)
        res = {"index": sel.current()}
        btns = tb.Frame(frm); btns.pack(fill=X, pady=(10,0))
        def ok():
            """Auto-generated docstring for `ok`."""
            res["index"] = sel.current(); win.destroy()
        def cancel():
            """Auto-generated docstring for `cancel`."""
            res["index"] = None; win.destroy()
        tb.Button(btns, text="Cancelar", command=cancel, bootstyle=SECONDARY).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Aceptar", command=ok, bootstyle=PRIMARY).pack(side=RIGHT)
        win.wait_window(); return res["index"]
    
    def select_monitor(sct):
        """Auto-generated docstring for `select_monitor`."""
        monitors = sct.monitors
        if not monitors:
            Messagebox.showerror("SNAP","No se detectaron monitores."); return None, None
        idx = _monitor_index["val"]
        if ask_always.get() or idx is None or idx >= len(monitors) or idx < 0:
            sel = select_monitor_modal(root, monitors)
            if sel is None: return None, None
            idx = sel; _monitor_index["val"] = idx
        return monitors, idx
    
    def _persist_capture_result(
        out_path: Path,
        meta_desc: Dict[str, str],
        cmd: str,
        status_new: str,
        status_extra: str,
        target_step_index: Optional[int] = None,
        inherit_primary_meta: bool = False,
    ) -> None:
        """Persist the capture either as a new evidence or as an attachment."""

        desc_val = (meta_desc.get("descripcion") or "").strip()
        cons_val = (meta_desc.get("consideraciones") or "").strip()
        obs_val = (meta_desc.get("observacion") or "").strip()
        shot_path = str(out_path)
        base_desc = desc_val
        base_cons = cons_val
        base_obs = obs_val

        if target_step_index is None:
            step: Dict[str, object] = {"cmd": cmd, "shots": [shot_path]}
            if desc_val:
                step["desc"] = desc_val
            if cons_val:
                step["consideraciones"] = cons_val
            if obs_val:
                step["observacion"] = obs_val
            session["steps"].append(step)
            evidence, error = controller.sessions.register_session_evidence(
                Path(step["shots"][0]),
                step.get("desc", ""),
                step.get("consideraciones", ""),
                step.get("observacion", ""),
            )
            if error:
                Messagebox.showerror("Sesión", error)
                session["steps"].pop()
                return
            if evidence:
                step["id"] = evidence.evidenceId
                step["createdAt"] = evidence.createdAt
                step["elapsedSinceStart"] = evidence.elapsedSinceSessionStartSeconds
                step["elapsedSincePrevious"] = evidence.elapsedSincePreviousEvidenceSeconds
            session_saved["val"] = False
            _refresh_evidence_tree()
            _schedule_timer_tick()
            status.set(status_new)
            return

        steps = session.get("steps", [])
        if target_step_index < 0 or target_step_index >= len(steps):
            Messagebox.showwarning("Evidencias", "No se encontró la evidencia seleccionada.")
            return
        step = steps[target_step_index]
        evidence_id = step.get("id")
        if not evidence_id:
            Messagebox.showwarning(
                "Evidencias",
            "La evidencia aún no se ha guardado en la sesión. Captura una nueva antes de adjuntar imágenes.",
            )
            return
        error = controller.sessions.add_evidence_shot(int(evidence_id), Path(shot_path))
        if error:
            Messagebox.showerror("Sesión", error)
            return
        shots_list = step.setdefault("shots", [])
        shots_list.append(shot_path)
        if inherit_primary_meta:
            desc_val = step.get("desc", "")
            cons_val = step.get("consideraciones", "")
            obs_val = step.get("observacion", "")
        else:
            step["desc"] = base_desc
            step["consideraciones"] = base_cons
            step["observacion"] = base_obs
        primary_path = shots_list[0] if shots_list else shot_path
        error = controller.sessions.update_session_evidence(
            int(evidence_id),
            Path(primary_path),
            step.get("desc", ""),
            step.get("consideraciones", ""),
            step.get("observacion", ""),
        )
        if error:
            Messagebox.showerror("Sesión", error)
            return
        session_saved["val"] = False
        _refresh_evidence_tree()
        _schedule_timer_tick()
        status.set(status_extra)

    def _open_capture_editor_for_shot(step_index: int, shot_index: int) -> None:
        """Open the editor for a specific capture and persist changes."""

        steps = session.get("steps", [])
        if step_index < 0 or step_index >= len(steps):
            Messagebox.showwarning("Evidencias", "No se encontró la evidencia solicitada.")
            return
        step = steps[step_index]
        shots = step.get("shots") or []
        if shot_index < 0 or shot_index >= len(shots):
            Messagebox.showwarning("Evidencias", "La captura seleccionada no es válida.")
            return
        if shot_index != 0:
            Messagebox.showinfo("Evidencias", "Por ahora solo se puede editar la captura principal.")
            return

        image_path = Path(shots[shot_index])
        meta_in = {
            "descripcion": step.get("desc", ""),
            "consideraciones": step.get("consideraciones", ""),
            "observaciones": step.get("observacion", ""),
        }
        try:
            edited_path, meta_out = open_capture_editor_fn(str(image_path), meta_in)
        except Exception as exc:
            Messagebox.showerror("Editor", f"No fue posible abrir el editor: {exc}")
            return

        new_path = Path(edited_path) if edited_path else image_path
        shots[shot_index] = str(new_path)
        step["desc"] = meta_out.get("descripcion", "") or ""
        step["consideraciones"] = meta_out.get("consideraciones", "") or ""
        step["observacion"] = meta_out.get("observaciones", "") or ""

        evidence_id = step.get("id")
        if evidence_id:
            error = controller.sessions.update_session_evidence(
                int(evidence_id),
                new_path,
                step.get("desc", ""),
                step.get("consideraciones", ""),
                step.get("observacion", ""),
            )
            if error:
                Messagebox.showerror("Sesión", error)
                return

        session_saved["val"] = False
        _refresh_evidence_tree()
        status.set("Evidencia actualizada.")

    def snap_externo_monitor(target_step_index: Optional[int] = None) -> None:
        """Capture the entire monitor or attach it to the selected evidence."""

        if not _ensure_session_running():
            return
        if not ensure_mss():
            return
        import mss, mss.tools

        with mss.mss() as sct:
            monitors, idx = select_monitor(sct)
            if monitors is None:
                return
            mon = monitors[idx]
            evid_dir = Path(ev_var.get())
            evid_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = evid_dir / f"snap_ext_monitor{idx}_{ts}.png"
            img = sct.grab(mon)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))

        meta_desc = {"descripcion": "", "consideraciones": "", "observacion": ""}
        try:
            meta_in = {
                "descripcion": meta_desc.get("descripcion", ""),
                "consideraciones": meta_desc.get("consideraciones", ""),
                "observaciones": meta_desc.get("observacion", ""),
            }
            edited_path, meta_out = open_capture_editor_fn(str(out_path), meta_in)
            if edited_path and os.path.exists(edited_path):
                out_path = Path(edited_path)
            meta_desc["descripcion"] = meta_out.get("descripcion", "")
            meta_desc["consideraciones"] = meta_out.get("consideraciones", "")
            meta_desc["observacion"] = meta_out.get("observaciones", "")
        except Exception as exc:
            Messagebox.showwarning("Editor", f"Editor no disponible: {exc}")

        _persist_capture_result(
            Path(out_path),
            meta_desc,
            "snap_externo",
            f"[SNAP] Captura externa guardada (monitor {idx}).",
            "[SNAP] Captura externa adicional agregada a la evidencia seleccionada.",
            target_step_index,
            inherit_primary_meta=bool(target_step_index is not None),
        )

    def snap_region_all(target_step_index: Optional[int] = None) -> None:
        """Capture a region of the desktop or attach it to an existing evidence."""
        if not _ensure_session_running():
            return
        if not ensure_mss():
            return
        import mss, mss.tools
        with mss.mss() as sct:
            desktop = sct.monitors[0]
            bbox = select_region_overlay(root, desktop)
            if not bbox:
                status.set("Seleccion cancelada.")
                return

            left, top, width, height = bbox
            region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
            evid_dir = Path(ev_var.get())
            evid_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = evid_dir / f"snap_region_all_{ts}.png"
            img = sct.grab(region)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))

        meta_desc = {"descripcion": "", "consideraciones": "", "observacion": ""}
        try:
            meta_in = {
                "descripcion": meta_desc.get("descripcion", ""),
                "consideraciones": meta_desc.get("consideraciones", ""),
                "observaciones": meta_desc.get("observacion", ""),
            }
            edited_path, meta_out = open_capture_editor_fn(str(out_path), meta_in)
            if edited_path and os.path.exists(edited_path):
                out_path = Path(edited_path)
            meta_desc["descripcion"] = meta_out.get("descripcion", "")
            meta_desc["consideraciones"] = meta_out.get("consideraciones", "")
            meta_desc["observacion"] = meta_out.get("observaciones", "")
        except Exception as exc:
            Messagebox.showwarning("Editor", f"Editor no disponible: {exc}")

        _persist_capture_result(
            Path(out_path),
            meta_desc,
            "snap_region_all",
            "[SNAP] Captura de region guardada.",
            "[SNAP] Captura de region agregada a la evidencia seleccionada.",
            target_step_index,
            inherit_primary_meta=bool(target_step_index is not None),
        )

    def _open_evidence_details_modal(step_index: int) -> None:
        """Display a modal that manages the captures linked to a step."""

        steps = session.get("steps", [])
        if step_index < 0 or step_index >= len(steps):
            Messagebox.showwarning("Evidencias", "No se encontró la evidencia seleccionada.")
            return
        step = steps[step_index]
        win = tb.Toplevel(root)
        win.title(f"Evidencia #{step_index + 1}")
        win.transient(root)
        win.grab_set()
        container = tb.Frame(win, padding=16)
        container.pack(fill=BOTH, expand=YES)

        meta_frame = tb.Frame(container)
        meta_frame.pack(fill=X, pady=(0, 12))
        tb.Label(
            meta_frame,
            text=step.get("desc", "") or "Sin descripción",
            font=("Segoe UI", 11, "bold"),
            wraplength=520,
            justify="left",
        ).pack(anchor=W)
        tb.Label(
            meta_frame,
            text=f"Consideraciones: {step.get('consideraciones', '') or '-'}",
            wraplength=520,
            justify="left",
        ).pack(anchor=W, pady=(6, 0))
        tb.Label(
            meta_frame,
            text=f"Observación: {step.get('observacion', '') or '-'}",
            wraplength=520,
            justify="left",
        ).pack(anchor=W, pady=(2, 0))

        shots_frame = tb.Labelframe(container, text="Capturas asociadas", padding=12)
        shots_frame.pack(fill=BOTH, expand=YES)

        shots_list = tk.Listbox(shots_frame, height=8)
        shots_list.pack(fill=BOTH, expand=YES, side=LEFT)
        preview_var = tk.StringVar(value="Selecciona una captura para consultar su ruta.")
        tb.Label(shots_frame, textvariable=preview_var, wraplength=260, justify="left").pack(
            side=LEFT, padx=(12, 0), fill=BOTH, expand=YES
        )

        def _refresh_shots_list() -> None:
            shots_list.delete(0, tk.END)
            for idx, shot_path in enumerate(step.get("shots", [])):
                label = os.path.basename(shot_path) or f"captura_{idx + 1}.png"
                shots_list.insert(tk.END, f"{idx + 1}. {label}")
            if shots_list.size():
                shots_list.selection_set(0)
                _update_preview()
            else:
                preview_var.set("La evidencia no tiene capturas registradas.")

        def _run_capture_with_modal_release(action: Callable[[], None]) -> None:
            """Execute an action freeing the modal grab so overlays can receive input."""

            has_grab = False
            try:
                has_grab = win.grab_current() is win
            except Exception:
                has_grab = False
            if has_grab:
                try:
                    win.grab_release()
                except Exception:
                    has_grab = False
            try:
                action()
            finally:
                if has_grab and win.winfo_exists():
                    try:
                        win.grab_set()
                    except Exception:
                        pass

        def _get_selection_index() -> Optional[int]:
            try:
                idx = int(shots_list.curselection()[0])
            except (IndexError, ValueError):
                return None
            return idx

        def _update_preview(*_args: object) -> None:
            idx = _get_selection_index()
            if idx is None:
                preview_var.set("Selecciona una captura para consultar su ruta.")
                return
            shots = step.get("shots", [])
            if idx >= len(shots):
                preview_var.set("No se encontró la captura solicitada.")
                return
            preview_var.set(shots[idx] or "(sin archivo)")

        def _open_selected_image() -> None:
            idx = _get_selection_index()
            if idx is None:
                Messagebox.showwarning("Evidencias", "Selecciona una captura para abrirla.")
                return
            shots = step.get("shots", [])
            if idx >= len(shots):
                Messagebox.showwarning("Evidencias", "No se encontró la captura seleccionada.")
                return
            path = shots[idx]
            if not path:
                Messagebox.showwarning("Evidencias", "La captura seleccionada no tiene un archivo asociado.")
                return
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except Exception as exc:
                Messagebox.showerror("Evidencias", f"No fue posible abrir la imagen: {exc}")

        def _edit_primary_capture() -> None:
            _open_capture_editor_for_shot(step_index, 0)
            _refresh_shots_list()

        def _capture_extra_monitor() -> None:
            """Capture an additional monitor screenshot for the selected evidence."""

            def _action() -> None:
                """Run the extra monitor capture workflow."""

                snap_externo_monitor(target_step_index=step_index)
                _refresh_evidence_tree()
                _refresh_shots_list()

            _run_capture_with_modal_release(_action)

        def _capture_extra_region() -> None:
            """Capture an extra region screenshot for the selected evidence."""

            def _action() -> None:
                """Run the extra region capture workflow."""

                snap_region_all(target_step_index=step_index)
                _refresh_evidence_tree()
                _refresh_shots_list()

            _run_capture_with_modal_release(_action)

        shots_list.bind("<<ListboxSelect>>", _update_preview, add="+")
        _refresh_shots_list()

        buttons = tb.Frame(container)
        buttons.pack(fill=X, pady=(12, 0))
        tb.Button(buttons, text="Editar captura principal", command=_edit_primary_capture, bootstyle=PRIMARY).pack(
            side=LEFT
        )
        tb.Button(
            buttons,
            text="Snap monitor extra",
            command=_capture_extra_monitor,
            bootstyle=INFO,
        ).pack(side=LEFT, padx=8)
        tb.Button(
            buttons,
            text="Snap región extra",
            command=_capture_extra_region,
            bootstyle=INFO,
        ).pack(side=LEFT, padx=8)
        tb.Button(buttons, text="Abrir imagen seleccionada", command=_open_selected_image, bootstyle=SECONDARY).pack(
            side=LEFT, padx=8
        )
        tb.Button(buttons, text="Cerrar", command=win.destroy, bootstyle=SECONDARY).pack(side=RIGHT)

    def generar_doc():
        """Auto-generated docstring for `generar_doc`."""
        if not session["steps"]:
            if not Messagebox.askyesno("Reporte","No hay pasos. ¿Generar documento vacío?"): return
        outp = Path(doc_var.get()); outp.parent.mkdir(parents=True, exist_ok=True)
        build_word_fn(session.get("title"), session["steps"], str(outp))
        _update_session_outputs()
        Messagebox.showinfo(f"Reporte generado:\n{outp}", f"Reporte Guardado En: \n{outp}")
        status.set("✅ Reporte generado")
        session_saved["val"] = True
        btn_limpiar.configure(state="normal")
    
    def modal_confluence_url():
        """Auto-generated docstring for `modal_confluence_url`."""
        win = tb.Toplevel(root); win.title("Importar a Confluence"); win.transient(root); win.grab_set(); win.geometry("800x300")
        frm = tb.Frame(win, padding=15); frm.pack(fill=BOTH, expand=YES)
        tb.Label(frm, text="URL de la página de Confluence", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(0,8))
    
        tb.Label(frm, text="ENTORNO", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(10,2))
        hist = controller.history.load_history(controller.CONFLUENCE_HISTORY_CATEGORY, controller.CONF_DEFAULT)
        urlv = tb.StringVar(value=hist[0] if hist else "")
        cmb = tb.Combobox(frm, textvariable=urlv, values=hist, width=70, bootstyle="light"); cmb.pack(fill=X)
        cmb.icursor("end")
    
        tb.Label(frm, text="ESPACIO", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(10,2))
        histspaces = controller.history.load_history(controller.CONFLUENCE_SPACES_CATEGORY, "")
        urlvspaces = tb.StringVar(value=histspaces[0] if histspaces else "")
        cmbspaces = tb.Combobox(frm, textvariable=urlvspaces, values=histspaces, width=70, bootstyle="light"); cmbspaces.pack(fill=X)
        cmbspaces.icursor("end")
        
        res = {"url": None}
        btns = tb.Frame(frm); btns.pack(fill=X, pady=(12,0))
        def ok():
            """Auto-generated docstring for `ok`."""
            space_value = urlvspaces.get().strip()
            if space_value:
                controller.history.register_history_value(controller.CONFLUENCE_SPACES_CATEGORY, space_value)
            res["url"] = ((urlv.get() + space_value) or "").strip(); win.destroy()
        def cancel():
            """Auto-generated docstring for `cancel`."""
            res["url"] = None; win.destroy()
        tb.Button(btns, text="Cancelar", command=cancel, bootstyle=SECONDARY).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Aceptar", command=ok, bootstyle=PRIMARY).pack(side=RIGHT)
        win.wait_window(); return res["url"]
    
    def importar_confluence():
        """Auto-generated docstring for `importar_confluence`."""
        if not session["steps"]:
            Messagebox.showwarning( "Confluence" , "No hay pasos en la sesión."); return
        outp = Path(doc_var.get()); outp.parent.mkdir(parents=True, exist_ok=True)
        build_word_fn(session.get("title"), session["steps"], str(outp))
    
    
        url_c = modal_confluence_url()
        if not url_c: return
        controller.history.register_history_value(controller.CONFLUENCE_HISTORY_CATEGORY, url_c)
    
        status.set("⏳ Preparando contenido y abriendo Confluence...")
        controller.browser.open_chrome_with_profile(url_c, "Default")
        log_path = sessions_dir / f"{session.get('title')}_confluence.log"
    
        Messagebox.showinfo(
            "Confluence",
            "Haz click en el campo de Confluence donde quieras pegar.\n"
            "El pegado empezará en 5 segundos."
        )
    
        pasted, errs = import_steps_fn(session["steps"], delay_sec=5, log_path=log_path)
    
        if errs:
            Messagebox.showwarning("Confluence", f"Pegado con advertencias ({len(errs)}). Revisa el log:\n{log_path}")
        else:
            Messagebox.showinfo("Confluence", f"✅ Pegado de {pasted} pasos completado.\nLog: {log_path}")
    
    
        session_saved["val"] = True
        try:
            btn_limpiar.configure(state="normal")
        except Exception:
            pass
    controls_bar = tb.Frame(parent, padding=(16, 6))
    controls_bar.pack(fill=tk.X)
    # --- Helpers de limpieza y selección ---
    def _clear_evidence_for(base_name: str, also_clear_session: bool = True):
        """Limpiar solo el estado en memoria manteniendo evidencias en disco."""
        removed = False  # ya no se elimina nada en disco
        if also_clear_session:
            try: session["steps"].clear()
            except Exception: pass
            _refresh_evidence_tree()
        return removed
    
    def reset_monitor_selection():
        """Auto-generated docstring for `reset_monitor_selection`."""
        _monitor_index["val"] = None
        Messagebox.showinfo("SNAP Externo","La próxima captura externa te pedirá la pantalla nuevamente.")
    
    def limpiar_cache():
        """Auto-generated docstring for `limpiar_cache`."""
        # Si aún no se ha guardado (DONE o Importar Confluence), pedir confirmación
        if not session_saved["val"]:
            if not Messagebox.askyesno("Limpiar caché (solo GUI)","Aún no has guardado con DONE ni Importar Confluence.¿Deseas limpiar SOLO el historial en la GUI de todas formas?(No se borrarán archivos de evidencia.)"):return

        if _is_dashboard_editing():
            _clear_dashboard_edit_mode()
            session_state.update({"active": False, "paused": False, "timerJob": None})
            _cancel_timer()
            timer_var.set(format_elapsed(0))
        base = controller.naming.slugify_for_windows(base_var.get() or "reporte")
        _clear_evidence_for(base, also_clear_session=True)
        status.set("🧹 Caché limpiado en la GUI. Las evidencias en disco se mantienen intactas.")
    def abrir_nav():
        """Auto-generated docstring for `abrir_nav`."""
        url = (url_var.get() or controller.DEFAULT_URL).strip() or controller.DEFAULT_URL
        ok, msg = controller.browser.open_chrome_with_profile(url, "Default")
        if ok:
            controller.history.register_history_value(controller.URL_HISTORY_CATEGORY, url)
            status.set("✅ Chrome abierto (perfil Default)")
        else:
            Messagebox.showerror("Navegador",f"No se pudo abrir Chrome: {msg}")
    
    tb.Button(controls_bar, text="🔗 Abrir navegador", command=abrir_nav, bootstyle=PRIMARY, width=18).pack(side=LEFT, padx=(0,8))
    tb.Button(controls_bar, text="🖥️ Cambiar pantalla…", command=reset_monitor_selection, bootstyle=SECONDARY, width=20).pack(side=LEFT, padx=8)
    tb.Button(controls_bar, text="🖥️ SNAP externo", command=snap_externo_monitor, bootstyle=INFO, width=16).pack(side=LEFT, padx=8)
    tb.Button(controls_bar, text="📐 SNAP región", command=snap_region_all, bootstyle=INFO, width=16).pack(side=LEFT, padx=8)
    
    ask_always = tk.BooleanVar(value=False)
    def _ask_switch():
        """Auto-generated docstring for `_ask_switch`."""
        if ask_always.get(): _monitor_index["val"] = None
    tb.Checkbutton(controls_bar, text="Preguntar pantalla cada vez", variable=ask_always, bootstyle="round-toggle", command=_ask_switch).pack(side=LEFT, padx=8)
    tb.Button(controls_bar, text="📥 Importar Confluence", command=importar_confluence, bootstyle=SUCCESS, width=22).pack(side=LEFT, padx=8)
    btn_limpiar = tb.Button(controls_bar, text="Finalizar Pruebas",  command=limpiar_cache, bootstyle=DANGER, width=16)
    btn_limpiar.pack(side=RIGHT, padx=(8,0))
    tb.Button(controls_bar, text="✅ DONE", command=generar_doc, bootstyle=WARNING, width=12).pack(side=RIGHT)

    context = PruebasViewContext(
        buttons=controls_bar,
        notebook=notebook,
        dashboardTab=dashboard_tab,
        sessionTab=session_tab,
    )

    def _sync_controls(_event: Optional[object] = None) -> None:
        """Update the visibility of the control bar when the tab changes."""

        context.refresh_controls_visibility()

    notebook.bind("<<NotebookTabChanged>>", _sync_controls, add="+")
    context.refresh_controls_visibility()

    return context
