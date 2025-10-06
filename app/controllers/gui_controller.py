"""Tkinter controller coordinating the GUI recorder workflow."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, EW, INFO, PRIMARY, RIGHT, SECONDARY, SUCCESS, WARNING, W, X, YES
from ttkbootstrap.dialogs import Messagebox

from app.daos.history_dao import HistoryDAO
from app.dtos.session_dto import SessionDTO
from app.services.browser_service import BrowserService
from app.services.history_service import HistoryService
from app.services.naming_service import slugify_for_windows
from utils.confluence_ui import import_steps_to_confluence
from utils.report_word import build_word

DEFAULT_URL = "http://localhost:8080/ELLiS/login"
URLS_FILE = Path("url_history.json")
CONF_FILE = Path("confluence_history.json")
SPACES_FILE = Path("confluence_spaces.json")


class GuiController:
    """Create the GUI elements and orchestrate user interactions."""

    def __init__(
        self,
        history_service: HistoryService,
        confluence_history_service: HistoryService,
        confluence_space_service: HistoryService,
        browser_service: Optional[BrowserService] = None,
    ) -> None:
        """Store dependencies used across the GUI interactions."""
        self.history_service = history_service
        self.confluence_history_service = confluence_history_service
        self.confluence_space_service = confluence_space_service
        self.browser_service = browser_service or BrowserService()
        self.session = SessionDTO(title="Incidencia")
        self._monitor_index: Dict[str, Optional[int]] = {"val": None}

        self.app: Optional[tb.Window] = None
        self.base_var: Optional[tb.StringVar] = None
        self.doc_var: Optional[tb.StringVar] = None
        self.ev_var: Optional[tb.StringVar] = None
        self.url_var: Optional[tb.StringVar] = None
        self.status: Optional[tb.StringVar] = None

    def run(self) -> None:
        """Initialize and launch the GUI main loop."""
        self.app = tb.Window(themename="flatly")
        self.app.title("Pruebas / Evidencias")
        self.app.geometry("980x640")

        body = tb.Frame(self.app, padding=(16, 0))
        body.pack(fill=BOTH, expand=YES)

        self._build_general_card(body)
        self._build_output_card(body)
        self._build_status_bar()
        self._build_actions()

        self.app.mainloop()

    def _build_general_card(self, body: tb.Frame) -> None:
        """Create controls for base information and URL history."""
        card = tb.Labelframe(body, text="Datos generales", bootstyle=SECONDARY, padding=12)
        card.pack(fill=X, pady=(0, 12))
        card.columnconfigure(1, weight=1)

        tb.Label(card, text="Nombre base").grid(row=0, column=0, sticky=W, pady=(2, 2))
        self.base_var = tb.StringVar(value="reporte")
        tb.Entry(card, textvariable=self.base_var).grid(row=0, column=1, sticky=EW, padx=(10, 0))

        tb.Label(card, text="URL inicial").grid(row=2, column=0, sticky=W, pady=(10, 2))
        urls = self.history_service.get_recent()
        default_url = urls[0] if urls else DEFAULT_URL
        self.url_var = tb.StringVar(value=default_url)
        tb.Combobox(card, textvariable=self.url_var, values=urls, width=56, bootstyle="light").grid(
            row=2, column=1, sticky=EW, pady=(10, 2)
        )

    def _build_output_card(self, body: tb.Frame) -> None:
        """Create controls for evidence and report destinations."""
        card = tb.Labelframe(body, text="Salidas", bootstyle=SECONDARY, padding=12)
        card.pack(fill=X, pady=(0, 12))
        card.columnconfigure(1, weight=1)

        tb.Label(card, text="Documento (DOCX)").grid(row=0, column=0, sticky=W)
        self.doc_var = tb.StringVar()
        tb.Entry(card, textvariable=self.doc_var).grid(row=0, column=1, sticky=EW, padx=(10, 0), pady=(2, 2))

        tb.Label(card, text="Carpeta evidencias").grid(row=1, column=0, sticky=W, pady=(6, 0))
        self.ev_var = tb.StringVar()
        tb.Entry(card, textvariable=self.ev_var).grid(row=1, column=1, sticky=EW, padx=(10, 0), pady=(2, 2))

        if self.base_var is None:
            return
        self.base_var.trace_add("write", self._refresh_paths)
        self._refresh_paths()

    def _build_status_bar(self) -> None:
        """Create the status bar used to notify the user."""
        if self.app is None:
            raise RuntimeError("Application window not initialized")
        self.status = tb.StringVar(value="Listo.")
        tb.Label(self.app, textvariable=self.status, bootstyle=INFO, anchor=W, padding=(16, 6)).pack(fill=X)

    def _build_actions(self) -> None:
        """Assemble action buttons and bind their callbacks."""
        if self.app is None:
            raise RuntimeError("Application window not initialized")

        btns = tb.Frame(self.app, padding=(16, 6))
        btns.pack(fill=X)

        tb.Button(btns, text="🔗 Abrir navegador", command=self._open_browser, bootstyle=PRIMARY, width=18).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        tb.Button(btns, text="🖥️ SNAP externo", command=self._snap_external_monitor, bootstyle=INFO, width=16).pack(
            side=tk.LEFT, padx=8
        )
        tb.Button(btns, text="📐 SNAP región", command=self._snap_region_all, bootstyle=INFO, width=16).pack(
            side=tk.LEFT, padx=8
        )
        tb.Button(
            btns,
            text="📥 Importar Confluence",
            command=self._import_confluence,
            bootstyle=SUCCESS,
            width=22,
        ).pack(side=tk.LEFT, padx=8)
        tb.Button(btns, text="✅ DONE", command=self._generate_report, bootstyle=WARNING, width=12).pack(side=tk.RIGHT)

    def _refresh_paths(self, *_args: object) -> None:
        """Update default output paths according to the base name."""
        if self.base_var is None or self.doc_var is None or self.ev_var is None:
            return
        base = slugify_for_windows(self.base_var.get() or "reporte")
        final_name = f"{base}"
        self.doc_var.set(str(Path("sessions") / f"{final_name}.docx"))
        self.ev_var.set(str(Path("evidencia") / final_name))

    def _ensure_mss(self) -> bool:
        """Verify that the MSS dependency is available for screen captures."""
        try:
            import mss  # noqa: F401
            import mss.tools  # noqa: F401
            return True
        except Exception:
            Messagebox.show_error("Falta el paquete 'mss'. Instala:\n\npip install mss", "SNAP")
            return False

    def _text_modal(self, title: str) -> Optional[Dict[str, str]]:
        """Display a modal dialog to capture textual metadata."""
        if self.app is None:
            return None
        win = tb.Toplevel(self.app)
        win.title(title)
        win.transient(self.app)
        win.grab_set()
        win.resizable(True, True)
        win.geometry("760x540")
        try:
            win.minsize(640, 420)
        except Exception:
            pass

        container = tb.Frame(win, padding=15)
        container.pack(fill=BOTH, expand=YES)
        tb.Label(container, text=title, font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0, 8))

        fields = {
            "descripcion": ("Descripción", 6),
            "consideraciones": ("Consideraciones", 5),
            "observacion": ("Observación", 5),
        }
        widgets: Dict[str, tk.Text] = {}
        for key, (label, height) in fields.items():
            tb.Label(container, text=label, font=("Segoe UI", 10, "bold")).pack(anchor=W)
            text = tk.Text(container, height=height, wrap="word")
            text.configure(font=("Segoe UI", 10))
            text.pack(fill=BOTH, expand=YES, pady=(2, 10))
            widgets[key] = text

        result: Dict[str, str] = {"cancel": "True"}

        def on_accept() -> None:
            """Persist the captured metadata and close the modal."""
            result.update({key: widget.get("1.0", "end").strip() for key, widget in widgets.items()})
            result["cancel"] = "False"
            win.destroy()

        def on_cancel() -> None:
            """Abort the metadata capture and close the modal."""
            result["cancel"] = "True"
            win.destroy()

        btns = tb.Frame(container)
        btns.pack(fill=X, pady=(8, 0))
        tb.Button(btns, text="Cancelar", command=on_cancel, bootstyle=SECONDARY, width=12).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Aceptar", command=on_accept, bootstyle=PRIMARY, width=12).pack(side=RIGHT)

        win.wait_window()
        if result.get("cancel") == "True":
            return None
        return {key: value for key, value in result.items() if key != "cancel"}

    def _select_monitor_modal(self, monitors: List[Dict[str, int]]) -> Optional[int]:
        """Ask the user which monitor should be used for captures."""
        if self.app is None:
            return None
        win = tb.Toplevel(self.app)
        win.title("Seleccionar monitor")
        win.transient(self.app)
        win.grab_set()
        frm = tb.Frame(win, padding=15)
        frm.pack(fill=BOTH, expand=YES)

        tb.Label(frm, text="Elige el monitor", font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0, 8))
        options = []
        for idx, monitor in enumerate(monitors):
            if idx == 0:
                label = f"Todos (desktop completo)  {monitor.get('width', '?')}x{monitor.get('height', '?')}"
            else:
                label = (
                    f"Monitor {idx}  ({monitor.get('left', '?')},{monitor.get('top', '?')})  "
                    f"{monitor.get('width', '?')}x{monitor.get('height', '?')}"
                )
            options.append(label)

        sel = tb.Combobox(frm, values=options, state="readonly", width=60)
        sel.pack(fill=X)
        sel.current(1 if len(monitors) > 1 else 0)

        res = {"index": None}

        def on_accept() -> None:
            """Confirm the selected monitor index."""
            res["index"] = sel.current()
            win.destroy()

        def on_cancel() -> None:
            """Cancel the monitor selection."""
            res["index"] = None
            win.destroy()

        btns = tb.Frame(frm)
        btns.pack(fill=X, pady=(10, 0))
        tb.Button(btns, text="Cancelar", command=on_cancel, bootstyle=SECONDARY).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Aceptar", command=on_accept, bootstyle=PRIMARY).pack(side=RIGHT)

        win.wait_window()
        return res["index"]

    def _select_monitor(self, sct: "mss.mss") -> Tuple[Optional[List[Dict[str, int]]], Optional[int]]:
        """Determine which monitor should be used for the next capture."""
        monitors = sct.monitors
        if not monitors:
            Messagebox.show_error("No se detectaron monitores.", "SNAP")
            return None, None
        idx = self._monitor_index.get("val")
        if idx is None or idx >= len(monitors) or idx < 0:
            idx = self._select_monitor_modal(monitors)
            if idx is None:
                return None, None
            self._monitor_index["val"] = idx
        return monitors, idx

    def _snap_external_monitor(self) -> None:
        """Capture the content of an external monitor."""
        if not self._ensure_mss() or self.ev_var is None:
            return
        import mss
        import mss.tools

        with mss.mss() as sct:
            monitors, idx = self._select_monitor(sct)
            if monitors is None or idx is None:
                return
            metadata = self._text_modal(f"SNAP externo (monitor {idx if idx > 0 else 'Todos'})")
            if metadata is None:
                return
            evid_dir = Path(self.ev_var.get())
            evid_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            out_path = evid_dir / f"snap_ext_monitor{idx}_{timestamp}.png"
            monitor = monitors[idx]
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))

        step = {"cmd": "snap_externo", "shots": [str(out_path)]}
        self._apply_metadata(step, metadata)
        self.session.add_step(step)
        if self.status:
            self.status.set(f"🖥️ SNAP externo agregado (monitor {idx})")

    def _snap_region_all(self) -> None:
        """Capture a custom region across all monitors."""
        if not self._ensure_mss() or self.ev_var is None or self.app is None:
            return
        import mss
        import mss.tools

        with mss.mss() as sct:
            desktop = sct.monitors[0]
            bbox = self._select_region_overlay(desktop)
            if not bbox:
                if self.status:
                    self.status.set("Selección cancelada.")
                return
            metadata = self._text_modal("SNAP región")
            if metadata is None:
                return

            left, top, width, height = bbox
            region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
            evid_dir = Path(self.ev_var.get())
            evid_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            out_path = evid_dir / f"snap_region_all_{timestamp}.png"
            img = sct.grab(region)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))

        step = {"cmd": "snap_region_all", "shots": [str(out_path)]}
        self._apply_metadata(step, metadata)
        self.session.add_step(step)
        if self.status:
            self.status.set("📐 SNAP región (todas) agregado")

    def _select_region_overlay(self, desktop: Dict[str, int]) -> Optional[Tuple[int, int, int, int]]:
        """Allow the user to select a region using an overlay window."""
        if self.app is None:
            return None
        import tkinter as tk_local

        left = int(desktop.get("left", 0))
        top = int(desktop.get("top", 0))
        width = int(desktop.get("width", 0))
        height = int(desktop.get("height", 0))

        overlay = tk_local.Toplevel(self.app)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        try:
            overlay.attributes("-alpha", 0.30)
        except Exception:
            pass
        overlay.configure(bg="gray")
        overlay.geometry(f"{width}x{height}+{left}+{top}")

        canvas = tk_local.Canvas(overlay, bg="gray", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        state: Dict[str, Optional[int]] = {"x0": None, "y0": None}
        rect = {"id": None}
        bbox: Dict[str, Optional[Tuple[int, int, int, int]]] = {"value": None}

        def on_press(event: tk_local.Event) -> None:
            """Capture the initial cursor coordinates."""
            state["x0"], state["y0"] = event.x, event.y
            if rect["id"]:
                canvas.delete(rect["id"])
                rect["id"] = None

        def on_move(event: tk_local.Event) -> None:
            """Update the preview rectangle while dragging."""
            if state["x0"] is None:
                return
            x1, y1 = event.x, event.y
            if rect["id"]:
                canvas.coords(rect["id"], state["x0"], state["y0"], x1, y1)
            else:
                rect["id"] = canvas.create_rectangle(
                    state["x0"], state["y0"], x1, y1, outline="red", width=3, dash=(4, 2)
                )

        def on_release(event: tk_local.Event) -> None:
            """Store the selected bounding box and close the overlay."""
            if state["x0"] is None:
                return
            x1, y1 = event.x, event.y
            x0, y0 = state["x0"], state["y0"]
            left_rel, right_rel = min(x0, x1), max(x0, x1)
            top_rel, bottom_rel = min(y0, y1), max(y0, y1)
            width_rel = max(1, right_rel - left_rel)
            height_rel = max(1, bottom_rel - top_rel)
            absolute_left = left + left_rel
            absolute_top = top + top_rel
            bbox["value"] = (absolute_left, absolute_top, width_rel, height_rel)
            overlay.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_move)
        canvas.bind("<ButtonRelease-1>", on_release)
        canvas.bind_all("<Escape>", lambda _event: overlay.destroy())
        tk_local.Label(
            overlay,
            text="Arrastra para seleccionar área (Esc para cancelar)",
            fg="white",
            bg="black",
        ).place(x=10, y=10)
        self.app.wait_window(overlay)
        return bbox["value"]

    def _apply_metadata(self, step: Dict[str, str], metadata: Optional[Dict[str, str]]) -> None:
        """Attach optional metadata fields to the captured step."""
        if not metadata:
            return
        for key, value in metadata.items():
            if value:
                if key == "descripcion":
                    step["desc"] = value
                else:
                    step[key] = value

    def _generate_report(self) -> None:
        """Generate the Word report using the recorded session steps."""
        if self.doc_var is None:
            return
        steps = self.session.steps
        if not steps and not Messagebox.yesno("No hay pasos. ¿Generar documento vacío?", "Reporte"):
            return
        out_path = Path(self.doc_var.get())
        out_path.parent.mkdir(parents=True, exist_ok=True)
        build_word(self.session.title, steps, str(out_path))
        Messagebox.showinfo(f"Reporte generado:\n{out_path}", f"Reporte Guardado En: \n{out_path}")
        if self.status:
            self.status.set("✅ Reporte generado")

    def _modal_confluence_url(self) -> Optional[str]:
        """Collect the Confluence target information from the user."""
        if self.app is None:
            return None
        win = tb.Toplevel(self.app)
        win.title("Importar a Confluence")
        win.transient(self.app)
        win.grab_set()
        win.geometry("800x300")
        frm = tb.Frame(win, padding=15)
        frm.pack(fill=BOTH, expand=YES)

        tb.Label(frm, text="URL de la página de Confluence", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(0, 8))

        tb.Label(frm, text="ENTORNO", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(10, 2))
        history_env = self.confluence_history_service.get_recent()
        env_var = tb.StringVar(value=history_env[0] if history_env else "")
        cmb_env = tb.Combobox(frm, textvariable=env_var, values=history_env, width=70, bootstyle="light")
        cmb_env.pack(fill=X)
        cmb_env.icursor("end")

        tb.Label(frm, text="ESPACIO", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(10, 2))
        history_space = self.confluence_space_service.get_recent()
        space_var = tb.StringVar(value=history_space[0] if history_space else "")
        cmb_space = tb.Combobox(frm, textvariable=space_var, values=history_space, width=70, bootstyle="light")
        cmb_space.pack(fill=X)
        cmb_space.icursor("end")

        result: Dict[str, Optional[str]] = {"url": None}

        def on_accept() -> None:
            """Confirm the composed Confluence URL."""
            result["url"] = ((env_var.get() + space_var.get()) or "").strip()
            win.destroy()

        def on_cancel() -> None:
            """Abort the Confluence import."""
            result["url"] = None
            win.destroy()

        btns = tb.Frame(frm)
        btns.pack(fill=X, pady=(12, 0))
        tb.Button(btns, text="Cancelar", command=on_cancel, bootstyle=SECONDARY).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Aceptar", command=on_accept, bootstyle=PRIMARY).pack(side=RIGHT)

        win.wait_window()
        return result["url"]

    def _import_confluence(self) -> None:
        """Trigger the Confluence integration by reusing existing utilities."""
        if self.session.steps == []:
            Messagebox.showwarning("Confluence", "No hay pasos en la sesión.")
            return
        if self.doc_var is None:
            return
        out_path = Path(self.doc_var.get())
        out_path.parent.mkdir(parents=True, exist_ok=True)
        build_word(self.session.title, self.session.steps, str(out_path))

        target_url = self._modal_confluence_url()
        if not target_url:
            return
        self.confluence_history_service.remember(target_url)

        if self.status:
            self.status.set("⏳ Preparando contenido y abriendo Confluence...")
        self.browser_service.open_with_profile(target_url, "Default")
        log_path = Path("sessions") / f"{self.session.title}_confluence.log"

        Messagebox.showinfo(
            "Confluence",
            "Haz click en el campo de Confluence donde quieras pegar.\nEl pegado empezará en 5 segundos.",
        )

        pasted, errs = import_steps_to_confluence(self.session.steps, delay_sec=5, log_path=log_path)

        if errs:
            Messagebox.showwarning("Confluence", f"Pegado con advertencias ({len(errs)}). Revisa el log:\n{log_path}")
        else:
            Messagebox.showinfo("Confluence", f"✅ Pegado de {pasted} pasos completado.\nLog: {log_path}")

    def _open_browser(self) -> None:
        """Launch Chrome using the currently selected URL."""
        url_value = DEFAULT_URL
        if self.url_var is not None:
            url_value = (self.url_var.get() or DEFAULT_URL).strip() or DEFAULT_URL
        success, message = self.browser_service.open_with_profile(url_value, "Default")
        if success:
            if self.status:
                self.status.set("✅ Chrome abierto (perfil Default)")
            self.history_service.remember(url_value)
        else:
            Messagebox.show_error(f"No se pudo abrir Chrome: {message}", "Navegador")


def run_gui() -> None:
    """Bootstrap the GUI controller with concrete service implementations."""
    history_service = HistoryService(HistoryDAO(URLS_FILE), DEFAULT_URL)
    confluence_history_service = HistoryService(HistoryDAO(CONF_FILE), "https://sistemaspremium.atlassian.net/wiki/spaces/")
    confluence_space_service = HistoryService(HistoryDAO(SPACES_FILE), "")
    controller = GuiController(history_service, confluence_history_service, confluence_space_service)
    controller.run()
