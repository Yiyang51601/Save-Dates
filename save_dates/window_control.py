from __future__ import annotations

from collections.abc import Callable

_show_window: Callable[[], None] | None = None


def set_show_callback(callback: Callable[[], None] | None) -> None:
    global _show_window
    _show_window = callback


def request_show() -> bool:
    if _show_window is None:
        return False
    _show_window()
    return True
