"""Resolve UI language from the OS until the user picks 中/EN."""

from __future__ import annotations

import locale
import os
import sys

# Primary language ID for Chinese (zh, zh-CN, zh-TW, zh-HK, …).
_LANG_CHINESE = 0x04


def locale_tag_is_chinese(tag: str | None) -> bool:
    raw = (tag or "").strip()
    if not raw:
        return False
    normalized = raw.replace("_", "-").lower()
    return normalized.startswith("zh") or "chinese" in normalized or "中文" in raw


def _windows_lang_tags() -> list[str]:
    if sys.platform != "win32":
        return []
    tags: list[str] = []
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        langid = int(kernel32.GetUserDefaultUILanguage())
        if (langid & 0x3FF) == _LANG_CHINESE:
            tags.append("zh")
        buf = ctypes.create_unicode_buffer(85)
        get_name = getattr(kernel32, "GetUserDefaultLocaleName", None)
        if get_name and get_name(buf, len(buf)):
            tags.append(buf.value)
    except Exception:
        pass
    return tags


def system_ui_lang() -> str:
    """Chinese if Windows UI/locale is zh*; otherwise English.

    Other (non-Chinese) system languages map to English; the app has no third locale.
    """
    tags: list[str] = []
    tags.extend(_windows_lang_tags())
    try:
        loc = locale.getlocale()
        if loc and loc[0]:
            tags.append(loc[0])
    except Exception:
        pass
    for key in ("LANG", "LC_ALL", "LC_MESSAGES"):
        tags.append(os.environ.get(key, ""))
    if any(locale_tag_is_chinese(tag) for tag in tags):
        return "zh"
    return "en"
