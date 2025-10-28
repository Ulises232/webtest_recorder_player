
"""Main Tkinter view for the desktop recorder desktop application."""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import ttk, messagebox as tk_messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import *
try:
    from ttkbootstrap.dialogs import Messagebox as BootstrapMessagebox
except Exception:  # pragma: no cover - fallback when ttkbootstrap is unavailable
    BootstrapMessagebox = None


class Messagebox:
    """Wrapper that normalizes message dialogs across Tkinter and ttkbootstrap."""

    _use_bootstrap_dialogs: bool = False

    @staticmethod
    def preferBootstrapDialogs(enable: bool) -> None:
        """Toggle the use of ttkbootstrap dialogs globally."""

        Messagebox._use_bootstrap_dialogs = bool(enable)

    @staticmethod
    def _should_use_bootstrap(method_name: str) -> bool:
        """Determine whether ttkbootstrap provides a compatible dialog method."""

        if not Messagebox._use_bootstrap_dialogs or BootstrapMessagebox is None:
            return False
        return hasattr(BootstrapMessagebox, method_name)

    @staticmethod
    def showinfo(title: str,message: str) -> None:
        """Display an informational dialog using the preferred backend."""

        if Messagebox._should_use_bootstrap("show_info"):
            BootstrapMessagebox.show_info(message, title)
            return
        tk_messagebox.showinfo(title=title, message=message)

    @staticmethod
    def showwarning(title: str,message: str) -> None:
        """Display a warning dialog using the preferred backend."""

        if Messagebox._should_use_bootstrap("show_warning"):
            BootstrapMessagebox.show_warning(message, title)
            return
        tk_messagebox.showwarning(title=title, message=message)

    @staticmethod
    def showerror(title: str,message: str) -> None:
        """Display an error dialog using the preferred backend."""

        if Messagebox._should_use_bootstrap("show_error"):
            BootstrapMessagebox.show_error(message, title)
            return
        tk_messagebox.showerror(title=title, message=message)

    @staticmethod
    def askyesno( title: str,message: str) -> bool:
        """Request a yes/no confirmation dialog and return the chosen option."""

        if Messagebox._should_use_bootstrap("askyesno"):
            result = BootstrapMessagebox.askyesno(message, title)
            return str(result).strip().lower() in {"yes", "true", "1", "ok"}
        if Messagebox._should_use_bootstrap("yesno"):
            result = BootstrapMessagebox.yesno(message, title)
            return str(result).strip().lower() in {"yes", "true", "1", "ok"}
        return bool(tk_messagebox.askyesno(title=title, message=message))

from app.controllers.main_controller import MainController
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus
from app.views.generacion_automatica_view import build_generacion_automatica_view
from app.views.generacion_manual_view import build_generacion_manual_view
from app.views.modificacion_matriz_view import build_modificacion_matriz_view
from app.views.alta_ciclos_view import build_alta_ciclos_view
from app.views.modificacion_ciclos_view import build_modificacion_ciclos_view
from app.views.pruebas_view import PruebasViewContext, build_pruebas_view
from app.views.login_view import build_login_view

# --- helper: enable mouse wheel scrolling on canvas/treeview ---
def _bind_mousewheel(_widget, _yview_callable):
    """Enable mouse wheel scrolling on a Tkinter widget."""
    def _on_mousewheel(event):
        """Auto-generated docstring for `_on_mousewheel`."""
        delta = 0
        if hasattr(event, "num") and event.num in (4, 5):
            delta = -1 if event.num == 4 else 1
        else:
            delta = -1 if event.delta > 0 else 1
        try:
            _yview_callable("scroll", delta, "units")
        except Exception:
            try: _yview_callable(delta)
            except Exception: pass
        return "break"
    _widget.bind("<Enter>", lambda e: _widget.bind_all("<MouseWheel>", _on_mousewheel), add="+")
    _widget.bind("<Leave>", lambda e: _widget.unbind_all("<MouseWheel>"), add="+")
    _widget.bind("<Button-4>", _on_mousewheel, add="+")
    _widget.bind("<Button-5>", _on_mousewheel, add="+")


