"""Translate short titles/snippets to Simplified Chinese. No API key or signup."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Callable

from save_dates.config import DATA_DIR, TRANSLATE_CACHE_PATH

_MAX_CHARS = 220
_CACHE_LIMIT = 2500
_TIMEOUT = 3.5
_lock = threading.Lock()
_cache: dict[str, str] | None = None
_queue: list[str] = []
_worker: threading.Thread | None = None
_notify_timer: threading.Timer | None = None
_on_translated: Callable[[], None] | None = None


def network_translate_enabled() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if os.environ.get("SAVE_DATES_NO_TRANSLATE") == "1":
        return False
    return True


def cache_path() -> Path:
    return TRANSLATE_CACHE_PATH


def _load_cache() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    path = cache_path()
    data: dict[str, str] = {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("items") if isinstance(raw, dict) else raw
        if isinstance(items, dict):
            data = {str(k): str(v) for k, v in items.items() if k and v}
    except Exception:
        data = {}
    _cache = data
    return _cache


def _save_cache() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    items = _load_cache()
    if len(items) > _CACHE_LIMIT:
        extra = len(items) - _CACHE_LIMIT
        for key in list(items.keys())[:extra]:
            items.pop(key, None)
    cache_path().write_text(
        json.dumps({"v": 1, "items": items}, ensure_ascii=False),
        encoding="utf-8",
    )


def cache_get(text: str) -> str:
    key = (text or "").strip()
    if not key:
        return ""
    with _lock:
        return _load_cache().get(key) or ""


def cache_put(text: str, translated: str) -> None:
    key = (text or "").strip()
    value = (translated or "").strip()
    if not key or not value:
        return
    with _lock:
        items = _load_cache()
        items[key] = value
        _save_cache()


def _fetch_google(text: str) -> str:
    import httpx

    resp = httpx.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    parts: list[str] = []
    if isinstance(data, list) and data and isinstance(data[0], list):
        for chunk in data[0]:
            if isinstance(chunk, list) and chunk and isinstance(chunk[0], str):
                parts.append(chunk[0])
    return "".join(parts).strip()


def _fetch_mymemory(text: str) -> str:
    import httpx

    resp = httpx.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": "en|zh-CN"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        return ""
    payload = data.get("responseData") or {}
    if isinstance(payload, dict):
        value = str(payload.get("translatedText") or "").strip()
        if value.lower() == text.lower():
            return ""
        return value
    return ""


def _fetch_zh(text: str) -> str:
    try:
        got = _fetch_google(text)
        if got:
            return got
    except Exception:
        pass
    try:
        return _fetch_mymemory(text)
    except Exception:
        return ""


def translate_to_zh(text: str, *, network: bool | None = None) -> str:
    """Return Simplified Chinese, or empty string if offline/blocked/unneeded."""
    source = (text or "").strip()
    if not source:
        return ""
    clipped = source[:_MAX_CHARS]
    cached = cache_get(clipped)
    if cached:
        return cached
    if network is None:
        network = network_translate_enabled()
    if not network:
        return ""
    try:
        translated = _fetch_zh(clipped)
    except Exception:
        translated = ""
    if translated and translated.strip() and translated.strip() != clipped:
        cache_put(clipped, translated.strip())
        return translated.strip()
    return ""


def enqueue_translation(text: str) -> None:
    source = (text or "").strip()[:_MAX_CHARS]
    if not source or not network_translate_enabled():
        return
    if cache_get(source):
        return
    global _worker
    with _lock:
        if source not in _queue:
            _queue.append(source)
        alive = _worker is not None and _worker.is_alive()
        if not alive:
            _worker = threading.Thread(target=_run_queue, name="save-dates-translate", daemon=True)
            _worker.start()


def set_translated_callback(callback: Callable[[], None] | None) -> None:
    global _on_translated
    _on_translated = callback


def _schedule_notify() -> None:
    global _notify_timer

    def fire() -> None:
        cb = _on_translated
        if cb:
            try:
                cb()
            except Exception:
                pass

    if _notify_timer is not None:
        _notify_timer.cancel()
    _notify_timer = threading.Timer(0.9, fire)
    _notify_timer.daemon = True
    _notify_timer.start()


def _run_queue() -> None:
    while True:
        with _lock:
            if not _queue:
                return
            text = _queue.pop(0)
        if cache_get(text):
            continue
        try:
            translated = _fetch_zh(text)
        except Exception:
            translated = ""
        if translated and translated.strip() != text:
            cache_put(text, translated.strip())
            _schedule_notify()
