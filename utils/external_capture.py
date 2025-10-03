
# utils/external_capture.py — Captura externa (Windows)
# Incluye utilidades de monitores y ventanas.
import time, ctypes
from pathlib import Path

try:
    import mss, mss.tools
    HAS_MSS = True
except Exception:
    HAS_MSS = False

user32 = ctypes.windll.user32
try:
    dwmapi = ctypes.windll.dwmapi
except Exception:
    dwmapi = None

SW_RESTORE = 9

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)]

def ts():
    return time.strftime("%Y%m%d-%H%M%S")

def _get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value or ""

def _is_window_visible(hwnd):
    return bool(user32.IsWindowVisible(hwnd))

def _get_window_rect(hwnd):
    if dwmapi is not None:
        rect = RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        res = dwmapi.DwmGetWindowAttribute(ctypes.c_void_p(hwnd),
                                           ctypes.c_uint(DWMWA_EXTENDED_FRAME_BOUNDS),
                                           ctypes.byref(rect),
                                           ctypes.sizeof(rect))
        if res == 0 and (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0:
            return (rect.left, rect.top, rect.right, rect.bottom)
    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None

def list_windows(visible_only=True, min_title=2):
    wins = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum_proc(hWnd, lParam):
        title = _get_window_text(hWnd)
        if visible_only and not _is_window_visible(hWnd):
            return True
        if title and len(title.strip()) >= min_title:
            rect = _get_window_rect(hWnd)
            if rect:
                wins.append({"hwnd": int(hWnd), "title": title, "rect": rect})
        return True
    user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)
    wins.sort(key=lambda w: w["title"].lower())
    return wins

def _capture_region(bbox, out_path):
    l, t, r, b = bbox
    w, h = max(1, r - l), max(1, b - t)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if HAS_MSS:
        with mss.mss() as sct:
            mon = {"left": int(l), "top": int(t), "width": int(w), "height": int(h)}
            img = sct.grab(mon)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))
            return str(out_path)
    else:
        from PIL import ImageGrab
        im = ImageGrab.grab(bbox=(int(l), int(t), int(r), int(b)))
        im.save(str(out_path))
        return str(out_path)

def capture_active_window(out_dir, name_prefix="ext"):
    out_dir = Path(out_dir)
    out_path = out_dir / f"{ts()}_{name_prefix}.png"
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("No hay ventana activa ahora mismo.")
    rect = _get_window_rect(hwnd)
    if not rect:
        raise RuntimeError("No pude obtener rectangulo de la ventana activa.")
    return _capture_region(rect, out_path)

def capture_monitor(index, out_dir, name_prefix="screen"):
    out_dir = Path(out_dir)
    out_path = out_dir / f"{ts()}_{name_prefix}{index}.png"
    if HAS_MSS:
        with mss.mss() as sct:
            mon = sct.monitors[index]
            bbox = (mon["left"], mon["top"], mon["left"]+mon["width"], mon["top"]+mon["height"])
            return _capture_region(bbox, out_path)
    else:
        from PIL import ImageGrab
        im = ImageGrab.grab()
        im.save(str(out_path))
        return str(out_path)

def list_monitors():
    mons = []
    if HAS_MSS:
        with mss.mss() as sct:
            for i, mon in enumerate(sct.monitors):
                mons.append({"index": i, "left": mon["left"], "top": mon["top"],
                             "width": mon["width"], "height": mon["height"]})
    else:
        SM_CXSCREEN = 0; SM_CYSCREEN = 1
        cx = user32.GetSystemMetrics(SM_CXSCREEN)
        cy = user32.GetSystemMetrics(SM_CYSCREEN)
        mons.append({"index": 1, "left": 0, "top": 0, "width": cx, "height": cy})
    return mons
