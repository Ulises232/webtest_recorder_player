
# gui_recorder_collect_inputs_modern.py — v3.2.4
# Cambios clave:
#  - Los botones SNAP mantienen la lógica anterior (mss).
#  - "Importar Confluence" YA NO usa Playwright para abrir el navegador.
#    * Abre Chrome via subprocess con el perfil "Default".
#    * Prepara el contenido y lo deja en portapapeles (usando utils.confluence_ui).
#    * Te pide hacer foco y pega con Ctrl+V (intento automático).
#
#  Con esto desaparece el error: "Playwright Sync API inside the asyncio loop".

import os, time, json, subprocess, shutil
from pathlib import Path
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from threading import Thread
import tkinter as tk
from tkinter import ttk, messagebox as Messagebox

from utils.report_word import build_word
from utils.confluence_ui import import_steps_to_confluence

DEFAULT_URL = "http://localhost:8080/ELLiS/login"
URLS_FILE = Path("url_history.json")
CONF_FILE = Path("confluence_history.json")
SPACES_FILE = Path("confluence_spaces.json")

def load_url_history(file_path: Path, default_item: str):
    try:
        if file_path.exists():
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass
    return [default_item]

def save_url_to_history(file_path: Path, url: str, cap: int = 15):
    url = (url or "").strip()
    if not url: return
    data = load_url_history(file_path, url)
    if any(u.lower() == url.lower() for u in data):
        pass
    else:
            data = [url] + [u for u in data if u.lower() != url.lower()]
            data = data[:cap]
            try:
                file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

def slugify_for_windows(name: str) -> str:
    import re
    name = (name or "").strip()
    name = re.sub(r'[<>:"/\\|?*\\x00-\\x1F]', '', name)
    name = re.sub(r'\\s+', '_', name)
    reserved = {"CON","PRN","AUX","NUL","COM1","COM2","COM3","COM4","COM5","COM6","COM7","COM8","COM9","LPT1","LPT2","LPT3","LPT4","LPT5","LPT6","LPT7","LPT8","LPT9"}
    if name.upper() in reserved:
        name = f"_{name}_"
    return name.rstrip(". ")[:80]

def text_modal(master, title: str):
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
        result["descripcion"] = desc.get("1.0","end").strip()
        result["consideraciones"] = cons.get("1.0","end").strip()
        result["observacion"] = obs.get("1.0","end").strip()
        win.destroy()
    def cancel():
        result["cancel"] = True
        win.destroy()
    tb.Button(btns, text="Cancelar", command=cancel, bootstyle=SECONDARY, width=12).pack(side=RIGHT, padx=6)
    tb.Button(btns, text="Aceptar", command=ok, bootstyle=PRIMARY, width=12).pack(side=RIGHT)

    win.wait_window(); return result

def select_region_overlay(master, desktop: dict):
    left = int(desktop.get("left", 0)); top = int(desktop.get("top", 0))
    width = int(desktop.get("width", 0)); height = int(desktop.get("height", 0))

    ov = tk.Toplevel(master); ov.overrideredirect(True); ov.attributes("-topmost", True)
    try: ov.attributes("-alpha", 0.30)
    except Exception: pass
    ov.configure(bg="gray"); ov.geometry(f"{width}x{height}+{left}+{top}")

    canvas = tk.Canvas(ov, bg="gray", highlightthickness=0); canvas.pack(fill="both", expand=True)
    state = {"x0": None, "y0": None, "rect": None, "bbox": None}

    def on_press(e):
        state["x0"], state["y0"] = e.x, e.y
        if state["rect"]: canvas.delete(state["rect"]); state["rect"] = None
    def on_move(e):
        if state["x0"] is None: return
        x1, y1 = e.x, e.y
        if state["rect"]:
            canvas.coords(state["rect"], state["x0"], state["y0"], x1, y1)
        else:
            state["rect"] = canvas.create_rectangle(state["x0"], state["y0"], x1, y1, outline="red", width=3, dash=(4,2))
    def on_release(e):
        if state["x0"] is None: return
        x1, y1 = e.x, e.y; x0, y0 = state["x0"], state["y0"]
        lx, rx = min(x0, x1), max(x0, x1); ty, by = min(y0, y1), max(y0, y1)
        w = max(1, rx - lx); h = max(1, by - ty); abs_left = left + lx; abs_top = top + ty
        state["bbox"] = (abs_left, abs_top, w, h); ov.destroy()
    canvas.bind("<ButtonPress-1>", on_press); canvas.bind("<B1-Motion>", on_move); canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind_all("<Escape>", lambda e: ov.destroy())
    tk.Label(ov, text="Arrastra para seleccionar área (Esc para cancelar)", fg="white", bg="black").place(x=10, y=10)
    master.wait_window(ov); return state["bbox"]

