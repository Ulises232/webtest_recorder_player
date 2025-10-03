# utils/config_store.py — Historial simple de URLs para Confluence/GUI
import json
from pathlib import Path

URLS_FILE = Path("url_history.json")

def load_urls(default: str) -> list[str]:
    try:
        if URLS_FILE.exists():
            data = json.loads(URLS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return [default]

def remember_url(url: str, limit: int = 15):
    url = (url or "").strip()
    if not url:
        return
    data = load_urls(url)
    if any(u.lower() == url.lower() for u in data):
        data = [url] + [u for u in data if u.lower() != url.lower()]
    else:
        data = [url] + data
    data = data[:limit]
    try:
        URLS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
