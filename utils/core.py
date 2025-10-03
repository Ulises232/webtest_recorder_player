# utils/core.py — v2.CorrecionGoogle (Chrome persistente con perfil Default)
# Abre Google Chrome estable con el perfil del usuario (NO incognito), conserva cookies/sesiones/autocompletado.
# Mantiene la API browser_page(start_url) para no romper GUIs existentes.
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import os, time

# Tamaño/posición (puedes sobrescribir con variables de entorno si quieres)
WIN_WIDTH  = int(os.environ.get("WT_WINDOW_WIDTH",  "1920"))
WIN_HEIGHT = int(os.environ.get("WT_WINDOW_HEIGHT", "1080"))
WIN_X      = int(os.environ.get("WT_WINDOW_X",      "0"))
WIN_Y      = int(os.environ.get("WT_WINDOW_Y",      "0"))

def _detect_chrome_profile() -> Tuple[str, str]:
    r"""
    Determina el 'user_data_dir' y el 'profile-directory' de Chrome.
    Prioriza variables de entorno si existen:
      WT_USER_DATA_DIR  -> C:\\Users\\<User>\\AppData\\Local\\Google\\Chrome\\User Data
      WT_PROFILE_DIR    -> Default  (o 'Profile 1', etc.)
    Si no, usa LOCALAPPDATA con perfil Default.
    """
    udd = os.environ.get("WT_USER_DATA_DIR")
    pdir = os.environ.get("WT_PROFILE_DIR") or "Default"

    if not udd:
        # Ruta estándar en Windows (puedes ajustar si usas otra cuenta)
        local = os.environ.get("LOCALAPPDATA") or r"C:\Users\Jonathan\AppData\Local"
        udd = str(Path(local) / "Google" / "Chrome" / "User Data")

    return udd, pdir

def _launch_persistent_context(user_data_dir: str, args: list[str]):
    r"""
    Lanza Chrome estable con perfil PERSISTENTE (no incognito) usando Playwright.
    """
    from playwright.sync_api import sync_playwright, Error as PWError
    pw = sync_playwright().start()
    try:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",          # Fuerza Google Chrome estable
            headless=False,            # Ventana visible
            no_viewport=True,          # Usa tamaño real de la ventana
            accept_downloads=True,     # Habilita descargas
            args=args,
        )
        return pw, ctx
    except PWError as e:
        try:
            pw.stop()
        except Exception:
            pass
        raise RuntimeError(
            "No se pudo abrir Chrome con el perfil seleccionado.\n"
            "Cierra todas las ventanas de Chrome y vuelve a intentar.\n\n"
            f"Detalle Playwright: {e}"
        )

def open_chrome_persistent(start_url: Optional[str] = None, app_mode: bool = True):
    r"""
    Abre Chrome con el perfil persistente del usuario (Default por defecto).
    - app_mode=True: usa --app=<url> (ventana tipo aplicación, sin barra/tabs) si se proporciona start_url.
    - app_mode=False: abre ventana normal.
    Devuelve (pw, ctx, page). Si hay start_url y no usamos --app, navega a la URL.
    """
    user_data_dir, profile_dir = _detect_chrome_profile()
    udd_path = Path(user_data_dir)
    if not udd_path.exists():
        raise RuntimeError(f"User Data dir no existe: {udd_path}\nAjusta WT_USER_DATA_DIR.")

    args = [
        f"--profile-directory={profile_dir}",    # PERFIL: Default (o el que definas)
        f"--window-position={WIN_X},{WIN_Y}",
        f"--window-size={WIN_WIDTH},{WIN_HEIGHT}",
        "--start-maximized",
        # NO usar --incognito / --guest
    ]
    if app_mode and start_url:
        args.append(f"--app={start_url}")        # Ventana tipo "app" (sin marco)

    print("[REC] Chrome (perfil persistente)")
    print(f"      user_data_dir      = {udd_path}")
    print(f"      profile_directory  = {profile_dir}")

    pw, ctx = _launch_persistent_context(str(udd_path), args)

    # Detectar/crear la página
    page = None
    if ctx.pages:
        # Si estamos en app_mode, usualmente habrá una página ya con la URL del app
        for p in ctx.pages:
            try:
                if p.url and p.url != "about:blank":
                    page = p
                    break
            except Exception:
                pass
        if page is None:
            page = ctx.pages[0]
    else:
        page = ctx.new_page()

    # Si no estamos en --app o quedamos en about:blank, navegar
    if start_url and (not app_mode or (page.url in ("", "about:blank"))):
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=120000)
        except Exception:
            time.sleep(0.8)
            page.goto(start_url, wait_until="domcontentloaded", timeout=120000)

    try:
        page.bring_to_front()
    except Exception:
        pass

    return pw, ctx, page

def close_persistent(ctx, pw):
    try: ctx.close()
    except Exception: pass
    try: pw.stop()
    except Exception: pass

def screenshot(page, evidence_dir, prefix="snap"):
    r"""
    Toma captura SOLO del área visible (no full page) en PNG.
    """
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = evidence_dir / f"{prefix}_{ts}.png"
    page.screenshot(path=str(path), full_page=False)
    return str(path)

# --- Compatibilidad: browser_page(start_url) ---
# Se mantiene para no romper el flujo de tus GUIs actuales.
from contextlib import contextmanager

@contextmanager
def browser_page(start_url: Optional[str] = None):
    r"""
    Compatibilidad con código existente:
      with browser_page(start_url) as page: ...
    Lanza Chrome con perfil persistente del usuario. Si pasas start_url -> app_mode=True.
    """
    pw, ctx, page = open_chrome_persistent(start_url=start_url, app_mode=bool(start_url))
    try:
        yield page
    finally:
        try:
            close_persistent(ctx, pw)
        except Exception:
            pass