from utils.report_word import build_word
from utils.confluence_ui import import_steps_to_confluence
from utils.capture_editor import open_capture_editor

controller = MainController()


def _format_elapsed(seconds: Optional[int]) -> str:
    """Convert a number of seconds into HH:MM:SS format."""

    total = max(0, int(seconds or 0))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_timestamp(value: Optional[datetime]) -> str:
    """Return a human friendly timestamp representation."""

    if not value:
        return ""
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")



def text_modal(master, title: str):
    """Display a modal with three multiline text inputs."""
    win = tb.Toplevel(master); win.title(title); win.transient(master); win.grab_set()
    win.resizable(True, True); win.geometry("760x540")
    try: win.minsize(640, 420)
    except Exception: pass

    container = tb.Frame(win, padding=15); container.pack(fill=BOTH, expand=YES)
    tb.Label(container, text=title, font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0,8))

    tb.Label(container, text="Descripción", font=("Segoe UI", 10, "bold")).pack(anchor=W)
    desc = tk.Text(container, height=6, wrap="word"); desc.configure(font=("Segoe UI", 10))
    desc.pack(fill=BOTH, expand=YES, pady=(2,10))

    tb.Label(container, text="Consideraciones", font=("Segoe UI", 10, "bold")).pack(anchor=W)
    cons = tk.Text(container, height=5, wrap="word"); cons.configure(font=("Segoe UI", 10))
    cons.pack(fill=BOTH, expand=YES, pady=(2,10))

    tb.Label(container, text="Observación", font=("Segoe UI", 10, "bold")).pack(anchor=W)
    obs = tk.Text(container, height=5, wrap="word"); obs.configure(font=("Segoe UI", 10))
    obs.pack(fill=BOTH, expand=YES, pady=(2,10))

    btns = tb.Frame(container); btns.pack(fill=X, pady=(8,0))
    result = {"descripcion":"", "consideraciones":"", "observacion":"", "cancel": False}

    def ok():
        """Auto-generated docstring for `ok`."""
        result["descripcion"] = desc.get("1.0","end").strip()
        result["consideraciones"] = cons.get("1.0","end").strip()
        result["observacion"] = obs.get("1.0","end").strip()
        win.destroy()
    def cancel():
        """Auto-generated docstring for `cancel`."""
        result["cancel"] = True
        win.destroy()
    tb.Button(btns, text="Cancelar", command=cancel, bootstyle=SECONDARY, width=12).pack(side=RIGHT, padx=6)
    tb.Button(btns, text="Aceptar", command=ok, bootstyle=PRIMARY, width=12).pack(side=RIGHT)

    win.wait_window(); return result

def select_region_overlay(master, desktop: dict):
    """Create an overlay that lets the user select a screen region."""
    left = int(desktop.get("left", 0)); top = int(desktop.get("top", 0))
    width = int(desktop.get("width", 0)); height = int(desktop.get("height", 0))

    ov = tk.Toplevel(master); ov.overrideredirect(True)
    ov.bind("<F11>", lambda e: ov.attributes("-fullscreen", not bool(ov.attributes("-fullscreen"))))
    ov.bind("m", lambda e: ov.iconify()); ov.attributes("-topmost", True)
    try: ov.attributes("-alpha", 0.30)
    except Exception: pass
    ov.configure(bg="gray"); ov.geometry(f"{width}x{height}+{left}+{top}")

    canvas = tk.Canvas(ov, bg="gray", highlightthickness=0); canvas.pack(fill="both", expand=True)
    state = {"x0": None, "y0": None, "rect": None, "bbox": None}

    def on_press(e):
        """Auto-generated docstring for `on_press`."""
        state["x0"], state["y0"] = e.x, e.y
        if state["rect"]: canvas.delete(state["rect"]); state["rect"] = None
    def on_move(e):
        """Auto-generated docstring for `on_move`."""
        if state["x0"] is None: return
        x1, y1 = e.x, e.y
        if state["rect"]:
            canvas.coords(state["rect"], state["x0"], state["y0"], x1, y1)
        else:
            state["rect"] = canvas.create_rectangle(state["x0"], state["y0"], x1, y1, outline="red", width=3, dash=(4,2))
    def on_release(e):
        """Auto-generated docstring for `on_release`."""
        if state["x0"] is None: return
        x1, y1 = e.x, e.y; x0, y0 = state["x0"], state["y0"]
        lx, rx = min(x0, x1), max(x0, x1); ty, by = min(y0, y1), max(y0, y1)
        w = max(1, rx - lx); h = max(1, by - ty); abs_left = left + lx; abs_top = top + ty
        state["bbox"] = (abs_left, abs_top, w, h); ov.destroy()
    canvas.bind("<ButtonPress-1>", on_press); canvas.bind("<B1-Motion>", on_move); canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind_all("<Escape>", lambda e: ov.destroy())
    tk.Label(ov, text="Arrastra para seleccionar área (Esc para cancelar)", fg="white", bg="black").place(x=10, y=10)
    master.wait_window(ov); return state["bbox"]

