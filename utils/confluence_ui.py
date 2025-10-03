# utils/confluence_ui.py — v5.1 (LOG + paso a paso)
import time, io
from pathlib import Path

def _clipboard_set_text(text: str):
    try:
        import pyperclip
        pyperclip.copy(text or "")
        return True, "pyperclip"
    except Exception:
        try:
            import win32clipboard as cb, win32con
            cb.OpenClipboard(); cb.EmptyClipboard()
            cb.SetClipboardData(win32con.CF_UNICODETEXT, text or "")
            cb.CloseClipboard()
            return True, "win32clipboard"
        except Exception as e:
            return False, str(e)

def _clipboard_set_image_from_path(img_path: Path):
    from PIL import Image
    import win32clipboard as cb, win32con
    im = Image.open(str(img_path)).convert("RGB")
    with io.BytesIO() as output:
        im.save(output, "BMP")
        data = output.getvalue()[14:]  # quitar header BMP
    cb.OpenClipboard(); cb.EmptyClipboard()
    cb.SetClipboardData(win32con.CF_DIB, data)
    cb.CloseClipboard()
    return True, "win32clipboard CF_DIB"

def _send_ctrl_v():
    import time
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "v"); time.sleep(0.15); 
        return True, "pyautogui"
    except Exception:
        try:
            import keyboard
            keyboard.send("ctrl+v"); time.sleep(0.15); 
            return True, "keyboard"
        except Exception as e:
            return False, str(e)

def _send_enter():
    import time
    try:
        import pyautogui
        pyautogui.press("enter")
        return True, "pyautogui"
    except Exception:
        try:
            import keyboard
            keyboard.send("enter")
            return True, "keyboard"
        except Exception as e:
            return False, str(e)

def copy_text_and_paste(text: str, logger=None):
    ok, how = _clipboard_set_text(text or "")
    if logger: logger(f"[TEXT] set_clipboard={ok} via {how}")
    if not ok: return False, how
    time.sleep(0.25)
    ok2, how2 = _send_ctrl_v()
    if logger: logger(f"[TEXT] paste={ok2} via {how2}")
    return ok2, how2

def copy_image_and_paste(path: str, logger=None):
    p = Path(path)
    if not p.exists(): return False, f"Imagen no encontrada: {p}"
    ok, how = _clipboard_set_image_from_path(p)
    if logger: logger(f"[IMG] set_clipboard={ok} via {how}")
    time.sleep(0.25)
    ok2, how2 = _send_ctrl_v()
    if logger: logger(f"[IMG] paste={ok2} via {how2}")
    return ok2, how2

def import_steps_to_confluence(steps, delay_sec=5, log_path=None):
    logs = []
    def _log(msg): logs.append(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {msg}")
    _log("=== Import to Confluence START ===")
    time.sleep(delay_sec)
    pasted_count, errors = 0, []

    for i, st in enumerate(steps, start=1):
        _log(f"-- Paso {i} --")
        lines = f"PASO {i}"
        text_block = lines
        copy_text_and_paste(text_block, logger=_log);_send_enter(); 

        desc = st.get("desc") or st.get("descripcion") or ""
        if desc: 
            lines = ''
            text_block = f'📝 Descripción: {desc}'
            copy_text_and_paste(text_block, logger=_log)
            _send_enter()

        for shot in st.get("shots", []):
            copy_image_and_paste(shot, logger=_log)
            time.sleep(0.3)

        cons = st.get("consideraciones") or st.get("consideracion") or ""
        if cons: 
            lines = ''
            text_block = f'⚠️ Consideración: {cons}'
            copy_text_and_paste(text_block, logger=_log)
            _send_enter()

        obs = st.get("observacion") or ""
        if obs: 
            lines = ''
            text_block = f'🔎 Observación: {obs}'
            copy_text_and_paste(text_block, logger=_log)
            _send_enter()

        _send_enter();_send_enter()
        
        pasted_count += 1

    if log_path:
        Path(log_path).write_text("\\n".join(logs), encoding="utf-8")

    return pasted_count, errors
