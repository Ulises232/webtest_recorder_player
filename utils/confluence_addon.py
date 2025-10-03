# utils/confluence_addon.py — Botón plug&play "Importar Confluence" para TU GUI actual
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from .confluence_ui import import_steps_to_confluence
from .config_store import load_urls, remember_url

def attach_confluence_button(btn_container, get_url_callable, session_ref: dict, status_var: tk.StringVar, default_url: str):
    """
    Añade un botón "📥 Importar Confluence" a tu GUI sin romper nada.
    - btn_container: frame donde colocas los demás botones.
    - get_url_callable: función sin args que devuelve el string URL (leer de tu combobox o entry).
    - session_ref: dict con {"steps": [...] } (igual al que ya usas).
    - status_var: StringVar para mostrar estatus.
    - default_url: URL por defecto para inicializar historial si hace falta.

    Ejemplo de uso en tu GUI:
        from utils.confluence_addon import attach_confluence_button
        attach_confluence_button(btns, lambda: url_var.get(), session, status, DEFAULT_URL)
    """
    def do_import():
        steps = session_ref.get("steps") or []
        if not steps:
            messagebox.showwarning("Importar", "No hay pasos en sesión."); return
        url = (get_url_callable() or "").strip()
        if not url:
            messagebox.showwarning("Importar", "Escribe/selecciona la URL de Confluence."); return

        remember_url(url)
        status_var.set("⏳ Importando en Confluence (simular UI)...")
        import_btn.config(state="disabled")

        def worker():
            ok, msg = import_steps_to_confluence(url, steps, add_title=None)
            def finish():
                import_btn.config(state="normal")
                status_var.set(("✅ " if ok else "❌ ") + msg)
                (messagebox.showinfo if ok else messagebox.showerror)("Importar Confluence", msg)
            btn_container.after(0, finish)
        Thread(target=worker, daemon=True).start()

    import_btn = ttk.Button(btn_container, text="📥  Importar Confluence", command=do_import)
    import_btn.pack(side="left", padx=8)
    return import_btn
