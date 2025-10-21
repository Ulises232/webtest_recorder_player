
"""Main Tkinter view for the desktop recorder desktop application."""

import os
import time
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import ttk, messagebox as Messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.controllers.main_controller import MainController
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus

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


def _prompt_login(root: tb.Window) -> Optional[AuthenticationResult]:
    """Show a modal login dialog and return the authenticated user if any."""

    root.update_idletasks()

    dialog = tb.Toplevel(root)
    dialog.title("Iniciar sesión")
    dialog.resizable(False, False)
    dialog.geometry("380x260")
    dialog.attributes("-topmost", True)
    dialog.withdraw()

    container = tb.Frame(dialog, padding=20)
    container.pack(fill=BOTH, expand=YES)

    tb.Label(container, text="Ingrese sus credenciales", font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0, 12))

    cached_credentials = controller.load_cached_credentials() or {}
    cached_username = cached_credentials.get("username", "").strip()
    cached_password = cached_credentials.get("password", "")

    username_var = tk.StringVar(value=cached_username)
    password_var = tk.StringVar(value=cached_password)
    status_var = tk.StringVar(value="Cargando usuarios activos...")

    display_to_username: dict[str, str] = {}
    username_to_display: dict[str, str] = {}
    username_widget_ref: dict[str, Optional[tk.Widget]] = {"widget": None}

    tb.Label(container, text="Usuario", font=("Segoe UI", 10, "bold")).pack(anchor=W)

    username_container = tb.Frame(container)
    username_container.pack(fill=X, pady=(0, 10))

    initial_entry = tb.Entry(username_container, textvariable=username_var)
    initial_entry.pack(fill=X)
    username_widget_ref["widget"] = initial_entry

    tb.Label(container, text="Contraseña", font=("Segoe UI", 10, "bold")).pack(anchor=W)
    password_entry = tb.Entry(container, textvariable=password_var, show="•")
    password_entry.pack(fill=X, pady=(0, 10))

    tb.Label(container, textvariable=status_var, bootstyle=WARNING).pack(anchor=W, pady=(0, 10))

    def _set_username_widget(widget: tk.Widget) -> None:
        """Remember the active username widget to manage focus later on."""

        username_widget_ref["widget"] = widget

    def _focus_username_widget() -> None:
        """Focus the current username widget if it is available."""

        widget = username_widget_ref.get("widget")
        if widget and widget.winfo_exists():
            widget.focus_set()

    def _enforce_geometry() -> None:
        """Ensure the dialog keeps a minimum size after layout updates."""

        dialog.update_idletasks()
        required_width = max(380, dialog.winfo_reqwidth())
        required_height = max(260, dialog.winfo_reqheight())
        dialog.minsize(required_width, required_height)
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        pos_x = max(0, (screen_width - required_width) // 2)
        pos_y = max(0, (screen_height - required_height) // 3)
        dialog.geometry(f"{required_width}x{required_height}+{pos_x}+{pos_y}")

    dialog_visibility: dict[str, bool] = {"shown": False}

    def _ensure_dialog_shown() -> None:
        """Display and focus the dialog once it has been prepared."""

        _enforce_geometry()
        dialog.update()
        if not dialog.winfo_ismapped():
            dialog.deiconify()
        if not dialog_visibility["shown"]:
            try:
                dialog.wait_visibility()
            except tk.TclError:
                pass
            dialog_visibility["shown"] = True
        dialog.lift()
        dialog.focus_force()

    def apply_user_choices(choices: list[tuple[str, str]], error_message: Optional[str]) -> None:
        """Populate the username input once the user list has been resolved."""

        if not dialog.winfo_exists():
            return

        display_to_username.clear()
        username_to_display.clear()

        for child in username_container.winfo_children():
            child.destroy()

        if choices:
            display_values: list[str] = []
            for username, display_name in choices:
                formatted_name = (display_name or "").strip()
                if not formatted_name:
                    formatted_name = username
                elif formatted_name.lower() != username.lower():
                    formatted_name = f"{formatted_name} ({username})"
                display_values.append(formatted_name)
                display_to_username[formatted_name] = username
                username_to_display.setdefault(username, formatted_name)

            username_combo = tb.Combobox(
                username_container,
                textvariable=username_var,
                values=display_values,
                state="readonly",
            )
            username_combo.pack(fill=X)
            _set_username_widget(username_combo)

            if cached_username and cached_username in username_to_display:
                username_var.set(username_to_display[cached_username])
            elif display_values:
                username_var.set(display_values[0])
        else:
            username_entry = tb.Entry(username_container, textvariable=username_var)
            username_entry.pack(fill=X)
            _set_username_widget(username_entry)
            if cached_username:
                username_var.set(cached_username)

        status_var.set(error_message or "")
        _enforce_geometry()
        _ensure_dialog_shown()

        if cached_password:
            password_entry.focus_set()
        else:
            _focus_username_widget()

    result: dict[str, Optional[AuthenticationResult]] = {"auth": None}

    def submit(_event=None):
        """Trigger the authentication flow using the typed credentials."""

        selected_value = username_var.get().strip()
        username = display_to_username.get(selected_value, selected_value)
        password = password_var.get()
        if not username or not password:
            status_var.set("Capture usuario y contraseña para continuar.")
            return

        auth_result = controller.authenticate_user(username, password)
        status = auth_result.status
        if status == AuthenticationStatus.AUTHENTICATED:
            result["auth"] = auth_result
            dialog.destroy()
            return

        password_var.set("")
        if status == AuthenticationStatus.RESET_REQUIRED:
            Messagebox.show_error(
                "Debes actualizar la contraseña en el sistema principal antes de usar esta aplicación.",
                "Cambio de contraseña requerido",
            )
            status_var.set("Actualiza tu contraseña en el sistema principal.")
            return

        if status == AuthenticationStatus.PASSWORD_REQUIRED:
            Messagebox.show_error(
                "El usuario no tiene contraseña definida. Ingresa al sistema principal para establecerla.",
                "Contraseña requerida",
            )
            status_var.set("Define una contraseña en el sistema principal y vuelve a intentar.")
            return

        if status == AuthenticationStatus.INACTIVE:
            Messagebox.show_error(auth_result.message, "Usuario inactivo")
            status_var.set("La cuenta está desactivada.")
            return

        if status == AuthenticationStatus.ERROR:
            Messagebox.show_error(auth_result.message, "Error al iniciar sesión")
            status_var.set("Revisa la conexión a la base de datos e intenta nuevamente.")
            return

        status_var.set("Usuario o contraseña inválidos.")

    def cancel() -> None:
        """Close the dialog without authenticating."""

        result["auth"] = None
        dialog.destroy()

    btn_row = tb.Frame(container)
    btn_row.pack(fill=X, pady=(12, 0))

    tb.Button(btn_row, text="Cancelar", command=cancel, bootstyle=SECONDARY).pack(side=RIGHT, padx=(6, 0))
    tb.Button(btn_row, text="Acceder", command=submit, bootstyle=PRIMARY).pack(side=RIGHT)

    dialog.bind("<Return>", submit)
    dialog.protocol("WM_DELETE_WINDOW", cancel)

    try:
        choices, error_message = controller.list_active_users()
    except Exception as exc:  # pragma: no cover - protege contra errores inesperados
        choices = []
        error_message = str(exc)

    apply_user_choices(choices, error_message)

    dialog.grab_set()

    root.wait_window(dialog)
    return result["auth"]


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

    auth_result = _prompt_login(app)
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

    session_info = controller.get_authenticated_user()
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

    # Placeholders
    def _placeholder(parent, title, desc):
        """Auto-generated docstring for `_placeholder`."""
        _section_title(parent, title, desc)

    # === GENERACIÓN AUTOMÁTICA — UI ===
    for _w in frame_gen_auto.winfo_children():
        _w.destroy()

    import os, csv, itertools, datetime, re
    import tkinter as tk
    from tkinter import messagebox

    ga_matrix_name = tk.StringVar(value="")
    ga_status      = tk.StringVar(value="Listo.")
    _variables     = []
    _preview_rows  = []

    top = tb.Labelframe(frame_gen_auto, text="Datos de la matriz", padding=10); top.pack(fill=X)
    tb.Label(top, text="Nombre de la matriz").grid(row=0, column=0, sticky="w", padx=(2,8), pady=6)
    ent_name = tb.Entry(top, textvariable=ga_matrix_name, width=40); ent_name.grid(row=0, column=1, sticky="we", pady=6)
    top.grid_columnconfigure(1, weight=1)

    cap = tb.Labelframe(frame_gen_auto, text="Captura de variables", padding=10); cap.pack(fill=X, pady=(8,0))
    tb.Label(cap, text="Variable").grid(row=0, column=0, sticky="w")
    tb.Label(cap, text="Puede valer (separado por comas)").grid(row=0, column=1, sticky="w")
    _var_name = tk.StringVar(value=""); _var_vals = tk.StringVar(value="")
    ent_var = tb.Entry(cap, textvariable=_var_name, width=24); ent_var.grid(row=1, column=0, sticky="we", padx=(0,8), pady=(0,8))
    ent_vals = tb.Entry(cap, textvariable=_var_vals, width=50); ent_vals.grid(row=1, column=1, sticky="we", padx=(0,8), pady=(0,8))
    def _add_variable():
        """Auto-generated docstring for `_add_variable`."""
        name = _var_name.get().strip()
        vals = [v.strip() for v in _var_vals.get().split(",") if v.strip()]
        if not name: messagebox.showwarning("Falta dato", "Debes capturar el nombre de la variable."); return
        if not vals: messagebox.showwarning("Falta dato", "Debes capturar al menos un valor para la variable."); return
        if any(v['name'].lower()==name.lower() for v in _variables):
            messagebox.showwarning("Duplicado", f"La variable '{name}' ya existe."); return
        _variables.append({'name': name, 'values': vals})
        _var_name.set(""); _var_vals.set(""); _render_variables(); ent_var.focus_set()
    tb.Button(cap, text="Agregar variable", bootstyle=PRIMARY, command=_add_variable).grid(row=1, column=2, sticky="w")
    cap.grid_columnconfigure(0, weight=1); cap.grid_columnconfigure(1, weight=4)

    vars_box = tb.Frame(cap); vars_box.grid(row=2, column=0, columnspan=3, sticky="we")

    def _render_variables():
        """Auto-generated docstring for `_render_variables`."""
        for w in vars_box.winfo_children(): w.destroy()
        if not _variables:
            tb.Label(vars_box, text="(Sin variables)", bootstyle=SECONDARY).pack(anchor="w"); return
        for idx, var in enumerate(_variables):
            row = tb.Frame(vars_box); row.pack(fill=X, pady=4)
            tb.Label(row, text=f"{var['name']}", font=("Segoe UI",10,"bold")).pack(side=LEFT)
            tb.Label(row, text="  |  ").pack(side=LEFT)
            tb.Label(row, text=", ".join(var['values']), bootstyle=SECONDARY).pack(side=LEFT)
            tb.Button(row, text="✏️ Editar", bootstyle=SECONDARY, command=lambda i=idx: _edit_var(i)).pack(side=RIGHT, padx=4)
            tb.Button(row, text="❌ Eliminar", bootstyle=DANGER, command=lambda i=idx: _del_var(i)).pack(side=RIGHT, padx=4)

    def _edit_var(i):
        """Auto-generated docstring for `_edit_var`."""
        var = _variables[i]
        win = tk.Toplevel(app); win.title(f"Editar {var['name']}"); win.geometry("420x200")
        n = tk.StringVar(value=var['name']); v = tk.StringVar(value=", ".join(var['values']))
        tb.Label(win, text="Variable").pack(anchor="w", padx=10, pady=(10,2)); tb.Entry(win, textvariable=n).pack(fill=X, padx=10)
        tb.Label(win, text="Valores (coma)").pack(anchor="w", padx=10, pady=(10,2)); tb.Entry(win, textvariable=v).pack(fill=X, padx=10)
        def _ok():
            """Auto-generated docstring for `_ok`."""
            name = n.get().strip(); vals = [x.strip() for x in v.get().split(",") if x.strip()]
            if not name or not vals: messagebox.showwarning("Faltan datos","Nombre y valores no pueden quedar vacíos."); return
            if any(j!=i and _variables[j]['name'].lower()==name.lower() for j in range(len(_variables))):
                messagebox.showwarning("Duplicado", f"Ya existe una variable con nombre '{name}'."); return
            _variables[i] = {'name': name, 'values': vals}; _render_variables(); win.destroy()
        tb.Button(win, text="Guardar", bootstyle=PRIMARY, command=_ok).pack(side=RIGHT, padx=10, pady=12)
        tb.Button(win, text="Cancelar", bootstyle=SECONDARY, command=win.destroy).pack(side=RIGHT, pady=12)

    def _del_var(i):
        """Auto-generated docstring for `_del_var`."""
        if messagebox.askyesno("Confirmar", f"¿Eliminar variable '{_variables[i]['name']}'?"):
            _variables.pop(i); _render_variables()

    _render_variables()

    tmpl = tb.Labelframe(frame_gen_auto, text="Plantilla de caso de prueba", padding=10); tmpl.pack(fill=X, pady=(8,0))
    _rules = tb.Labelframe(frame_gen_auto, text="Reglas de invalidez (Var=Val && Var=Val => inválido)", padding=10); _rules.pack(fill=X, pady=(8,0))
    tmpl_text  = tk.Text(tmpl, height=3); tmpl_text.pack(fill=X)
    rules_text = tk.Text(_rules, height=4); rules_text.pack(fill=X)

    def _default_template():
        """Auto-generated docstring for `_default_template`."""
        if not _variables: return "Validar el sistema"
        parts = [f"{v['name']} es {{{v['name']}}}" for v in _variables]
        return "Validar el sistema cuando " + ", ".join(parts)

    def _parse_rules(text):
        """Auto-generated docstring for `_parse_rules`."""
        import re; rules = []; lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines:
            if "=>" not in line: continue
            conds, result = [p.strip() for p in line.split("=>", 1)]
            if not re.search(r'inv[aá]lido', result, flags=re.IGNORECASE): continue
            parts = re.split(r'(&&|\|\|)', conds); terms = [p.strip() for p in parts if p.strip()]
            cond_terms, ops = [], []
            for t in terms:
                if t in ("&&","||"): ops.append(t)
                else: key, _, val = t.partition("="); cond_terms.append({'key': key.strip(), 'val': val.strip()})
            rules.append({'parts': cond_terms, 'ops': ops})
        return rules

    def _evaluate_rules(rules, row_vals, var_order):
        """Auto-generated docstring for `_evaluate_rules`."""
        def term_value(term):
            """Auto-generated docstring for `term_value`."""
            try: idx = var_order.index(term['key'])
            except ValueError: return False
            return row_vals[idx] == term['val']
        for r in rules:
            val = None
            for i, term in enumerate(r['parts']):
                t_val = term_value(term)
                if val is None: val = t_val
                else:
                    op = r['ops'][i-1] if i-1 < len(r['ops']) else '&&'
                    val = (val and t_val) if op=='&&' else (val or t_val)
            if val: return True
        return False

    preview = tb.Labelframe(frame_gen_auto, text="Vista previa", padding=10); preview.pack(fill=BOTH, expand=True, pady=(8,0))
    btn_row = tb.Frame(preview); btn_row.pack(fill=X)
    tb.Button(btn_row, text="Generar vista previa", bootstyle=INFO, command=lambda: _generate_preview()).pack(side=LEFT)

    count_lbl = tb.Label(preview, text="", bootstyle=SECONDARY); count_lbl.pack(anchor="w", pady=(6,6))
    tv_wrap = tb.Frame(preview); tv_wrap.pack(fill=BOTH, expand=True)
    tree = ttk.Treeview(tv_wrap, show="headings", height=12)
    vsb  = ttk.Scrollbar(tv_wrap, orient="vertical", command=tree.yview); tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True); vsb.pack(side=RIGHT, fill=Y)
    _bind_mousewheel(tree, tree.yview)

    def _clear_tree_auto():
        """Auto-generated docstring for `_clear_tree_auto`."""
        for c in tree['columns']:
            try: tree.heading(c, text="")
            except Exception: pass
        tree.delete(*tree.get_children()); tree['columns'] = ()

    def _reset_ga_form(confirm=True):
        """Auto-generated docstring for `_reset_ga_form`."""
        has_data = bool(_variables or tree.get_children(""))
        if confirm and has_data:
            if not messagebox.askyesno("Nueva matriz", "¿Limpiar la captura y comenzar otra matriz?"): return
        _variables.clear(); _render_variables()
        ga_matrix_name.set("")
        tmpl_text.delete("1.0","end"); rules_text.delete("1.0","end")
        _clear_tree_auto(); count_lbl.configure(text="")
        ga_status.set("Listo.")
        try: ent_name.focus_set()
        except Exception: pass

    def _generate_preview():
        """Auto-generated docstring for `_generate_preview`."""
        missing = []
        if not ga_matrix_name.get().strip(): missing.append("Nombre de la matriz")
        if not _variables: missing.append("Al menos una variable")
        else:
            for v in _variables:
                if not v['values']: missing.append(f"Valores de {v['name']}")
        if missing: messagebox.showwarning("Faltan datos", "Faltan: " + ", ".join(missing)); return

        var_names = [v['name'] for v in _variables]
        template  = tmpl_text.get("1.0","end").strip() or _default_template()
        rules     = _parse_rules(rules_text.get("1.0","end"))

        combos = list(itertools.product(*[v['values'] for v in _variables])) if _variables else []
        _preview_rows.clear()
        valid_count = invalid_count = 0

        for idx, combo in enumerate(combos, start=1):
            testcase = template
            for vn, vv in zip(var_names, combo): testcase = testcase.replace("{"+vn+"}", str(vv))
            is_invalid = _evaluate_rules(rules, list(combo), var_names)
            is_valid_text = "No" if is_invalid else "Sí"
            if is_invalid: invalid_count += 1
            else: valid_count += 1
            row = [f"CASO {idx}", *combo, testcase, is_valid_text, ""]
            _preview_rows.append(row)

        _clear_tree_auto()
        cols = ["NUMERO CASO DE PRUEBA", *var_names, "Caso de prueba", "¿Válido?", "PROCESAR"]
        tree['columns'] = cols
        for c in cols: tree.heading(c, text=c); tree.column(c, width=160, anchor="w")
        for r in _preview_rows: tree.insert("", "end", values=r)

        count_lbl.configure(text=f"Total: {len(_preview_rows)}  •  Válidos: {valid_count}  •  Inválidos: {invalid_count}")
        ga_status.set("Vista previa generada.")

    save_toolbar = tb.Frame(frame_gen_auto); save_toolbar.pack(fill=X, pady=(8,0))
    tb.Button(save_toolbar, text="Descargar CSV", bootstyle=PRIMARY, command=lambda: _save_csv()).pack(side=LEFT)
    tb.Button(save_toolbar, text="Generar otra matriz", bootstyle=SECONDARY, command=lambda: _reset_ga_form(True)).pack(side=LEFT, padx=(8,0))
    tb.Label(save_toolbar, textvariable=ga_status, bootstyle=SECONDARY).pack(side=LEFT, padx=12)

    def _sanitize_filename(name: str) -> str:
        """Auto-generated docstring for `_sanitize_filename`."""
        name = re.sub(r'[\\/:*?"<>|]+', "_", name.strip()); return name

    def _save_csv():
        """Auto-generated docstring for `_save_csv`."""
        rows = [tree.item(ch, 'values') for ch in tree.get_children("")]
        if not rows:
            messagebox.showwarning("Sin datos", "Primero genera la vista previa."); return
        base = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(base, "template_matrices"); os.makedirs(target_dir, exist_ok=True)
        dt = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); fname = f"{_sanitize_filename(ga_matrix_name.get())}_{dt}.csv"
        fpath = os.path.join(target_dir, fname); cols = tree['columns']
        try:
            with open(fpath, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(cols); w.writerows(rows)
            ga_status.set(f"Guardado: {fpath}"); messagebox.showinfo("Éxito", f"Matriz guardada en:\n{fpath}")
        except Exception as ex:
            ga_status.set("ERROR al guardar CSV"); messagebox.showerror("Error", f"No se pudo guardar el CSV:\n{ex}")
    # === GENERACIÓN MANUAL — UI ===
    for _w in frame_gen_manual.winfo_children():
        _w.destroy()

    import os, csv, datetime, re
    import tkinter as tk
    from tkinter import messagebox, filedialog

    gm_matrix_name = tk.StringVar(value="")
    gm_mode = tk.StringVar(value="")
    gm_status = tk.StringVar(value="Elige cómo quieres trabajar (importar o captura manual).")
    gm_case_counter = tk.IntVar(value=1)
    gm_dyncols = []

    def _sanitize_filename(name: str) -> str:
        """Auto-generated docstring for `_sanitize_filename`."""
        name = re.sub(r'[\\/:*?"<>|]+', "_", name.strip()); return name

    def _normalize_header(s: str) -> str:
        """Auto-generated docstring for `_normalize_header`."""
        s = (s or "").strip().lower()
        for a,b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","¿":"", "?":""}.items():
            s = s.replace(a,b)
        s = re.sub(r'\s+', ' ', s)
        return s

    REQ_LEFT  = "numero caso de prueba"
    REQ_RIGHT = "caso de prueba"
    REQ_FIXED_TAIL = ["¿válido?", "procesar"]

    def _headers_ok(headers):
        """Auto-generated docstring for `_headers_ok`."""
        norm = [_normalize_header(h) for h in headers]
        fixed_norm = [_normalize_header(h) for h in REQ_FIXED_TAIL]
        if REQ_LEFT not in norm: return False, "Falta columna 'NUMERO CASO DE PRUEBA'"
        if REQ_RIGHT not in norm: return False, "Falta columna 'Caso de prueba'"
        miss = [REQ_FIXED_TAIL[i] for i,h in enumerate(fixed_norm) if h not in norm]
        if miss: return False, f"Faltan columnas: {', '.join(miss)}"
        if norm.index(REQ_LEFT) >= norm.index(REQ_RIGHT):
            return False, "'NUMERO CASO DE PRUEBA' debe ir antes que 'Caso de prueba'"
        return True, ""

    def _split_headers(headers):
        """Auto-generated docstring for `_split_headers`."""
        norm = [_normalize_header(h) for h in headers]
        li = norm.index(REQ_LEFT); ri = norm.index(REQ_RIGHT)
        left = [headers[li]]; dyn = headers[li+1:ri]; tail = headers[ri:]
        return left, dyn, tail

    def _tree_set_columns(tree, headers):
        """Auto-generated docstring for `_tree_set_columns`."""
        tree['columns'] = headers
        for c in headers:
            try: tree.heading(c, text=c); tree.column(c, width=160, anchor="w")
            except Exception: pass

    def _renumber_cases(tree):
        """Auto-generated docstring for `_renumber_cases`."""
        cols = list(tree['columns'])
        norm = [_normalize_header(h) for h in cols]
        if REQ_LEFT not in norm: return
        idx = norm.index(REQ_LEFT)
        for i, item in enumerate(tree.get_children(""), start=1):
            vals = list(tree.item(item, 'values'))
            if idx < len(vals):
                vals[idx] = f"CASO {i}"
                tree.item(item, values=vals)

    def _read_csv_any_encoding(path):
        """Auto-generated docstring for `_read_csv_any_encoding`."""
        encs = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        last_err = None
        for enc in encs:
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    sample = f.read(4096); f.seek(0)
                    delim = ","
                    if sample.count(";") > sample.count(",") and ";" in sample: delim = ";"
                    elif "\t" in sample and sample.count("\t") > 0: delim = "\t"
                    reader = csv.reader(f, delimiter=delim)
                    headers = next(reader, [])
                    rows = list(reader)
                    return headers, rows
            except Exception as ex:
                last_err = ex; continue
        raise last_err if last_err else Exception("No se pudo leer el CSV.")

    # Selector de modo
    mode_box = tb.Labelframe(frame_gen_manual, text="¿Cómo deseas trabajar?", padding=10); mode_box.pack(fill=X)
    tb.Radiobutton(mode_box, text="Importar CSV/XLSX", variable=gm_mode, value="import", command=lambda: _show_mode()).pack(side=LEFT, padx=(0,12))
    tb.Radiobutton(mode_box, text="Captura manual",   variable=gm_mode, value="manual", command=lambda: _show_mode()).pack(side=LEFT)

    status_lbl = tb.Label(frame_gen_manual, textvariable=gm_status, bootstyle=SECONDARY)
    status_lbl.pack(anchor="w", padx=6, pady=(6,0))

    top = tb.Labelframe(frame_gen_manual, text="Datos de la matriz", padding=10)
    tb.Label(top, text="Nombre de la matriz").grid(row=0, column=0, sticky="w", padx=(2,8), pady=6)
    tb.Entry(top, textvariable=gm_matrix_name, width=40).grid(row=0, column=1, sticky="we", pady=6)
    top.grid_columnconfigure(1, weight=1)

    # Barra única (evita duplicados)
    gm_toolbar = tb.Frame(frame_gen_manual)
    def _build_toolbar():
        """Auto-generated docstring for `_build_toolbar`."""
        for w in gm_toolbar.winfo_children(): w.destroy()
        tb.Button(gm_toolbar, text="Guardar CSV", bootstyle=PRIMARY,
                command=lambda: _save_from_tree(imp_tree if gm_mode.get()=='import' else man_tree)).pack(side=LEFT)
        tb.Button(gm_toolbar, text="Nueva matriz", bootstyle=SECONDARY,
                command=lambda: _gm_reset_form(True)).pack(side=LEFT, padx=(8,0))
    _build_toolbar()

    def _save_from_tree(tree):
        """Auto-generated docstring for `_save_from_tree`."""
        rows = [tree.item(ch, 'values') for ch in tree.get_children("")]
        if not rows:
            messagebox.showwarning("Sin datos", "No hay filas para guardar."); return
        if not gm_matrix_name.get().strip():
            messagebox.showwarning("Falta nombre", "Captura el nombre de la matriz."); return
        base = os.path.dirname(os.path.abspath(__file__)); target_dir = os.path.join(base, "template_matrices"); os.makedirs(target_dir, exist_ok=True)
        dt = datetime.datetime.now().strftime("%Y%m%d_%H%M%S"); fname = f"{_sanitize_filename(gm_matrix_name.get())}_{dt}.csv"
        fpath = os.path.join(target_dir, fname)
        try:
            with open(fpath, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(tree['columns'])
                for r in rows: w.writerow(r)
            gm_status.set(f"Guardado: {fpath}"); messagebox.showinfo("Éxito", f"Matriz guardada en:\n{fpath}")
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo guardar el CSV:\n{ex}")

    def _gm_clear_tree(tree):
        """Auto-generated docstring for `_gm_clear_tree`."""
        if not isinstance(tree, ttk.Treeview): return
        for c in tree['columns']:
            try: tree.heading(c, text="")
            except Exception: pass
        tree.delete(*tree.get_children()); tree['columns'] = ()

    def _gm_reset_form(confirm=True):
        """Auto-generated docstring for `_gm_reset_form`."""
        has_rows = False
        try: has_rows = bool(imp_tree.get_children("") or man_tree.get_children(""))
        except Exception: pass
        has_dyn = bool(gm_dyncols); has_name = bool(gm_matrix_name.get().strip())
        if confirm and (has_rows or has_dyn or has_name):
            if not messagebox.askyesno("Nueva matriz", "¿Limpiar todo para comenzar una nueva matriz?"): return
        gm_matrix_name.set(""); gm_case_counter.set(1); gm_dyncols.clear()
        try: _gm_clear_tree(imp_tree); _gm_clear_tree(man_tree)
        except Exception: pass
        gm_status.set("Elige cómo quieres trabajar (importar o captura manual).")
        gm_mode.set(""); _show_mode()

    import_frame = tb.Frame(frame_gen_manual)
    manual_frame = tb.Frame(frame_gen_manual)

    # --- Importar ---
    imp_top = tb.Labelframe(import_frame, text="Importar archivo", padding=10)
    imp_path = tk.StringVar(value="")
    tb.Entry(imp_top, textvariable=imp_path).grid(row=0, column=0, sticky="we", padx=(0,6))
    tb.Button(imp_top, text="Examinar...", bootstyle=SECONDARY, command=lambda: _browse_import()).grid(row=0, column=1)
    imp_top.grid_columnconfigure(0, weight=1)
    imp_info = tb.Label(import_frame, text="Selecciona un CSV o XLSX con estructura compatible.", bootstyle=SECONDARY)
    imp_prev = tb.Labelframe(import_frame, text="Vista previa (importado)", padding=10)
    imp_tv_wrap = tb.Frame(imp_prev)
    imp_tree = ttk.Treeview(imp_tv_wrap, show="headings", height=10)
    imp_vsb = ttk.Scrollbar(imp_tv_wrap, orient="vertical", command=imp_tree.yview); imp_tree.configure(yscrollcommand=imp_vsb.set)
    imp_tree.pack(side=LEFT, fill=BOTH, expand=True); imp_vsb.pack(side=RIGHT, fill=Y)
    _bind_mousewheel(imp_tree, imp_tree.yview)
    imp_actions = tb.Frame(import_frame)

    def _imp_delete_selected():
        """Auto-generated docstring for `_imp_delete_selected`."""
        sel = imp_tree.selection()
        if not sel: return
        if not messagebox.askyesno("Eliminar", f"¿Eliminar {len(sel)} fila(s) seleccionada(s)?"): return
        for it in sel: imp_tree.delete(it)
        _renumber_cases(imp_tree); gm_status.set("Fila(s) eliminada(s).")

    def _imp_clear_all():
        """Auto-generated docstring for `_imp_clear_all`."""
        if not imp_tree.get_children(""): return
        if not messagebox.askyesno("Vaciar tabla", "¿Vaciar todas las filas importadas?"): return
        imp_tree.delete(*imp_tree.get_children()); gm_status.set("Tabla vacía.")

    imp_tree.bind("<Delete>", lambda e: (_imp_delete_selected(), "break"))

    tb.Button(imp_actions, text="Eliminar fila", bootstyle=DANGER, command=_imp_delete_selected).pack(side=LEFT)
    tb.Button(imp_actions, text="Vaciar tabla", bootstyle=SECONDARY, command=_imp_clear_all).pack(side=LEFT, padx=(8,0))

    # --- Manual ---
    cols_bar = tb.Labelframe(manual_frame, text="Columnas dinámicas", padding=10)
    _gm_newcol = tk.StringVar(value="")
    tb.Entry(cols_bar, textvariable=_gm_newcol, width=28).pack(side=LEFT)
    def _add_dyncol_and_refresh():
        """Auto-generated docstring for `_add_dyncol_and_refresh`."""
        name = _gm_newcol.get().strip()
        if not name: return
        if name in gm_dyncols: messagebox.showwarning("Duplicado", f"La columna '{name}' ya existe."); return
        gm_dyncols.append(name); _gm_newcol.set("")
        _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()
    tb.Button(cols_bar, text="Agregar columna", bootstyle=SECONDARY, command=_add_dyncol_and_refresh).pack(side=LEFT, padx=(8,0))
    tb.Button(cols_bar, text="Cargar desde plantilla (CSV)", bootstyle=SECONDARY, command=lambda: _load_dyncols_from_template()).pack(side=LEFT, padx=(8,0))

    chips_holder = tb.Frame(cols_bar); chips_holder.pack(fill=X, pady=(8,0))

    def _render_dynchips():
        """Auto-generated docstring for `_render_dynchips`."""
        for w in chips_holder.winfo_children(): w.destroy()
        if not gm_dyncols:
            tb.Label(chips_holder, text="(Sin columnas dinámicas)", bootstyle=SECONDARY).pack(anchor="w"); return
        for i, col in enumerate(gm_dyncols):
            chip = tb.Frame(chips_holder, bootstyle=SECONDARY); chip.pack(side=LEFT, padx=4)
            tb.Label(chip, text=col).pack(side=LEFT, padx=(6,2), pady=2)
            def _make_cmd(name=col):
                """Auto-generated docstring for `_make_cmd`."""
                def _cmd():
                    """Auto-generated docstring for `_cmd`."""
                    if man_tree.get_children(""):
                        if not messagebox.askyesno("Eliminar columna", f"Hay filas capturadas.\n¿Eliminar la columna '{name}' y ajustar la tabla?"): return
                    old = list(gm_dyncols); new_dyn = [c for c in old if c != name]
                    rows = [man_tree.item(ch, 'values') for ch in man_tree.get_children("")]
                    gm_dyncols.clear(); gm_dyncols.extend(new_dyn)
                    _man_build_tree_headers()
                    if rows:
                        man_tree.delete(*man_tree.get_children(""))
                        old_dyn_len = len(old)
                        for vals in rows:
                            base = [vals[0]]; old_dyn_vals = list(vals[1:1+old_dyn_len]); rest = list(vals[1+old_dyn_len:])
                            mapped = [old_dyn_vals[old.index(c)] for c in new_dyn]
                            man_tree.insert("", "end", values=base+mapped+rest)
                    _rebuild_manual_inputs(); _render_dynchips()
                return _cmd
            tb.Button(chip, text="✕", bootstyle=DANGER, width=2, command=_make_cmd()).pack(side=LEFT, padx=(2,6), pady=2)

    man_cap = tb.Labelframe(manual_frame, text="Captura de filas", padding=10)
    scroll_wrap = tb.Frame(man_cap)
    canvas = tk.Canvas(scroll_wrap, height=220, highlightthickness=0)
    vscroll = ttk.Scrollbar(scroll_wrap, orient="vertical", command=canvas.yview); canvas.configure(yscrollcommand=vscroll.set)
    canvas.pack(side=LEFT, fill=X, expand=True); vscroll.pack(side=RIGHT, fill=Y)
    _bind_mousewheel(canvas, canvas.yview)

    inner = tb.Frame(canvas); inner_id = canvas.create_window((0,0), window=inner, anchor="nw")
    def _on_inner_config(event):
        """Auto-generated docstring for `_on_inner_config`."""
        canvas.configure(scrollregion=canvas.bbox("all"))
        try: canvas.itemconfig(inner_id, width=canvas.winfo_width())
        except Exception: pass
    inner.bind("<Configure>", _on_inner_config)
    def _on_canvas_config(event):
        """Auto-generated docstring for `_on_canvas_config`."""
        try: canvas.itemconfig(inner_id, width=event.width)
        except Exception: pass
    canvas.bind("<Configure>", _on_canvas_config)

    btns = tb.Frame(man_cap)

    man_prev = tb.Labelframe(manual_frame, text="Vista previa (manual)", padding=10)
    man_tv_wrap = tb.Frame(man_prev)
    man_tree = ttk.Treeview(man_tv_wrap, show="headings", height=10)
    man_vsb = ttk.Scrollbar(man_tv_wrap, orient="vertical", command=man_tree.yview); man_tree.configure(yscrollcommand=man_vsb.set)
    man_tree.pack(side=LEFT, fill=BOTH, expand=True); man_vsb.pack(side=RIGHT, fill=Y)
    _bind_mousewheel(man_tree, man_tree.yview)
    man_actions = tb.Frame(manual_frame)

    def _man_build_tree_headers():
        """Auto-generated docstring for `_man_build_tree_headers`."""
        headers = ["NUMERO CASO DE PRUEBA", *gm_dyncols, "Caso de prueba", "¿Válido?", "PROCESAR"]
        man_tree.delete(*man_tree.get_children()); _tree_set_columns(man_tree, headers)

    def _rebuild_manual_inputs():
        """Auto-generated docstring for `_rebuild_manual_inputs`."""
        for w in inner.winfo_children(): w.destroy()
        row = 0
        tb.Label(inner, text="NUMERO CASO DE PRUEBA").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        case_no_var = tk.StringVar(value=f"CASO {gm_case_counter.get()}")
        tb.Label(inner, textvariable=case_no_var).grid(row=row, column=1, sticky="w")
        tb.Label(inner, text="Siguiente #").grid(row=row, column=2, sticky="e", padx=(12,4))
        try: sb = ttk.Spinbox(inner, from_=1, to=1000000, textvariable=gm_case_counter, width=8)
        except Exception: sb = tk.Spinbox(inner, from_=1, to=1000000, textvariable=gm_case_counter, width=8)
        sb.grid(row=row, column=3, sticky="w")
        # Botón superior agregar fila (visible)
        def _add_row():
            """Auto-generated docstring for `_add_row`."""
            missing = [c for c in gm_dyncols if not col_vars[c].get().strip()]
            if not case_txt.get().strip(): missing.append("Caso de prueba")
            if missing: messagebox.showwarning("Faltan datos", "Completa: " + ", ".join(missing)); return
            case_no = f"CASO {gm_case_counter.get()}"; gm_case_counter.set(gm_case_counter.get()+1)
            row_vals = [case_no] + [col_vars[c].get().strip() for c in gm_dyncols] + [case_txt.get().strip(), valid_var.get(), proc_var.get().strip()]
            man_tree.insert("", "end", values=row_vals); gm_status.set(f"Fila agregada ({case_no})")
            case_no_var.set(f"CASO {gm_case_counter.get()}"); case_txt.set(""); proc_var.set(""); val_combo.set("Sí")
            _renumber_cases(man_tree)
        tb.Button(inner, text="Agregar fila", bootstyle=PRIMARY, command=_add_row).grid(row=row, column=4, sticky="w", padx=(12,0))
        row += 1

        col_vars = {}
        for c in gm_dyncols:
            tb.Label(inner, text=c).grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
            v = tk.StringVar(value=""); col_vars[c] = v
            tb.Entry(inner, textvariable=v).grid(row=row, column=1, sticky="we", padx=(0,8), pady=4)
            row += 1
        inner.grid_columnconfigure(1, weight=1)

        tb.Label(inner, text="Caso de prueba").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        case_txt = tk.StringVar(value=""); tb.Entry(inner, textvariable=case_txt).grid(row=row, column=1, sticky="we", pady=4); row += 1

        tb.Label(inner, text="¿Válido?").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        valid_var = tk.StringVar(value="Sí"); val_combo = ttk.Combobox(inner, textvariable=valid_var, values=["Sí","No"], state="readonly", width=10)
        val_combo.grid(row=row, column=1, sticky="w", pady=4); row += 1

        tb.Label(inner, text="PROCESAR").grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)
        proc_var = tk.StringVar(value=""); tb.Entry(inner, textvariable=proc_var, width=10).grid(row=row, column=1, sticky="w", pady=4); row += 1

        for w in btns.winfo_children(): w.destroy()
        def _clear_inputs():
            """Auto-generated docstring for `_clear_inputs`."""
            for c in gm_dyncols:
                try: col_vars[c].set("")
                except Exception: pass
            case_txt.set(""); val_combo.set("Sí"); proc_var.set("")
        tb.Button(btns, text="Agregar fila", bootstyle=PRIMARY, command=_add_row).pack(side=LEFT)
        tb.Button(btns, text="Limpiar entradas", bootstyle=SECONDARY, command=_clear_inputs).pack(side=LEFT, padx=(8,0))

    def _browse_import():
        """Auto-generated docstring for `_browse_import`."""
        path = filedialog.askopenfilename(filetypes=[("CSV o Excel","*.csv *.xlsx *.xls"),("Todos","*.*")])
        if not path: return
        imp_path.set(path); _load_import(path)

    def _load_import(path):
        """Auto-generated docstring for `_load_import`."""
        ext = os.path.splitext(path)[1].lower()
        rows = []; headers = []
        try:
            if ext == ".csv":
                headers, rows = _read_csv_any_encoding(path)
            elif ext in (".xlsx",".xls"):
                try: import openpyxl
                except Exception:
                    messagebox.showerror("XLSX no soportado", "Para importar XLSX/XLS instala 'openpyxl' o conviértelo a CSV."); return
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                ws = wb.active
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    vals = [("" if c is None else str(c)) for c in row]
                    if i == 0: headers = vals
                    else: rows.append(vals)
            else:
                messagebox.showwarning("Formato no soportado", "Selecciona un archivo .csv o .xlsx/.xls"); return
        except Exception as ex:
            messagebox.showerror("Error al leer archivo", f"No se pudo leer el archivo:\n{ex}"); return

        ok, msg = _headers_ok(headers)
        if not ok: messagebox.showwarning("Encabezados incompatibles", msg); return

        imp_tree.delete(*imp_tree.get_children()); _tree_set_columns(imp_tree, headers)
        for r in rows:
            if len(r) < len(headers): r = r + [""]*(len(headers)-len(r))
            elif len(r) > len(headers): r = r[:len(headers)]
            imp_tree.insert("", "end", values=r)
        _renumber_cases(imp_tree)

        _, dyn, _ = _split_headers(headers)
        gm_dyncols.clear(); gm_dyncols.extend(dyn)
        _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()
        gm_status.set(f"Archivo cargado. Columnas dinámicas: {', '.join(dyn) if dyn else '(ninguna)'}")

    def _man_edit_selected():
        """Auto-generated docstring for `_man_edit_selected`."""
        sel = man_tree.selection()
        if not sel: messagebox.showinfo("Editar", "Selecciona una fila para editar."); return
        item = sel[0]; values = list(man_tree.item(item, 'values'))
        win = tk.Toplevel(app); win.title("Editar fila"); win.geometry("520x380")
        vars_map = []
        for i, h in enumerate(man_tree['columns']):
            v = tk.StringVar(value=values[i]); vars_map.append((h,v))
            fr = tb.Frame(win); fr.pack(fill=X, padx=10, pady=4)
            tb.Label(fr, text=h, width=24).pack(side=LEFT); tb.Entry(fr, textvariable=v).pack(side=LEFT, fill=X, expand=True)
        def _ok():
            """Auto-generated docstring for `_ok`."""
            new_vals = [v.get() for _,v in vars_map]; man_tree.item(item, values=new_vals); win.destroy()
        tb.Button(win, text="Guardar", bootstyle=PRIMARY, command=_ok).pack(side=RIGHT, padx=10, pady=10)
        tb.Button(win, text="Cancelar", bootstyle=SECONDARY, command=win.destroy).pack(side=RIGHT, pady=10)

    def _man_delete_selected():
        """Auto-generated docstring for `_man_delete_selected`."""
        sel = man_tree.selection()
        if not sel: return
        if not messagebox.askyesno("Eliminar", f"¿Eliminar {len(sel)} fila(s)?"): return
        for it in sel: man_tree.delete(it)
        _renumber_cases(man_tree)

    def _man_clear_all():
        """Auto-generated docstring for `_man_clear_all`."""
        if not man_tree.get_children(""): return
        if not messagebox.askyesno("Vaciar tabla", "¿Vaciar todas las filas capturadas?"): return
        man_tree.delete(*man_tree.get_children()); gm_case_counter.set(1)

    man_tree.bind("<Delete>", lambda e: (_man_delete_selected(), "break"))

    tb.Button(man_actions, text="Editar fila", bootstyle=SECONDARY, command=_man_edit_selected).pack(side=LEFT)
    tb.Button(man_actions, text="Eliminar fila", bootstyle=DANGER, command=_man_delete_selected).pack(side=LEFT, padx=(8,0))
    tb.Button(man_actions, text="Vaciar tabla", bootstyle=SECONDARY, command=_man_clear_all).pack(side=LEFT, padx=(8,0))

    def _show_mode():
        """Auto-generated docstring for `_show_mode`."""
        try:
            status_lbl.pack_forget()
            top.pack_forget(); gm_toolbar.pack_forget()
            import_frame.pack_forget(); imp_top.pack_forget(); imp_info.pack_forget(); imp_prev.pack_forget(); imp_tv_wrap.pack_forget(); imp_actions.pack_forget()
            manual_frame.pack_forget(); cols_bar.pack_forget(); chips_holder.pack_forget(); man_cap.pack_forget(); scroll_wrap.pack_forget(); btns.pack_forget(); man_prev.pack_forget(); man_tv_wrap.pack_forget(); man_actions.pack_forget()
        except Exception: pass

        mode = gm_mode.get()
        if mode not in ("import","manual"):
            gm_status.set("Elige cómo quieres trabajar (importar o captura manual).")
            status_lbl.pack(anchor="w", padx=6, pady=(6,0)); return

        top.pack(fill=X); gm_toolbar.pack(fill=X, pady=(6,0))

        if mode == "import":
            import_frame.pack(fill=BOTH, expand=True)
            imp_top.pack(fill=X); imp_info.pack(anchor="w", pady=(6,0))
            imp_prev.pack(fill=BOTH, expand=True, pady=(6,0)); imp_tv_wrap.pack(fill=BOTH, expand=True)
            imp_actions.pack(fill=X, pady=(6,0))
        else:
            manual_frame.pack(fill=BOTH, expand=True)
            cols_bar.pack(fill=X); chips_holder.pack(fill=X, pady=(8,0))
            man_cap.pack(fill=BOTH, expand=True, pady=(6,0))
            scroll_wrap.pack(fill=X); btns.pack(fill=X, pady=(6,0))
            man_prev.pack(fill=BOTH, expand=True, pady=(6,0)); man_tv_wrap.pack(fill=BOTH, expand=True)
            man_actions.pack(fill=X, pady=(6,0))
            _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()

    def _load_dyncols_from_template():
        """Auto-generated docstring for `_load_dyncols_from_template`."""
        path = filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path: return
        try:
            headers, _rows = _read_csv_any_encoding(path)
            ok, msg = _headers_ok(headers)
            if not ok: messagebox.showwarning("Plantilla incompatible", msg); return
            _, dyn, _ = _split_headers(headers)
            gm_dyncols.clear(); gm_dyncols.extend(dyn)
            _man_build_tree_headers(); _rebuild_manual_inputs(); _render_dynchips()
            gm_status.set(f"Dinámicas cargadas: {', '.join(dyn) if dyn else '(ninguna)'}")
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo leer la plantilla:\n{ex}")

    _show_mode()
    _placeholder(frame_mod_matriz, "Modificación de Matriz", "Busca, abre y edita matrices existentes.")
    _placeholder(frame_alta_cic,   "Alta de Ciclos", "Crea ciclos nuevos para su uso en matrices.")
    _placeholder(frame_mod_cic,    "Modificación de Ciclos Existentes", "Actualiza ciclos previamente creados.")

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

    def show_section(section_id: str):
        """Auto-generated docstring for `show_section`."""
        for fr in all_frames.values():
            fr.pack_forget()
        all_frames.get(section_id, frame_pruebas).pack(fill=BOTH, expand=YES)
        _highlight_nav(section_id)
        # Botonera inferior solo en PRUEBAS
        try:
            if section_id == "PRUEBAS" and 'btns' in globals():
                btns.pack(fill=X)
            elif 'btns' in globals():
                btns.pack_forget()
        except Exception:
            pass

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
    body = frame_pruebas

    # === Vista inicial: LAUNCHER (sin sidebar) ===
    hide_sidebar()
    show_section("LAUNCHER")

    card1 = tb.Labelframe(body, text="Datos generales", bootstyle=SECONDARY, padding=12)
    card1.pack(fill=X, pady=(0,12)); card1.columnconfigure(1, weight=1)

    tb.Label(card1, text="Nombre base").grid(row=0, column=0, sticky=W, pady=(2,2))
    base_var = tb.StringVar(value="reporte"); tb.Entry(card1, textvariable=base_var).grid(row=0, column=1, sticky=EW, padx=(10,0))

    tb.Label(card1, text="URL inicial").grid(row=2, column=0, sticky=W, pady=(10,2))
    urls = controller.load_history(controller.URL_HISTORY_CATEGORY, controller.DEFAULT_URL)
    url_var = tb.StringVar(value=urls[0] if urls else controller.DEFAULT_URL)
    tb.Combobox(card1, textvariable=url_var, values=urls, width=56, bootstyle="light").grid(row=2, column=1, sticky=EW, pady=(10,2))

    card2 = tb.Labelframe(body, text="Salidas", bootstyle=SECONDARY, padding=12)
    card2.pack(fill=X, pady=(0,12)); card2.columnconfigure(1, weight=1)

    tb.Label(card2, text="Documento (DOCX)").grid(row=0, column=0, sticky=W)
    doc_var = tb.StringVar(); tb.Entry(card2, textvariable=doc_var).grid(row=0, column=1, sticky=EW, padx=(10,0) , pady=(2,2))

    tb.Label(card2, text="Carpeta evidencias").grid(row=1, column=0, sticky=W, pady=(6,0))
    ev_var = tb.StringVar(); tb.Entry(card2, textvariable=ev_var).grid(row=1, column=1, sticky=EW, padx=(10,0) , pady=(2,2))

    def refresh_paths(*_):
        """Auto-generated docstring for `refresh_paths`."""
        base = controller.slugify_for_windows(base_var.get() or "reporte")
        final = f"{base}"
        doc_var.set(str(Path("sessions")/f"{final}.docx"))
        ev_var.set(str(Path("evidencia")/final))
    base_var.trace_add("write", refresh_paths); refresh_paths()

    prev_base = {"val": controller.slugify_for_windows(base_var.get() or "reporte")}
    def _on_base_change(*_):
        """Auto-generated docstring for `_on_base_change`."""
        new_base = controller.slugify_for_windows(base_var.get() or "reporte")
        old_base = prev_base["val"]
        if not old_base or new_base == old_base:
            return
        ev_old = Path("evidencia")/old_base
        has_hist = bool(session.get("steps")) if isinstance(session, dict) else False
        has_old_dir = ev_old.exists()
        if has_hist or has_old_dir:
            if Messagebox.askyesno(f"Se cambió el nombre base de '{old_base}' a '{new_base}'. ¿Limpiar historial en la GUI? (Las evidencias en disco no se tocan)", "Cambio de nombre"):
                _clear_evidence_for(old_base, also_clear_session=True)
                status.set(f"🧹 Historial limpiado. Evidencias en disco conservadas para: {old_base}")
            prev_base["val"] = new_base
        base_var.trace_add("write", _on_base_change)

    status = tb.StringVar(value="Listo.")
    status_bar = tb.Label(app, textvariable=status, bootstyle=INFO, anchor=W, padding=(16,6)); status_bar.pack(fill=X)

    session_saved = {"val": False}

    session = {"title": "Incidencia", "steps": []}
    _monitor_index = {"val": None}

    def ensure_mss():
        """Auto-generated docstring for `ensure_mss`."""
        try:
            import mss, mss.tools
            return True
        except Exception:
            Messagebox.show_error("Falta el paquete 'mss'. Instala:\n\npip install mss", "SNAP")
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
            Messagebox.show_error("No se detectaron monitores.", "SNAP"); return None, None
        idx = _monitor_index["val"]
        if ask_always.get() or idx is None or idx >= len(monitors) or idx < 0:
            sel = select_monitor_modal(app, monitors)
            if sel is None: return None, None
            idx = sel; _monitor_index["val"] = idx
        return monitors, idx

    def snap_externo_monitor():
        """Auto-generated docstring for `snap_externo_monitor`."""
        if not ensure_mss(): return
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
            from utils.capture_editor import open_capture_editor
            meta_in = {
                "descripcion": meta_desc.get("descripcion",""),
                "consideraciones": meta_desc.get("consideraciones",""),
                "observaciones": meta_desc.get("observacion",""),
            }
            edited_path, meta_out = open_capture_editor(str(out_path), meta_in)
            if edited_path and os.path.exists(edited_path):
                out_path = Path(edited_path)
            # Sincronizar claves con el formato del sistema (observacion en singular)
            meta_desc["descripcion"]     = meta_out.get("descripcion","")
            meta_desc["consideraciones"] = meta_out.get("consideraciones","")
            meta_desc["observacion"]     = meta_out.get("observaciones","")
        except Exception as e:
            Messagebox.show_warning(f"Editor no disponible: {e}", "Editor")

        step = {"cmd": "snap_externo", "shots": [str(out_path)]}
        if meta_desc["descripcion"]: step["desc"] = meta_desc["descripcion"]
        if meta_desc["consideraciones"]: step["consideraciones"] = meta_desc["consideraciones"]
        if meta_desc["observacion"]: step["observacion"] = meta_desc["observacion"]
        session["steps"].append(step); status.set(f"🖥️ SNAP externo agregado (monitor {idx})")
        try:
            tipo = step.get("cmd", "snap")
            archivo = os.path.basename((step.get("shots") or [""])[0])
            hist.insert("", "end", iid=len(session["steps"])-1, values=(tipo, archivo))
        except Exception:
            pass


    def snap_region_all():
        """Auto-generated docstring for `snap_region_all`."""
        if not ensure_mss(): return
        import mss, mss.tools
        with mss.mss() as sct:
            desktop = sct.monitors[0]
            bbox = select_region_overlay(app, desktop)
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
            from utils.capture_editor import open_capture_editor
            meta_in = {
                "descripcion": meta_desc.get("descripcion",""),
                "consideraciones": meta_desc.get("consideraciones",""),
                "observaciones": meta_desc.get("observacion",""),
            }
            edited_path, meta_out = open_capture_editor(str(out_path), meta_in)
            if edited_path and os.path.exists(edited_path):
                out_path = Path(edited_path)
            meta_desc["descripcion"]     = meta_out.get("descripcion","")
            meta_desc["consideraciones"] = meta_out.get("consideraciones","")
            meta_desc["observacion"]     = meta_out.get("observaciones","")
        except Exception as e:
            Messagebox.show_warning(f"Editor no disponible: {e}", "Editor")

        step = {"cmd": "snap_region_all", "shots": [str(out_path)]}
        if meta_desc["descripcion"]: step["desc"] = meta_desc["descripcion"]
        if meta_desc["consideraciones"]: step["consideraciones"] = meta_desc["consideraciones"]
        if meta_desc["observacion"]: step["observacion"] = meta_desc["observacion"]
        session["steps"].append(step); status.set("📐 SNAP región (todas) agregado")
        try:
            tipo = step.get("cmd", "snap")
            archivo = os.path.basename((step.get("shots") or [""])[0])
            hist.insert("", "end", iid=len(session["steps"])-1, values=(tipo, archivo))
        except Exception:
            pass

    def generar_doc():
        """Auto-generated docstring for `generar_doc`."""
        if not session["steps"]:
            if not Messagebox.askyesno("Reporte","No hay pasos. ¿Generar documento vacío?"): return
        outp = Path(doc_var.get()); outp.parent.mkdir(parents=True, exist_ok=True)
        build_word(session.get("title"), session["steps"], str(outp))
        Messagebox.showinfo(f"Reporte generado:\n{outp}", f"Reporte Guardado En: \n{outp}"); status.set("✅ Reporte generado"); session_saved["val"]=True; 
        btn_limpiar.configure(state="normal")

    def modal_confluence_url():
        """Auto-generated docstring for `modal_confluence_url`."""
        win = tb.Toplevel(app); win.title("Importar a Confluence"); win.transient(app); win.grab_set(); win.geometry("800x300")
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
        build_word(session.get("title"), session["steps"], str(outp))


        url_c = modal_confluence_url()
        if not url_c: return
        controller.register_history_value(controller.CONFLUENCE_HISTORY_CATEGORY, url_c)

        status.set("⏳ Preparando contenido y abriendo Confluence...")
        controller.open_chrome_with_profile(url_c, "Default")
        log_path = Path("sessions") / f"{session.get('title')}_confluence.log"

        Messagebox.showinfo(
            "Confluence",
            "Haz click en el campo de Confluence donde quieras pegar.\n"
            "El pegado empezará en 5 segundos."
        )

        pasted, errs = import_steps_to_confluence(session["steps"], delay_sec=5, log_path=log_path)

        if errs:
            Messagebox.showwarning("Confluence", f"Pegado con advertencias ({len(errs)}). Revisa el log:\n{log_path}")
        else:
            Messagebox.showinfo("Confluence", f"✅ Pegado de {pasted} pasos completado.\nLog: {log_path}")

    
        session_saved["val"] = True
        try:
            btn_limpiar.configure(state="normal")
        except Exception:
            pass
    btns = tb.Frame(frame_pruebas, padding=(16,6)); btns.pack(fill=X)
    # --- Helpers de limpieza y selección ---
    def _clear_evidence_for(base_name: str, also_clear_session: bool = True):
        """Limpiar solo el estado en memoria manteniendo evidencias en disco."""
        removed = False  # ya no se elimina nada en disco
        if also_clear_session:
            try: session["steps"].clear()
            except Exception: pass
            try: hist.delete(*hist.get_children())
            except Exception: pass
        return removed

    def reset_monitor_selection():
        """Auto-generated docstring for `reset_monitor_selection`."""
        _monitor_index["val"] = None
        Messagebox.showinfo("SNAP Externo","La próxima captura externa te pedirá la pantalla nuevamente.")

    def limpiar_cache():
        """Auto-generated docstring for `limpiar_cache`."""
        # Si aún no se ha guardado (DONE o Importar Confluence), pedir confirmación
        if not session_saved["val"]:
            if not Messagebox.askyesno("Aún no has guardado con DONE ni Importar Confluence.¿Deseas limpiar SOLO el historial en la GUI de todas formas?(No se borrarán archivos de evidencia.)","Limpiar caché (solo GUI)"):return

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
            Messagebox.show_error(f"No se pudo abrir Chrome: {msg}", "Navegador")

    tb.Button(btns, text="🔗 Abrir navegador", command=abrir_nav, bootstyle=PRIMARY, width=18).pack(side=LEFT, padx=(0,8))
    tb.Button(btns, text="🖥️ Cambiar pantalla…", command=reset_monitor_selection, bootstyle=SECONDARY, width=20).pack(side=LEFT, padx=8)
    tb.Button(btns, text="🖥️ SNAP externo", command=snap_externo_monitor, bootstyle=INFO, width=16).pack(side=LEFT, padx=8)
    tb.Button(btns, text="📐 SNAP región", command=snap_region_all, bootstyle=INFO, width=16).pack(side=LEFT, padx=8)

    ask_always = tk.BooleanVar(value=False)
    def _ask_switch():
        """Auto-generated docstring for `_ask_switch`."""
        if ask_always.get(): _monitor_index["val"] = None
    tb.Checkbutton(btns, text="Preguntar pantalla cada vez", variable=ask_always, bootstyle="round-toggle", command=_ask_switch).pack(side=LEFT, padx=8)
    tb.Button(btns, text="📥 Importar Confluence", command=importar_confluence, bootstyle=SUCCESS, width=22).pack(side=LEFT, padx=8)
    btn_limpiar = tb.Button(btns, text="Finalizar Pruebas",  command=limpiar_cache, bootstyle=DANGER, width=16)
    btn_limpiar.pack(side=RIGHT, padx=(8,0))
    tb.Button(btns, text="✅ DONE", command=generar_doc, bootstyle=WARNING, width=12).pack(side=RIGHT)

    app.mainloop()

if __name__ == "__main__":
    run_gui()
