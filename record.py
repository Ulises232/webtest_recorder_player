
import argparse, yaml, sys, shlex, os
from pathlib import Path
from playwright.sync_api import TimeoutError as PWTimeoutError
from utils.core import browser_page, screenshot
from utils.report_word import build_word

# NEW: external app capture
try:
    from utils.external_capture import capture_active_window, capture_window_by_title, list_windows
    HAS_EXT = True
except Exception as e:
    HAS_EXT = False

HELP = """\
Comandos disponibles:
  snap
  nav <url|/ruta>
  click <selector>
  fill <selector> :: <valor>
  wait <selector>
  assert_text <texto>
  base <url_base>
  title <titulo>
  save          (guardar YAML manual, opcional)
  done
  help

  # Captura de apps externas (Windows)
  wins                   → lista ventanas visibles
  snap_ext               → captura la ventana ACTIVA (app externa)
  snap_win <texto>       → busca por titulo (parcial) y captura esa ventana

Notas:
  - No hay captura inicial automatica: la primera captura ocurre con 'snap' o al final de cada comando.
  - Para 'snap_ext' y 'snap_win' se pedira Descripcion y Consideraciones y se integraran igual que los demas pasos.
"""

_CONIN = None

def ask(prompt):
    import sys, os
    global _CONIN
    print(prompt, end="", flush=True)
    try:
        if sys.stdin and sys.stdin.isatty():
            line = sys.stdin.readline()
            if line != "":
                return line.rstrip("\r\n")
    except Exception:
        pass
    if os.name == "nt":
        try:
            if _CONIN is None:
                _CONIN = open("CONIN$", "r", encoding="utf-8", errors="replace")
            line = _CONIN.readline()
            if line != "":
                return line.rstrip("\r\n")
        except Exception:
            pass
    try:
        return input().rstrip("\r\n")
    except Exception:
        print("\n[ERR] No puedo leer entrada interactiva.")
        return ""

