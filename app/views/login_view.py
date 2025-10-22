"""Standalone view module that renders the login dialog."""

from __future__ import annotations

from typing import Optional, Protocol

import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, PRIMARY, RIGHT, SECONDARY, WARNING, W, X, YES

from app.controllers.main_controller import MainController
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus


class MessageboxProtocol(Protocol):
    """Define the contract expected from the messagebox helper class."""

    @staticmethod
    def showinfo(title: str, message: str) -> None:
        """Display an informational dialog.

        Args:
            title: Caption used for the dialog window.
            message: Body text presented to the user.
        """

    @staticmethod
    def showwarning(title: str, message: str) -> None:
        """Display a warning dialog.

        Args:
            title: Caption used for the dialog window.
            message: Body text presented to the user.
        """

    @staticmethod
    def showerror(title: str, message: str) -> None:
        """Display an error dialog.

        Args:
            title: Caption used for the dialog window.
            message: Body text presented to the user.
        """

    @staticmethod
    def askyesno(title: str, message: str) -> bool:
        """Ask the user to confirm an action with a yes/no dialog.

        Args:
            title: Caption used for the dialog window.
            message: Body text presented to the user.

        Returns:
            ``True`` when the user accepts the action, ``False`` otherwise.
        """


def build_login_view(
    root: tb.Window,
    controller: MainController,
    messagebox: MessageboxProtocol,
) -> Optional[AuthenticationResult]:
    """Render the login dialog and return the authenticated user if successful.

    Args:
        root: Root application window used to parent the login dialog.
        controller: Controller that provides the authentication helpers.
        messagebox: Helper that standardizes the feedback dialogs.

    Returns:
        The authentication result when the user logs in successfully, otherwise
        ``None`` if the dialog is closed or the process is cancelled.
    """

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
        """Remember the active username widget to manage focus later on.

        Args:
            widget: Entry or combobox that should receive focus later.
        """

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
        """Populate the username input once the user list has been resolved.

        Args:
            choices: Collection of ``(username, display_name)`` tuples to show.
            error_message: Error text to display when the list retrieval fails.
        """

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
        """Trigger the authentication flow using the typed credentials.

        Args:
            _event: Optional Tkinter event when invoked via keyboard binding.
        """

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
            messagebox.showerror(
                "Cambio de contraseña requerido",
                "Debes actualizar la contraseña en el sistema principal antes de usar esta aplicación.",
            )
            status_var.set("Actualiza tu contraseña en el sistema principal.")
            return

        if status == AuthenticationStatus.PASSWORD_REQUIRED:
            messagebox.showerror(
                "Contraseña requerida",
                "El usuario no tiene contraseña definida. Ingresa al sistema principal para establecerla.",
            )
            status_var.set("Define una contraseña en el sistema principal y vuelve a intentar.")
            return

        if status == AuthenticationStatus.INACTIVE:
            messagebox.showerror("Usuario inactivo", auth_result.message)
            status_var.set("La cuenta está desactivada.")
            return

        if status == AuthenticationStatus.ERROR:
            messagebox.showerror("Error al iniciar sesión", auth_result.message)
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
