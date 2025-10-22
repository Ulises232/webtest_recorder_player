"""UI components for the 'Pruebas' workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
import os
import time
import tkinter as tk
from tkinter import ttk

import ttkbootstrap as tb
from ttkbootstrap.constants import *  # noqa: F401,F403

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
        error_msg = controller.update_session_details(
            session_id,
            base_var.get().strip(),
            url_var.get().strip(),
            doc_var.get().strip(),
            ev_var.get().strip(),
        )
        if error_msg:
            Messagebox.showerror("Sesión", error_msg)
            return
        prev_base["val"] = controller.slugify_for_windows(base_var.get() or "reporte")
        session["title"] = (base_var.get() or session.get("title", "")).strip() or session.get("title", "")
        session_saved["val"] = True
        status.set("💾 Sesión actualizada desde el editor.")
        _refresh_sessions_table()

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
    urls = controller.load_history(controller.URL_HISTORY_CATEGORY, controller.DEFAULT_URL)
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
    
    sessions_dir = controller.getSessionsDirectory()
    evidence_dir = controller.getEvidenceDirectory()

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

    header_bg = "#E8ECFF"
    row_even_bg = "#ffffff"
    row_odd_bg = "#f5f7fa"

    dashboard_header = tb.Frame(dashboard_tab)
    dashboard_header.pack(fill=X, pady=(0, 16))
    tb.Label(
        dashboard_header,
        text="Sesiones de pruebas",
        font=("Segoe UI", 16, "bold"),
    ).pack(side=LEFT)

    def _get_current_username() -> str:
        """Return the username of the authenticated operator."""

        return controller.get_authenticated_username().strip()

    def _prepare_new_session_form() -> None:
        """Reset the inputs before creating a new session."""

        try:
            base_var.set("reporte")
        except Exception:
            pass
        default_url = controller.DEFAULT_URL
        urls = controller.load_history(controller.URL_HISTORY_CATEGORY, default_url)
        try:
            url_var.set(urls[0] if urls else default_url)
        except Exception:
            pass
        refresh_paths()
        status.set("🆕 Prepara una nueva sesión de evidencias.")

    def _open_new_session_tab() -> None:
        """Navigate to the evidence tab to start a new session."""

        _prepare_new_session_form()
        notebook.select(session_tab)

    tb.Button(
        dashboard_header,
        text="🔄 Actualizar",
        style="CartoonGhost.TButton",
        command=lambda: _refresh_sessions_table(),
        compound=LEFT,
    ).pack(side=RIGHT)
    tb.Button(
        dashboard_header,
        text="✨ Crear sesión",
        style="CartoonAccent.TButton",
        command=_open_new_session_tab,
        compound=LEFT,
    ).pack(side=RIGHT, padx=(0, 8))

    table_container = tb.Frame(dashboard_tab)
    table_container.pack(fill=BOTH, expand=YES)

    header_frame = tk.Frame(table_container, bg=header_bg)
    header_frame.pack(fill=X, padx=(0, 12))
    header_frame.grid_columnconfigure(0, minsize=160)
    header_frame.grid_columnconfigure(1, weight=1, minsize=240)
    header_frame.grid_columnconfigure(2, minsize=160)
    header_frame.grid_columnconfigure(3, minsize=340)

    header_specs = (
        ("Fecha", "center"),
        ("Nombre", "w"),
        ("Usuario", "center"),
        ("Acciones", "e"),
    )
    for column_index, (title, anchor) in enumerate(header_specs):
        header_label = tk.Label(
            header_frame,
            text=title,
            bg=header_bg,
            fg="#1f2240",
            font=("Segoe UI", 10, "bold"),
            anchor=anchor,
        )
        header_label.grid(row=0, column=column_index, sticky="ew", padx=(16 if column_index == 0 else 8, 8), pady=12)

    sessions_canvas = tk.Canvas(
        table_container,
        highlightthickness=0,
        background=row_even_bg,
        borderwidth=0,
    )
    sessions_canvas.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 12))

    sessions_scroll = ttk.Scrollbar(table_container, orient="vertical", command=sessions_canvas.yview)
    sessions_scroll.pack(side=RIGHT, fill=Y)
    sessions_canvas.configure(yscrollcommand=sessions_scroll.set)

    sessions_rows_holder = tk.Frame(sessions_canvas, bg=row_even_bg)
    sessions_rows_holder.grid_columnconfigure(0, weight=1)
    sessions_window = sessions_canvas.create_window((0, 0), window=sessions_rows_holder, anchor="nw")

    def _on_sessions_canvas_configure(event) -> None:
        """Resize the table canvas content when the widget changes."""

        try:
            sessions_canvas.itemconfigure(sessions_window, width=event.width)
        except Exception:
            pass

    def _update_sessions_scrollregion(_event) -> None:
        """Sync the scrollable region with the content size."""

        try:
            sessions_canvas.configure(scrollregion=sessions_canvas.bbox("all"))
        except Exception:
            pass

    sessions_canvas.bind("<Configure>", _on_sessions_canvas_configure, add="+")
    sessions_rows_holder.bind("<Configure>", _update_sessions_scrollregion, add="+")
    bind_mousewheel(sessions_canvas, sessions_canvas.yview)

    def _refresh_sessions_table() -> None:
        """Reload the table with the latest sessions from the service."""

        for child in sessions_rows_holder.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        sessions, error = controller.list_sessions(limit=100)
        if error:
            status.set(f"⚠️ {error}")
            return
        current_username = _get_current_username().lower()
        for index, session_obj in enumerate(sessions, start=1):
            is_owner = session_obj.username.lower() == current_username and bool(current_username)
            row_bg = row_even_bg if index % 2 == 0 else row_odd_bg
            row_frame = tk.Frame(sessions_rows_holder, bg=row_bg)
            row_frame.grid(row=index - 1, column=0, sticky="ew", pady=(0, 8), padx=(0, 12))
            row_frame.grid_columnconfigure(0, minsize=160)
            row_frame.grid_columnconfigure(1, weight=1, minsize=240)
            row_frame.grid_columnconfigure(2, minsize=160)
            row_frame.grid_columnconfigure(3, minsize=340)

            tk.Label(
                row_frame,
                text=format_timestamp(session_obj.startedAt),
                bg=row_bg,
                fg="#1f2230",
                font=("Segoe UI", 10),
                anchor="center",
            ).grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=12)

            tk.Label(
                row_frame,
                text=session_obj.name,
                bg=row_bg,
                fg="#1f2230",
                font=("Segoe UI", 10),
                anchor="w",
            ).grid(row=0, column=1, sticky="ew", padx=8, pady=12)

            tk.Label(
                row_frame,
                text=session_obj.username,
                bg=row_bg,
                fg="#1f2230",
                font=("Segoe UI", 10),
                anchor="center",
            ).grid(row=0, column=2, sticky="ew", padx=8, pady=12)

            actions_frame = tk.Frame(row_frame, bg=row_bg)
            actions_frame.grid(row=0, column=3, sticky="e", padx=(8, 16))

            def _make_action_button(label: str, handler: Callable[[], None], enabled: bool = True) -> tb.Button:
                """Create a blue-styled action button for the dashboard table."""

                btn = tb.Button(
                    actions_frame,
                    text=label,
                    style="CartoonAccentSlim.TButton",
                    command=handler,
                    width=9,
                )
                if not enabled:
                    btn.configure(state="disabled")
                btn.pack(side=LEFT, padx=4)
                return btn

            _make_action_button(
                "Ver",
                handler=lambda obj=session_obj: _view_session_details(obj),
            )

            _make_action_button(
                "Editar",
                handler=lambda obj=session_obj: _open_session_editor(obj),
                enabled=is_owner,
            )

            _make_action_button(
                "Eliminar",
                handler=lambda obj=session_obj: _confirm_delete_session(obj),
                enabled=is_owner,
            )

            _make_action_button(
                "Descargar",
                handler=lambda obj=session_obj: _handle_download(obj),
            )

            if not is_owner:
                note_label = tk.Label(
                    actions_frame,
                    text="Solo propietario",
                    bg=row_bg,
                    fg="#6C63FF",
                    font=("Segoe UI", 8, "italic"),
                    anchor="e",
                )
                note_label.pack(anchor="e", pady=(6, 0))
        if sessions:
            status.set(f"📋 {len(sessions)} sesiones cargadas.")
        else:
            status.set("📋 No hay sesiones registradas todavía.")

    def _view_session_details(session_obj) -> None:
        """Display a read-only summary for the selected session."""

        win = tb.Toplevel(root)
        win.title(f"Sesión: {session_obj.name}")
        win.transient(root)
        win.grab_set()
        frm = tb.Frame(win, padding=16)
        frm.pack(fill=BOTH, expand=YES)
        tb.Label(frm, text=session_obj.name, font=("Segoe UI", 14, "bold")).pack(anchor=W, pady=(0, 12))
        details = (
            ("Fecha de inicio", format_timestamp(session_obj.startedAt)),
            ("Fecha de cierre", format_timestamp(session_obj.endedAt)),
            ("Usuario", session_obj.username),
            ("URL inicial", session_obj.initialUrl),
            ("Documento", session_obj.docxUrl),
            ("Carpeta evidencias", session_obj.evidencesUrl),
        )
        for label, value in details:
            row = tb.Frame(frm)
            row.pack(fill=X, pady=4)
            tb.Label(row, text=f"{label}:", font=("Segoe UI", 10, "bold"), width=18, anchor=E).pack(side=LEFT)
            tb.Label(row, text=value or "", font=("Segoe UI", 10), anchor=W, wraplength=520, justify=LEFT).pack(side=LEFT, fill=X, expand=YES, padx=(8, 0))
        tb.Button(frm, text="Cerrar", command=win.destroy, bootstyle=SECONDARY, width=18).pack(anchor=E, pady=(16, 0))

    def _map_evidence_to_step(evidence: SessionEvidenceDTO) -> Dict[str, object]:
        """Translate a persisted evidence to the in-memory representation."""

        shots: List[str] = []
        if evidence.filePath:
            shots.append(evidence.filePath)
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
        try:
            controller.clear_active_session()
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

        session_payload, evidences, error = controller.activate_session_for_dashboard_edit(session_obj.sessionId or 0)
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

        prev_base["val"] = controller.slugify_for_windows(base_var.get() or "reporte")
        session["title"] = loaded_session.name or ""
        session["sessionId"] = loaded_session.sessionId
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
        error = controller.delete_session(session_obj.sessionId or 0)
        if error:
            Messagebox.showerror("Sesión", error)
            return
        status.set("🗑️ Sesión eliminada.")
        _refresh_sessions_table()

    def _handle_download(session_obj) -> None:
        """Placeholder action for the future download workflow."""

        Messagebox.showinfo(
            "Descarga",
            "La descarga de sesiones estará disponible próximamente.",
        )

    _refresh_sessions_table()

    auto_paths_state = {"enabled": True}

    def refresh_paths(*_args: object) -> None:
        """Compute default output locations when the base name changes."""

        if not auto_paths_state.get("enabled", True):
            return
        base = controller.slugify_for_windows(base_var.get() or "reporte")
        final = f"{base}"
        doc_var.set(str(sessions_dir / f"{final}.docx"))
        ev_var.set(str(evidence_dir / final))

    base_var.trace_add("write", refresh_paths)
    refresh_paths()

    prev_base = {"val": controller.slugify_for_windows(base_var.get() or "reporte")}

    def _on_base_change(*_args: object) -> None:
        """Synchronize caches and optionally clear history when the base changes."""

        new_base = controller.slugify_for_windows(base_var.get() or "reporte")
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
    
    session = {"title": "Incidencia", "steps": [], "sessionId": None}
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
    
        timer_var.set(format_elapsed(controller.get_session_elapsed_seconds()))
    
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
        error = controller.update_active_session_outputs(doc_var.get(), ev_var.get())
        if error:
            status.set(f"⚠️ {error}")
    
    doc_var.trace_add("write", _update_session_outputs)
    ev_var.trace_add("write", _update_session_outputs)
    
    def _show_elapsed_message() -> None:
        """Display the elapsed time in a dialog."""
    
        _refresh_timer_label()
        Messagebox.showinfo("Sesión", f"Tiempo transcurrido: {format_elapsed(controller.get_session_elapsed_seconds())}")
    
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

        base_name = controller.slugify_for_windows(base_var.get() or "reporte") or "reporte"
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
    
        session_obj, error = controller.begin_evidence_session(
            session_title,
            (url_var.get() or controller.DEFAULT_URL).strip() or controller.DEFAULT_URL,
            str(doc_path),
            str(evidence_path),
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
            error = controller.resume_evidence_session()
            if error:
                Messagebox.showerror("Sesión", error)
                return
            session_state["paused"] = False
            status.set("▶️ Sesión reanudada.")
            btn_session_pause.configure(text="Pausar sesión")
            _schedule_timer_tick()
            return
    
        error = controller.pause_evidence_session()
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
    
        session_obj, error = controller.finalize_evidence_session()
        if error:
            Messagebox.showerror("Sesión", error)
            return
    
        session_state.update({"active": False, "paused": False, "timerJob": None})
        _cancel_timer()
        final_elapsed = session_obj.durationSeconds if session_obj else controller.get_session_elapsed_seconds()
        timer_var.set(format_elapsed(final_elapsed))
        status.set("✅ Sesión finalizada.")
        try:
            btn_session_start.configure(state="normal")
            btn_session_pause.configure(state="disabled", text="Pausar sesión")
            btn_session_finish.configure(state="disabled")
        except Exception:
            pass
    
    def edit_selected_evidence() -> None:
        """Open the capture editor for the selected evidence."""
    
        if not _ensure_session_active(True):
            return
        tree = evidence_tree_ref.get("tree")
        if not isinstance(tree, ttk.Treeview):
            return
        selection = tree.selection()
        if not selection:
            Messagebox.showwarning("Evidencias", "Selecciona una evidencia para editarla.")
            return
        try:
            index = int(selection[0])
        except ValueError:
            Messagebox.showwarning("Evidencias", "La evidencia seleccionada no es válida.")
            return
        if index < 0 or index >= len(session.get("steps", [])):
            Messagebox.showwarning("Evidencias", "No se encontró la evidencia seleccionada.")
            return
    
        step = session["steps"][index]
        shots = step.get("shots") or []
        if not shots:
            Messagebox.showwarning("Evidencias", "La evidencia no tiene una imagen asociada.")
            return
    
        image_path = Path(shots[0])
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
        shots[0] = str(new_path)
        step["desc"] = meta_out.get("descripcion", "") or ""
        step["consideraciones"] = meta_out.get("consideraciones", "") or ""
        step["observacion"] = meta_out.get("observaciones", "") or ""
    
        evidence_id = step.get("id")
        if evidence_id:
            error = controller.update_session_evidence(
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
        status.set("✏️ Evidencia actualizada.")
    
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
    
    def snap_externo_monitor():
        """Auto-generated docstring for `snap_externo_monitor`."""
        if not _ensure_session_running():
            return
        if not ensure_mss():
            return
        import mss, mss.tools
        with mss.mss() as sct:
            monitors, idx = select_monitor(sct)
            if monitors is None: return
            mon = monitors[idx]
            evid_dir = Path(ev_var.get()); evid_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S"); out_path = evid_dir / f"snap_ext_monitor{idx}_{ts}.png"
            img = sct.grab(mon); mss.tools.to_png(img.rgb, img.size, output=str(out_path))
    
        # === ÚNICA ventana: Editor con vista previa + Descripción/Consideraciones/Observación ===
        meta_desc = {"descripcion":"", "consideraciones":"", "observacion":""}
        try:
            meta_in = {
                "descripcion": meta_desc.get("descripcion",""),
                "consideraciones": meta_desc.get("consideraciones",""),
                "observaciones": meta_desc.get("observacion",""),
            }
            edited_path, meta_out = open_capture_editor_fn(str(out_path), meta_in)
            if edited_path and os.path.exists(edited_path):
                out_path = Path(edited_path)
            # Sincronizar claves con el formato del sistema (observacion en singular)
            meta_desc["descripcion"]     = meta_out.get("descripcion","")
            meta_desc["consideraciones"] = meta_out.get("consideraciones","")
            meta_desc["observacion"]     = meta_out.get("observaciones","")
        except Exception as e:
            Messagebox.showwarning( "Editor",f"Editor no disponible: {e}")
    
        step = {"cmd": "snap_externo", "shots": [str(out_path)]}
        if meta_desc["descripcion"]: step["desc"] = meta_desc["descripcion"]
        if meta_desc["consideraciones"]: step["consideraciones"] = meta_desc["consideraciones"]
        if meta_desc["observacion"]: step["observacion"] = meta_desc["observacion"]
        session["steps"].append(step)
        evidence, error = controller.register_session_evidence(
            Path(step["shots"][0]),
            step.get("desc", ""),
            step.get("consideraciones", ""),
            step.get("observacion", ""),
        )
        if error:
            Messagebox.showerror("Sesión", error)
        elif evidence:
            step["id"] = evidence.evidenceId
            step["createdAt"] = evidence.createdAt
            step["elapsedSinceStart"] = evidence.elapsedSinceSessionStartSeconds
            step["elapsedSincePrevious"] = evidence.elapsedSincePreviousEvidenceSeconds
        session_saved["val"] = False
        _refresh_evidence_tree()
        _schedule_timer_tick()
        status.set(f"🖥️ SNAP externo agregado (monitor {idx})")
    
    
    def snap_region_all():
        """Auto-generated docstring for `snap_region_all`."""
        if not _ensure_session_running():
            return
        if not ensure_mss():
            return
        import mss, mss.tools
        with mss.mss() as sct:
            desktop = sct.monitors[0]
            bbox = select_region_overlay(root, desktop)
            if not bbox:
                status.set("Selección cancelada."); return
    
            left, top, width, height = bbox
            region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
            evid_dir = Path(ev_var.get()); evid_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S"); out_path = evid_dir / f"snap_region_all_{ts}.png"
            img = sct.grab(region); mss.tools.to_png(img.rgb, img.size, output=str(out_path))
    
        # === ÚNICA ventana: Editor con vista previa + Descripción/Consideraciones/Observación ===
        meta_desc = {"descripcion":"", "consideraciones":"", "observacion":""}
        try:
            meta_in = {
                "descripcion": meta_desc.get("descripcion",""),
                "consideraciones": meta_desc.get("consideraciones",""),
                "observaciones": meta_desc.get("observacion",""),
            }
            edited_path, meta_out = open_capture_editor_fn(str(out_path), meta_in)
            if edited_path and os.path.exists(edited_path):
                out_path = Path(edited_path)
            meta_desc["descripcion"]     = meta_out.get("descripcion","")
            meta_desc["consideraciones"] = meta_out.get("consideraciones","")
            meta_desc["observacion"]     = meta_out.get("observaciones","")
        except Exception as e:
            Messagebox.showwarning("Editor", f"Editor no disponible: {e}")
    
        step = {"cmd": "snap_region_all", "shots": [str(out_path)]}
        if meta_desc["descripcion"]: step["desc"] = meta_desc["descripcion"]
        if meta_desc["consideraciones"]: step["consideraciones"] = meta_desc["consideraciones"]
        if meta_desc["observacion"]: step["observacion"] = meta_desc["observacion"]
        session["steps"].append(step)
        evidence, error = controller.register_session_evidence(
            Path(step["shots"][0]),
            step.get("desc", ""),
            step.get("consideraciones", ""),
            step.get("observacion", ""),
        )
        if error:
            Messagebox.showerror("Sesión", error)
        elif evidence:
            step["id"] = evidence.evidenceId
            step["createdAt"] = evidence.createdAt
            step["elapsedSinceStart"] = evidence.elapsedSinceSessionStartSeconds
            step["elapsedSincePrevious"] = evidence.elapsedSincePreviousEvidenceSeconds
        session_saved["val"] = False
        _refresh_evidence_tree()
        _schedule_timer_tick()
        status.set("📐 SNAP región (todas) agregado")
    
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
        hist = controller.load_history(controller.CONFLUENCE_HISTORY_CATEGORY, controller.CONF_DEFAULT)
        urlv = tb.StringVar(value=hist[0] if hist else "")
        cmb = tb.Combobox(frm, textvariable=urlv, values=hist, width=70, bootstyle="light"); cmb.pack(fill=X)
        cmb.icursor("end")
    
        tb.Label(frm, text="ESPACIO", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(10,2))
        histspaces = controller.load_history(controller.CONFLUENCE_SPACES_CATEGORY, "")
        urlvspaces = tb.StringVar(value=histspaces[0] if histspaces else "")
        cmbspaces = tb.Combobox(frm, textvariable=urlvspaces, values=histspaces, width=70, bootstyle="light"); cmbspaces.pack(fill=X)
        cmbspaces.icursor("end")
        
        res = {"url": None}
        btns = tb.Frame(frm); btns.pack(fill=X, pady=(12,0))
        def ok():
            """Auto-generated docstring for `ok`."""
            space_value = urlvspaces.get().strip()
            if space_value:
                controller.register_history_value(controller.CONFLUENCE_SPACES_CATEGORY, space_value)
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
        controller.register_history_value(controller.CONFLUENCE_HISTORY_CATEGORY, url_c)
    
        status.set("⏳ Preparando contenido y abriendo Confluence...")
        controller.open_chrome_with_profile(url_c, "Default")
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
        base = controller.slugify_for_windows(base_var.get() or "reporte")
        _clear_evidence_for(base, also_clear_session=True)
        status.set("🧹 Caché limpiado en la GUI. Las evidencias en disco se mantienen intactas.")
    def abrir_nav():
        """Auto-generated docstring for `abrir_nav`."""
        url = (url_var.get() or controller.DEFAULT_URL).strip() or controller.DEFAULT_URL
        ok, msg = controller.open_chrome_with_profile(url, "Default")
        if ok:
            controller.register_history_value(controller.URL_HISTORY_CATEGORY, url)
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
