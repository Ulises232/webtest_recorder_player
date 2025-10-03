
# utils/core_cdp.py — FIX v3.2.1
# Simplifica la apertura de Chrome: SIEMPRE lanza un contexto persistente
# con el perfil Default (sin intentar CDP en 127.0.0.1:9222). De este modo
# evitamos el error connect_over_cdp ECONNREFUSED y el GUI puede detectar
# correctamente la página activa.

from pathlib import Path
import os
import shutil
from typing import Tuple, Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# Detección de rutas Chrome/Perfil
def _guess_chrome_exe() -> Optional[str]:
    # Rutas comunes
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("chrome"),  # si está en PATH
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def _guess_user_data_dir() -> str:
    base = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    return base if os.path.isdir(base) else str(Path.home() / "AppData/Local/Google/Chrome/User Data")

def open_or_attach_chrome(
    start_url: str,
    normal_window: bool = True,
    user_data_dir: Optional[str] = None,
    profile_directory: str = "Default",
):
    """
    Lanza Chrome con perfil persistente (Default) y devuelve (pw, browser, context, page).
    No intenta conectar por CDP a puertos (evita ECONNREFUSED 127.0.0.1:9222).
    """
    user_data_dir = user_data_dir or _guess_user_data_dir()
    chrome_exe = _guess_chrome_exe()

    pw = sync_playwright().start()

    # Preferimos channel="chrome" si no tenemos ruta exacta
    kwargs = dict()
    if chrome_exe and os.path.exists(chrome_exe):
        kwargs["executable_path"] = chrome_exe
    else:
        kwargs["channel"] = "chrome"

    args = [
        f"--profile-directory={profile_directory}",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-popup-blocking",
        "--disable-dev-shm-usage",
        "--no-default-browser-check",
        "--no-first-run",
        "--start-maximized",
    ]

    if not normal_window and start_url:
        # Ventana tipo "app" sin barras (más limpia). Si estorba, cambiar a normal_window=True
        args.append(f"--app={start_url}")

    context = pw.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
        args=args,
        **kwargs,
    )

    browser = context.browser

    # Page: usa la existente o crea una
    page = None
    try:
        pages = context.pages
        page = next((p for p in pages if not p.is_closed()), None)
    except Exception:
        page = None

    if page is None:
        page = context.new_page()

    # Si no abrimos con --app, navegamos ahora
    if normal_window and start_url:
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=120000)
        except Exception:
            # no interrumpimos: la GUI podrá reintentar
            pass

    try:
        page.bring_to_front()
    except Exception:
        pass

    return pw, browser, context, page


def close_cdp(pw_obj):
    try:
        pw_obj.stop()
    except Exception:
        pass