def safe_goto(page, url: str):
    if not url:
        return None
    print(f"[NAV] Ir a: {url}")
    try:
        r = page.goto(url, wait_until="domcontentloaded", timeout=120000)
        print("[NAV] domcontentloaded")
        return r
    except PWTimeoutError:
        print("[NAV] Timeout domcontentloaded, intento commit...")
        try:
            page.goto(url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            print("[NAV] commit + domcontentloaded")
        except PWTimeoutError:
            print("[NAV] No hubo domcontentloaded; continuo.")
        return None

def resolve_yaml_path(out_yaml_arg: str, doc_out: str):
    if out_yaml_arg:
        return Path(out_yaml_arg)
    if doc_out:
        return Path(doc_out).with_suffix(".yml")
    return Path("sessions/manual_save.yml")

def main(out_yaml: str, evidence_dir: str, start_url: str, doc_out: str=None):
    session = {"title": "Flujo grabado", "base": "", "steps": []}
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    with browser_page(start_url=start_url) as page:
        print("[REC] Recorder activo. Escribe 'help' para ver comandos.\n")

        while True:
            raw = ask("rec> ")
            if not raw:
                continue
            parts = shlex.split(raw, posix=False)
            cmd = parts[0].lower()

            if cmd == "help":
                print(HELP)
                if not HAS_EXT:
                    print("\n[INFO] Para capturar apps externas instala 'Pillow' o 'mss' (recomendado):")
                    print("  pip install pillow   (o)   pip install mss pillow")
                continue

            if cmd == "done":
                break

            if cmd == "save":
                yml_path = resolve_yaml_path(out_yaml, doc_out)
                yml_path.parent.mkdir(parents=True, exist_ok=True)
                with open(yml_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(session, f, allow_unicode=True, sort_keys=False)
                print(f"[REC] YAML guardado manualmente en: {yml_path}")
                continue

            if cmd == "title":
                title = raw[len("title"):].strip()
                session["title"] = title or session["title"]
                print(f"[REC] Titulo: {session['title']}")
                continue

            if cmd == "base":
                base = raw[len("base"):].strip()
                session["base"] = base
                print(f"[REC] BASE_URL: {session['base']}")
                continue

            if cmd == "snap":
                desc = ask("   descripcion (opcional): ")
                cons = ask("   consideraciones (opcional): ")
                shot = screenshot(page, Path(evidence_dir), "snap")
                step = {"cmd": "snap", "shots": [shot]}
                if desc: step["desc"] = desc
                if cons: step["consideraciones"] = cons
                session["steps"].append(step)
                print("[REC] SNAP agregado.\n")
                continue

            # ======== EXTERNAL APP CAPTURE ========
            if cmd == "wins":
                if not HAS_EXT:
                    print("[ERR] Falta modulo utils.external_capture o dependencias (mss/pillow).")
                    continue
                try:
                    from utils.external_capture import list_windows
                    wins = list_windows()
                    print("Ventanas visibles:")
                    for i, w in enumerate(wins, 1):
                        l,t,r,b = w["rect"]
                        print(f"  {i:2d}. {w['title']}  ({l},{t},{r},{b})")
                except Exception as e:
                    print(f"[ERR] No se pudo listar ventanas: {e}")
                continue

            if cmd == "snap_ext":
                if not HAS_EXT:
                    print("[ERR] Falta modulo utils.external_capture o dependencias (mss/pillow).")
                    continue
                try:
                    shot = capture_active_window(str(evidence_dir), "ext")
                    desc = ask("   descripcion (opcional): ")
                    cons = ask("   consideraciones (opcional): ")
                    step = {"cmd": "snap_ext", "shots": [shot]}
                    if desc: step["desc"] = desc
                    if cons: step["consideraciones"] = cons
                    session["steps"].append(step)
                    print("[REC] SNAP externo agregado.\n")
                except Exception as e:
                    print(f"[ERR] snap_ext fallo: {e}")
                continue

            if cmd == "snap_win":
                if not HAS_EXT:
                    print("[ERR] Falta modulo utils.external_capture o dependencias (mss/pillow).")
                    continue
                arg = raw[len("snap_win"):].strip()
                if not arg:
                    print("Uso: snap_win <texto en titulo>")
                    continue
                try:
                    shot = capture_window_by_title(arg, str(evidence_dir), "extwin")
                    desc = ask("   descripcion (opcional): ")
                    cons = ask("   consideraciones (opcional): ")
                    step = {"cmd": "snap_win", "shots": [shot]}
                    if desc: step["desc"] = desc
                    if cons: step["consideraciones"] = cons
                    session["steps"].append(step)
                    print("[REC] SNAP de ventana especifica agregado.\n")
                except Exception as e:
                    print(f"[ERR] snap_win fallo: {e}")
                continue
            # ======================================

            # --- Otros comandos web ---
            step = {"cmd": cmd, "shots": []}

            if cmd == "nav":
                arg = raw[len("nav"):].strip()
                url = arg
                if session.get("base") and arg.startswith("/"):
                    url = session["base"].rstrip("/") + arg
                safe_goto(page, url)
                step["url"] = url

            elif cmd == "click":
                sel = raw[len("click"):].strip()
                page.locator(sel).click()
                step["selector"] = sel

            elif cmd == "fill":
                arg = raw[len("fill"):].strip()
                if " :: " not in arg:
                    print("[WARN] Usa: fill <selector> :: <valor>")
                    continue
                sel, val = arg.split(" :: ", 1)
                page.locator(sel.strip()).fill(val)
                step["selector"] = sel.strip()
                step["value"] = val

            elif cmd == "wait":
                sel = raw[len("wait"):].strip()
                page.wait_for_selector(sel, timeout=20000)
                step["selector"] = sel

            elif cmd == "assert_text":
                txt = raw[len("assert_text"):].strip()
                loc = page.locator(f"text={txt}")
                assert loc.first.is_visible(), f"No se encontro texto visible: {txt}"
                step["text"] = txt

            else:
                print("[ERR] Comando no reconocido. Escribe 'help'.")
                continue

            # Pide descripcion y evidencia al final de cada comando web
            desc = ask("   descripcion (opcional): ")
            if desc: step["desc"] = desc
            shot = screenshot(page, Path(evidence_dir), cmd)
            step["shots"].append(shot)
            session["steps"].append(step)
            print("[REC] Paso agregado. Usa 'save' para (opcional) guardar YAML o 'done' para finalizar.\n")

    # Al finalizar: SOLO DOCX + evidencias (NO YAML automatico)
    docx_path = Path(doc_out) if doc_out else Path("sessions/flujo.docx")
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    build_word(session.get("title"), session["steps"], str(docx_path))
    print(f"[REC] Reporte Word: {docx_path}")
    print("[REC] Listo (sin YAML final). Use 'save' durante la sesion si desea un YAML.")
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="(OPCIONAL) Ruta YAML si usas 'save' para guardar manualmente")
    ap.add_argument("--evidence", default="evidencia/rec", help="Carpeta de capturas")
    ap.add_argument("--start-url", default="", help="URL inicial a abrir automaticamente (opcional)")
    ap.add_argument("--doc", dest="doc_out", default=None, help="Ruta DOCX de salida (opcional)")
    args = ap.parse_args()
    raise SystemExit(main(args.out, args.evidence, args.start_url, args.doc_out))
