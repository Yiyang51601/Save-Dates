from __future__ import annotations

import sys
from pathlib import Path


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    if _frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def app_dir() -> Path:
    if _frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = app_dir()
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "save_dates.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
TRANSLATE_CACHE_PATH = DATA_DIR / "title_zh_cache.json"
STATIC_DIR = bundle_dir() / "save_dates" / "static"
ICON_PATH = bundle_dir() / "assets" / "icon.ico"
LOG_PATH = DATA_DIR / "app.log"

HOST = "127.0.0.1"
PORT = 8765

DEFAULT_SCAN_DAYS = 14
DEFAULT_MAX_EMAILS = 80
BODY_CHAR_LIMIT = 8000
PAST_GRACE_HOURS = 12
MAX_FUTURE_DAYS = 400
PENDING_LIST_LIMIT = 80
SEARCH_SCAN_DAYS = 14
SEARCH_MAX_EMAILS = 40
SEARCH_RESULT_LIMIT = 12
SEARCH_QUERY_MAX = 80

WATCH_IDLE_SEC = 0.08
WATCH_RETRY_SEC = 10
WATCH_RECENT_IDS = 64
GRAPH_WATCH_SEC = 20
MSAL_CACHE_PATH = DATA_DIR / "msal_cache.bin"
GRAPH_STATE_PATH = DATA_DIR / "graph_state.json"
GRAPH_ID_PREFIX = "graph:"
GRAPH_SCOPES = ("User.Read", "Mail.Read", "Mail.ReadWrite", "Calendars.ReadWrite")
GRAPH_AUTHORITY = "https://login.microsoftonline.com/common"
# Public native client. MSAL interactive login binds http://localhost on a free port.
GRAPH_REDIRECT_URI = "http://localhost"
# Developer-owned public client. Friends never register Entra apps or type an App ID.
DEFAULT_GRAPH_CLIENT_ID = "65f4dd53-e782-46a4-a0b1-8ccd331dd6ff"

CATEGORY_NAME = "Save Dates"
REMINDER_MINUTES_TIMED = 30
REMINDER_MINUTES_ALL_DAY = 18 * 60