def run_gui():
    """Render and start the Tkinter interface for the recorder."""
    app = tb.Window(themename="flatly")
    app.withdraw()
    app.update_idletasks()

    auth_result = build_login_view(app, controller, Messagebox)
    if not auth_result:
        app.destroy()
        return

    display_name = auth_result.displayName or auth_result.username or "Usuario"
    app.title(f"Pruebas / Evidencias - {display_name}")
    app.geometry("1500x640")
    app.deiconify()

    # === Contenedor principal: CONTENIDO IZQ + SIDEBAR DER ===
    container = tb.Frame(app); container.pack(fill=BOTH, expand=YES)

    # --- ÁREA DE CONTENIDO (izquierda) ---
    content_area = tb.Frame(container); content_area.pack(side=LEFT, fill=BOTH, expand=YES)

    # --- SIDEBAR (oculto al inicio) — icono + texto, a la DERECHA ---
    sidebar = tb.Frame(container, padding=(8,8), width=220)
    sidebar.pack_propagate(False)  # aún no se empaqueta; aparecerá después del primer click

    session_info = controller.auth.get_authenticated_user()
    if session_info:
        tb.Label(
            sidebar,
            text="Sesión activa",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=W, pady=(0, 4))
        tb.Label(
            sidebar,
            text=session_info.displayName or session_info.username,
            wraplength=180,
        ).pack(anchor=W, pady=(0, 12))
    _sidebar_visible = False

    def ensure_sidebar_visible():
        """Auto-generated docstring for `ensure_sidebar_visible`."""
        global _sidebar_visible
        try:
            val = _sidebar_visible
        except NameError:
            val = False
        if not val:
            sidebar.pack(side=RIGHT, fill=Y, padx=(12,0), pady=(0,0))  # barra a la DERECHA
            globals()['_sidebar_visible'] = True

    def hide_sidebar():
        """Oculta el sidebar y deja el contenido ocupando todo el ancho."""
        global _sidebar_visible
        try:
            sidebar.pack_forget()
        except Exception:
            pass
        _sidebar_visible = False
        try:
            content_area.pack_forget()
        except Exception:
            pass
        content_area.pack(side=LEFT, fill=BOTH, expand=YES)

    # Frames por sección (contenido)
    frame_gen_root   = tb.Frame(content_area, padding=(16,10))  # mini-launcher de Generación
    frame_gen_auto   = tb.Frame(content_area, padding=(16,10))
    frame_gen_manual = tb.Frame(content_area, padding=(16,10))
    frame_mod_matriz = tb.Frame(content_area, padding=(16,10))
    frame_alta_cic   = tb.Frame(content_area, padding=(16,10))
    frame_mod_cic    = tb.Frame(content_area, padding=(16,10))
    frame_pruebas    = tb.Frame(content_area, padding=(16,0))   # flujo existente
    frame_launcher   = tb.Frame(content_area, padding=(16,16))  # dashboard inicial

    def _section_title(parent, title, desc=None):
        """Auto-generated docstring for `_section_title`."""
        tb.Label(parent, text=title, font=("Segoe UI", 16, "bold")).pack(anchor=W, pady=(0,6))
        if desc:
            tb.Label(parent, text=desc, bootstyle=SECONDARY).pack(anchor=W)
        tb.Separator(parent).pack(fill=X, pady=10)

    # === Utils de interacción ===
    def _bind_click_all(widget, cmd):
        """Vuelve clickeable TODO el contenido (widget + descendientes)."""
        widget.bind("<Button-1>", lambda e: cmd(), add="+")
        try: widget.configure(cursor="hand2")
        except Exception: pass
        for child in widget.winfo_children():
            _bind_click_all(child, cmd)

    # === Tarjetas estilo dashboard (accesos rápidos) ===
    def _card(parent, title, subtitle="", icon="📄"):
        """Auto-generated docstring for `_card`."""
        card = tb.Frame(parent, bootstyle=LIGHT, padding=12)
        card.configure(borderwidth=1)
        row = tb.Frame(card); row.pack(fill=X, expand=YES)
        tb.Label(row, text=icon, font=("Segoe UI Emoji", 18)).pack(side=LEFT, padx=(0,10))
        textcol = tb.Frame(row); textcol.pack(side=LEFT, fill=X, expand=YES)
        tb.Label(textcol, text=title, font=("Segoe UI", 12, "bold")).pack(anchor=W)
        if subtitle:
            tb.Label(textcol, text=subtitle, bootstyle=SECONDARY).pack(anchor=W, pady=(2,0))
        return card

    def _cards_grid(parent, items, columns=2, pad=(10,10)):
        """Auto-generated docstring for `_cards_grid`."""
        grid = tb.Frame(parent); grid.pack(fill=X, expand=YES)
        r, c = 0, 0
        for title, subtitle, icon, cmd in items:
            holder = tb.Frame(grid, padding=2)
            holder.grid(row=r, column=c, padx=pad[0], pady=pad[1], sticky="nsew")
            crd = _card(holder, title, subtitle, icon)
            crd.pack(fill=BOTH, expand=YES)
            _bind_click_all(crd, cmd)  # click en toda la tarjeta
            c += 1
            if c >= columns:
                c = 0; r += 1
        for i in range(columns):
            grid.grid_columnconfigure(i, weight=1)

    build_generacion_automatica_view(app, frame_gen_auto, _bind_mousewheel)

    build_generacion_manual_view(app, frame_gen_manual, _bind_mousewheel)
    build_modificacion_matriz_view(frame_mod_matriz)
    build_alta_ciclos_view(frame_alta_cic)
    build_modificacion_ciclos_view(frame_mod_cic)

    # Mini-launcher
    _section_title(frame_gen_root, "Generación de Matrices", "Elige un modo para continuar:")
    _cards_grid(frame_gen_root, [
        ("Generación Automática", "Reglas, lotes, previsualización", "⚙️", lambda: go_section("GEN_AUTO", from_launcher=False)),
        ("Generación Manual",     "Captura paso a paso",            "✍️", lambda: go_section("GEN_MANUAL", from_launcher=False)),
    ], columns=2)

    # Launcher principal
    _section_title(frame_launcher, "Inicio", "Selecciona una acción para comenzar:")
    _cards_grid(frame_launcher, [
        ("Generación Automática", "Matrices por lote",               "⚙️", lambda: go_section("GEN_AUTO", from_launcher=True)),
        ("Generación Manual",     "Genera una matriz puntual",       "✍️", lambda: go_section("GEN_MANUAL", from_launcher=True)),
        ("Modificación de Matriz","Busca y edita matrices",          "📝", lambda: go_section("MOD_MATRIZ", from_launcher=True)),
        ("Alta de Ciclos",        "Crea ciclos nuevos",              "➕", lambda: go_section("ALTA_CICLOS", from_launcher=True)),
        ("Modificación de Ciclos","Actualiza ciclos existentes",     "✏️", lambda: go_section("MOD_CICLOS", from_launcher=True)),
        ("Pruebas",               "Flujo actual del sistema",        "🧪", lambda: go_section("PRUEBAS", from_launcher=True)),
    ], columns=2)

    # === SIDEBAR DERECHA: icono + texto ===
    nav_buttons = {}
    def _nav_item(parent, icon, label, sid):
        """Auto-generated docstring for `_nav_item`."""
        wrapper = tb.Frame(parent, padding=(0,0))
        wrapper.pack(fill=X, pady=4)
        # Sin 'anchor' (ttk no soporta 'anchor')
        btn = tb.Button(wrapper, text=f"{icon}  {label}", bootstyle=SECONDARY, takefocus=False,
                        padding=(12,10), command=lambda: go_section(sid, from_launcher=False))
        btn.pack(fill=X)
        nav_buttons[sid] = btn
        return btn

    tb.Label(sidebar, text="Menú", font=("Segoe UI", 12, "bold")).pack(anchor=W, padx=6, pady=(0,6))
    _nav_item(sidebar, "🏁", "Inicio", "LAUNCHER")
    tb.Separator(sidebar, bootstyle=SECONDARY).pack(fill=X, pady=8)
    _nav_item(sidebar, "⚙️", "Generación Automática", "GEN_AUTO")
    _nav_item(sidebar, "✍️", "Generación Manual",     "GEN_MANUAL")
    tb.Separator(sidebar, bootstyle=SECONDARY).pack(fill=X, pady=8)
    _nav_item(sidebar, "📝", "Modificación de Matriz", "MOD_MATRIZ")
    _nav_item(sidebar, "➕", "Alta de Ciclos",          "ALTA_CICLOS")
    _nav_item(sidebar, "✏️", "Modificación de Ciclos", "MOD_CICLOS")
    tb.Separator(sidebar, bootstyle=SECONDARY).pack(fill=X, pady=8)
    _nav_item(sidebar, "🧪", "Pruebas", "PRUEBAS")

    # === Navegación ===
    all_frames = {
        "GEN_ROOT": frame_gen_root,
        "GEN_AUTO": frame_gen_auto,
        "GEN_MANUAL": frame_gen_manual,
        "MOD_MATRIZ": frame_mod_matriz,
        "ALTA_CICLOS": frame_alta_cic,
        "MOD_CICLOS": frame_mod_cic,
        "PRUEBAS": frame_pruebas,
        "LAUNCHER": frame_launcher,
    }

    def _highlight_nav(section_id):
        """Auto-generated docstring for `_highlight_nav`."""
        for sid, b in nav_buttons.items():
            b.configure(bootstyle=PRIMARY if sid == section_id else SECONDARY)

    pruebas_ctx: Optional[PruebasViewContext] = None

    def show_section(section_id: str):
        """Auto-generated docstring for `show_section`."""
        for fr in all_frames.values():
            fr.pack_forget()
        all_frames.get(section_id, frame_pruebas).pack(fill=BOTH, expand=YES)
        _highlight_nav(section_id)
        if pruebas_ctx:
            if section_id == "PRUEBAS":
                pruebas_ctx.show_controls()
            else:
                pruebas_ctx.hide_controls()

    def go_section(section_id: str, from_launcher: bool = False):
        """Auto-generated docstring for `go_section`."""
        # Si el destino es INICIO, ocultar siempre el sidebar
        if section_id == "LAUNCHER":
            hide_sidebar()
            show_section("LAUNCHER")
            return
        # Si venimos desde el launcher (tarjeta), mostrar el sidebar
        if from_launcher:
            ensure_sidebar_visible()
        show_section(section_id)

    # === IMPORTANTE: redirigir 'body' al frame de PRUEBAS para no tocar el flujo actual ===
    pruebas_ctx = build_pruebas_view(
        app,
        frame_pruebas,
        controller,
        Messagebox,
        _bind_mousewheel,
        _format_elapsed,
        _format_timestamp,
        select_region_overlay,
        build_word,
        import_steps_to_confluence,
        open_capture_editor,
    )

    hide_sidebar()
    show_section("LAUNCHER")

    app.mainloop()

if __name__ == "__main__":
    run_gui()