def find_chrome_exe():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("chrome"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None

def open_chrome_with_profile(url: str, profile_dir: str = "Default"):
    exe = find_chrome_exe()
    if not exe:
        raise RuntimeError("No se encontró chrome.exe")
    args = [exe, f"--profile-directory={profile_dir}", url]
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, ""
    except Exception as e:
        return False, str(e)

def run_gui():
    app = tb.Window(themename="flatly")
    app.title("Pruebas / Evidencias")
    app.geometry("980x640")


    body = tb.Frame(app, padding=(16,0)); body.pack(fill=BOTH, expand=YES)

    card1 = tb.Labelframe(body, text="Datos generales", bootstyle=SECONDARY, padding=12)
    card1.pack(fill=X, pady=(0,12)); card1.columnconfigure(1, weight=1)

    tb.Label(card1, text="Nombre base").grid(row=0, column=0, sticky=W, pady=(2,2))
    base_var = tb.StringVar(value="reporte"); tb.Entry(card1, textvariable=base_var).grid(row=0, column=1, sticky=EW, padx=(10,0))

    tb.Label(card1, text="URL inicial").grid(row=2, column=0, sticky=W, pady=(10,2))
    urls = load_url_history(URLS_FILE, DEFAULT_URL)
    url_var = tb.StringVar(value=urls[0] if urls else DEFAULT_URL)
    tb.Combobox(card1, textvariable=url_var, values=urls, width=56, bootstyle="light").grid(row=2, column=1, sticky=EW, pady=(10,2))

    card2 = tb.Labelframe(body, text="Salidas", bootstyle=SECONDARY, padding=12)
    card2.pack(fill=X, pady=(0,12)); card2.columnconfigure(1, weight=1)

    tb.Label(card2, text="Documento (DOCX)").grid(row=0, column=0, sticky=W)
    doc_var = tb.StringVar(); tb.Entry(card2, textvariable=doc_var).grid(row=0, column=1, sticky=EW, padx=(10,0) , pady=(2,2))

    tb.Label(card2, text="Carpeta evidencias").grid(row=1, column=0, sticky=W, pady=(6,0))
    ev_var = tb.StringVar(); tb.Entry(card2, textvariable=ev_var).grid(row=1, column=1, sticky=EW, padx=(10,0) , pady=(2,2))

    def refresh_paths(*_):
        base = slugify_for_windows(base_var.get() or "reporte")
        final = f"{base}"
        doc_var.set(str(Path("sessions")/f"{final}.docx"))
        ev_var.set(str(Path("evidencia")/final))
    base_var.trace_add("write", refresh_paths); refresh_paths()

    status = tb.StringVar(value="Listo.")
    status_bar = tb.Label(app, textvariable=status, bootstyle=INFO, anchor=W, padding=(16,6)); status_bar.pack(fill=X)

    session = {"title": "Incidencia", "steps": []}
    _monitor_index = {"val": None}

    def ensure_mss():
        try:
            import mss, mss.tools
            return True
        except Exception:
            Messagebox.show_error("Falta el paquete 'mss'. Instala:\n\npip install mss", "SNAP")
            return False

    def select_monitor_modal(master, monitors):
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
        def ok(): res["index"] = sel.current(); win.destroy()
        def cancel(): res["index"] = None; win.destroy()
        tb.Button(btns, text="Cancelar", command=cancel, bootstyle=SECONDARY).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Aceptar", command=ok, bootstyle=PRIMARY).pack(side=RIGHT)
        win.wait_window(); return res["index"]

    def select_monitor(sct):
        monitors = sct.monitors
        if not monitors:
            Messagebox.show_error("No se detectaron monitores.", "SNAP"); return None, None
        idx = _monitor_index["val"]
        if idx is None or idx >= len(monitors) or idx < 0:
            sel = select_monitor_modal(app, monitors)
            if sel is None: return None, None
            idx = sel; _monitor_index["val"] = idx
        return monitors, idx

    def snap_externo_monitor():
        if not ensure_mss(): return
        import mss, mss.tools
        with mss.mss() as sct:
            monitors, idx = select_monitor(sct)
            if monitors is None: return
            mon = monitors[idx]
            data = text_modal(app, f"SNAP externo (monitor {idx if idx>0 else 'Todos'})")
            if data is None or data.get("cancel"): return
            evid_dir = Path(ev_var.get()); evid_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S"); out_path = evid_dir / f"snap_ext_monitor{idx}_{ts}.png"
            img = sct.grab(mon); mss.tools.to_png(img.rgb, img.size, output=str(out_path))

        step = {"cmd": "snap_externo", "shots": [str(out_path)]}
        if data.get("descripcion"): step["desc"] = data["descripcion"]
        if data.get("consideraciones"): step["consideraciones"] = data["consideraciones"]
        if data.get("observacion"): step["observacion"] = data["observacion"]
        session["steps"].append(step); status.set(f"🖥️ SNAP externo agregado (monitor {idx})")

    def snap_region_all():
        if not ensure_mss(): return
        import mss, mss.tools
        with mss.mss() as sct:
            desktop = sct.monitors[0]
            bbox = select_region_overlay(app, desktop)
            if not bbox:
                status.set("Selección cancelada."); return
            data = text_modal(app, "SNAP región")
            if data is None or data.get("cancel"): return

            left, top, width, height = bbox
            region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
            evid_dir = Path(ev_var.get()); evid_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S"); out_path = evid_dir / f"snap_region_all_{ts}.png"
            img = sct.grab(region); mss.tools.to_png(img.rgb, img.size, output=str(out_path))

        step = {"cmd": "snap_region_all", "shots": [str(out_path)]}
        if data.get("descripcion"): step["desc"] = data["descripcion"]
        if data.get("consideraciones"): step["consideraciones"] = data["consideraciones"]
        if data.get("observacion"): step["observacion"] = data["observacion"]
        session["steps"].append(step); status.set("📐 SNAP región (todas) agregado")

    def generar_doc():
        if not session["steps"]:
            if not Messagebox.yesno("No hay pasos. ¿Generar documento vacío?", "Reporte"): return
        outp = Path(doc_var.get()); outp.parent.mkdir(parents=True, exist_ok=True)
        build_word(session.get("title"), session["steps"], str(outp))
        Messagebox.showinfo(f"Reporte generado:\n{outp}", f"Reporte Guardado En: \n{outp}"); status.set("✅ Reporte generado")

    def modal_confluence_url():
        win = tb.Toplevel(app); win.title("Importar a Confluence"); win.transient(app); win.grab_set(); win.geometry("800x300")
        frm = tb.Frame(win, padding=15); frm.pack(fill=BOTH, expand=YES)
        tb.Label(frm, text="URL de la página de Confluence", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(0,8))

        tb.Label(frm, text="ENTORNO", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(10,2))
        hist = load_url_history(CONF_FILE, "https://sistemaspremium.atlassian.net/wiki/spaces/")
        urlv = tb.StringVar(value=hist[0] if hist else "")
        cmb = tb.Combobox(frm, textvariable=urlv, values=hist, width=70, bootstyle="light"); cmb.pack(fill=X)
        cmb.icursor("end")

        tb.Label(frm, text="ESPACIO", font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(10,2))
        histspaces = load_url_history(SPACES_FILE, "")
        urlvspaces = tb.StringVar(value=histspaces[0] if histspaces else "")
        cmbspaces = tb.Combobox(frm, textvariable=urlvspaces, values=histspaces, width=70, bootstyle="light"); cmbspaces.pack(fill=X)
        cmbspaces.icursor("end")
        
        res = {"url": None}
        btns = tb.Frame(frm); btns.pack(fill=X, pady=(12,0))
        def ok(): res["url"] = ((urlv.get() + urlvspaces.get())  or "").strip(); win.destroy()
        def cancel(): res["url"] = None; win.destroy()
        tb.Button(btns, text="Cancelar", command=cancel, bootstyle=SECONDARY).pack(side=RIGHT, padx=6)
        tb.Button(btns, text="Aceptar", command=ok, bootstyle=PRIMARY).pack(side=RIGHT)
        win.wait_window(); return res["url"]

    def importar_confluence():
        if not session["steps"]:
            Messagebox.showwarning( "Confluence" , "No hay pasos en la sesión."); return
        outp = Path(doc_var.get()); outp.parent.mkdir(parents=True, exist_ok=True)
        build_word(session.get("title"), session["steps"], str(outp))


        url_c = modal_confluence_url()
        if not url_c: return
        save_url_to_history(CONF_FILE, url_c)

        status.set("⏳ Preparando contenido y abriendo Confluence...")
        open_chrome_with_profile(url_c, "Default")
        log_path = Path("sessions") / f"{session.get("title")}_confluence.log"

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

    btns = tb.Frame(app, padding=(16,6)); btns.pack(fill=X)
    def abrir_nav():
        url = (url_var.get() or DEFAULT_URL).strip() or DEFAULT_URL
        ok, msg = open_chrome_with_profile(url, "Default")
        if ok: status.set("✅ Chrome abierto (perfil Default)")
        else: Messagebox.show_error(f"No se pudo abrir Chrome: {msg}", "Navegador")

    tb.Button(btns, text="🔗 Abrir navegador", command=abrir_nav, bootstyle=PRIMARY, width=18).pack(side=LEFT, padx=(0,8))
    tb.Button(btns, text="🖥️ SNAP externo", command=snap_externo_monitor, bootstyle=INFO, width=16).pack(side=LEFT, padx=8)
    tb.Button(btns, text="📐 SNAP región", command=snap_region_all, bootstyle=INFO, width=16).pack(side=LEFT, padx=8)
    tb.Button(btns, text="📥 Importar Confluence", command=importar_confluence, bootstyle=SUCCESS, width=22).pack(side=LEFT, padx=8)
    tb.Button(btns, text="✅ DONE", command=generar_doc, bootstyle=WARNING, width=12).pack(side=RIGHT)

    app.mainloop()

if __name__ == "__main__":
    run_gui()
