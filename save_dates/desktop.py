from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time

from save_dates.config import DATA_DIR, HOST, ICON_PATH, LOG_PATH, PORT


def _setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    if not getattr(sys, "frozen", False):
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((HOST, PORT)) == 0


def _wait_ready(timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use():
            return True
        time.sleep(0.1)
    return False


def _icon_image():
    from PIL import Image

    if ICON_PATH.exists():
        return Image.open(ICON_PATH).convert("RGBA")
    return Image.new("RGBA", (64, 64), (194, 59, 34, 255))


def _ensure_stdio() -> None:
    # Windowed PyInstaller builds set stdout/stderr to None; uvicorn logging
    # calls sys.stdout.isatty() during startup and would crash otherwise.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _start_server() -> None:
    try:
        import uvicorn

        from save_dates.server import app

        _ensure_stdio()
        logging.info("Starting local server at http://%s:%s", HOST, PORT)
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
    except Exception:
        logging.exception("Local server thread crashed")


def _load_tray_icon(show_window, quit_app):
    import pystray

    menu = pystray.Menu(
        pystray.MenuItem("打开窗口", show_window, default=True),
        pystray.MenuItem("退出", quit_app),
    )
    icon = pystray.Icon("SaveDates", _icon_image(), "Save Dates", menu)
    icon.run_detached()
    return icon


def _ask_existing_to_show(url: str) -> bool:
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/desktop/show", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        logging.info("Existing instance did not accept a show request")
        return False


def main() -> None:
    _ensure_stdio()
    _setup_logging()
    url = f"http://{HOST}:{PORT}"
    own_server = False

    if not _port_in_use():
        thread = threading.Thread(target=_start_server, name="save-dates-http", daemon=True)
        thread.start()
        own_server = True
        if not _wait_ready():
            logging.error("Local server failed to start. See %s", LOG_PATH)
            raise SystemExit("Save Dates 启动失败，请查看 data/app.log")
    else:
        logging.info("Reusing already running instance at %s", url)
        if _ask_existing_to_show(url):
            logging.info("Asked the running instance to show its window")
            return

    try:
        import webview
    except Exception:
        logging.exception("pywebview unavailable, falling back to browser")
        import webbrowser

        webbrowser.open(url)
        if own_server:
            threading.Event().wait()
        return

    window = webview.create_window(
        "Save Dates",
        url,
        width=1080,
        height=860,
        min_size=(820, 640),
        confirm_close=False,
        hidden=False,
    )
    tray = None
    quitting = {"value": False}

    def show_window() -> None:
        try:
            window.show()
            window.restore()
        except Exception:
            logging.exception("Failed to restore window")

    from save_dates.window_control import set_show_callback

    set_show_callback(show_window)

    def quit_app() -> None:
        quitting["value"] = True
        set_show_callback(None)
        try:
            if tray:
                tray.stop()
        except Exception:
            pass
        try:
            window.destroy()
        except Exception:
            pass

    def on_closing() -> bool:
        if quitting["value"] or not own_server or tray is None:
            return True
        window.hide()
        return False

    if own_server:
        try:
            tray = _load_tray_icon(show_window, quit_app)
        except Exception:
            logging.exception("Tray icon failed; window close will exit the app")
            tray = None

    window.events.closing += on_closing
    try:
        window.events.loaded += show_window
    except Exception:
        pass
    logging.info("Opening native window")

    start_kwargs = {"gui": "edgechromium", "private_mode": False}
    if ICON_PATH.exists():
        start_kwargs["icon"] = str(ICON_PATH)
    try:
        webview.start(**start_kwargs)
    except TypeError:
        logging.exception("webview.start rejected an argument")
        start_kwargs.pop("icon", None)
        try:
            webview.start(**start_kwargs)
        except TypeError:
            start_kwargs.pop("private_mode", None)
            webview.start(**start_kwargs)
    except Exception:
        logging.exception("edgechromium GUI failed, retrying default")
        try:
            webview.start()
        except Exception:
            logging.exception("default GUI failed, falling back to browser")
            import webbrowser

            webbrowser.open(url)
            if own_server:
                threading.Event().wait()
            return
    logging.info("Native window closed")
    quit_app()


if __name__ == "__main__":
    main()
