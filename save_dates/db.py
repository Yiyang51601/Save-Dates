from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from save_dates.config import DATA_DIR, DB_PATH, SETTINGS_PATH
from save_dates.display_title import attach_display_titles
from save_dates.i18n import system_ui_lang
from save_dates.priority import attach_priority, sort_pending

_lock = threading.Lock()
_session_backend: str | None = None


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT NOT NULL,
                    internet_id TEXT,
                    subject TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    all_day INTEGER NOT NULL DEFAULT 0,
                    snippet TEXT NOT NULL DEFAULT '',
                    matched_text TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'pending',
                    calendar_entry_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
                CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email_id);

                CREATE TABLE IF NOT EXISTS processed_emails (
                    email_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS seen_emails (
                    email_id TEXT PRIMARY KEY,
                    seen_at TEXT NOT NULL
                );
                """
            )
            _relax_unique(conn)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
            if "store_id" not in cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN store_id TEXT")
            if "mail_url" not in cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN mail_url TEXT")
            if "fuzzy" not in cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN fuzzy INTEGER NOT NULL DEFAULT 0")
            if "kind" not in cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN kind TEXT NOT NULL DEFAULT 'event'")
            if "task_type" not in cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN task_type TEXT NOT NULL DEFAULT ''")
            if "mailbox" not in cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN mailbox TEXT NOT NULL DEFAULT ''")
            conn.execute("DROP INDEX IF EXISTS idx_pending_unique")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_unique
                ON candidates(email_id, start_at, title, kind, task_type)
                WHERE status = 'pending'
                """
            )
            conn.commit()
        finally:
            conn.close()


def _relax_unique(conn: sqlite3.Connection) -> None:
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='candidates'"
    ).fetchone()
    if not sql or "UNIQUE(email_id, start_at, title)" not in (sql[0] or ""):
        return
    conn.executescript(
        """
        DROP TABLE IF EXISTS candidates_migrated;
        CREATE TABLE candidates_migrated (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT NOT NULL,
            internet_id TEXT,
            subject TEXT NOT NULL,
            sender TEXT NOT NULL,
            received_at TEXT NOT NULL,
            title TEXT NOT NULL,
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            all_day INTEGER NOT NULL DEFAULT 0,
            snippet TEXT NOT NULL DEFAULT '',
            matched_text TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0.5,
            status TEXT NOT NULL DEFAULT 'pending',
            calendar_entry_id TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO candidates_migrated (
            id, email_id, internet_id, subject, sender, received_at, title,
            start_at, end_at, all_day, snippet, matched_text, confidence,
            status, calendar_entry_id, created_at
        )
        SELECT id, email_id, internet_id, subject, sender, received_at, title,
            start_at, end_at, all_day, snippet, matched_text, confidence,
            status, calendar_entry_id, created_at
        FROM candidates;
        DROP TABLE candidates;
        ALTER TABLE candidates_migrated RENAME TO candidates;
        CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
        CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_unique
            ON candidates(email_id, start_at, title, kind, task_type)
            WHERE status = 'pending';
        """
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["all_day"] = bool(item["all_day"])
    item["fuzzy"] = bool(item.get("fuzzy"))
    item["kind"] = item.get("kind") or "event"
    item["task_type"] = item.get("task_type") or ""
    item["mailbox"] = item.get("mailbox") or ""
    email_id = str(item.get("email_id") or "")
    mail_url = str(item.get("mail_url") or "")
    item["can_open_mail"] = (bool(email_id) and not email_id.startswith("demo-")) or bool(mail_url)
    return attach_priority(attach_display_titles(item))


def list_searchable(limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 400))
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM candidates
                WHERE status IN ('pending', 'accepted')
                ORDER BY received_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def find_candidate_match(
    email_id: str,
    title: str,
    start_at: str,
    kind: str = "event",
    task_type: str = "",
) -> dict[str, Any] | None:
    if not email_id:
        return None
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM candidates
                WHERE email_id = ? AND title = ? AND start_at = ?
                  AND kind = ? AND IFNULL(task_type, '') = ?
                ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'accepted' THEN 1 ELSE 2 END, id DESC
                LIMIT 1
                """,
                (email_id, title, start_at, kind or "event", task_type or ""),
            ).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()


def list_candidates(status: str | None = "pending", limit: int = 80) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    fetch_limit = 400 if status == "pending" else limit
    with _lock:
        conn = _connect()
        try:
            if status == "pending":
                rows = conn.execute(
                    """
                    SELECT * FROM candidates
                    WHERE status = ?
                    ORDER BY start_at ASC, id ASC
                    LIMIT ?
                    """,
                    (status, fetch_limit),
                ).fetchall()
                items = [_row_to_dict(r) for r in rows]
                return sort_pending(items)[:limit]
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM candidates
                    WHERE status = ?
                    ORDER BY start_at ASC, id ASC
                    LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM candidates
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def get_candidate(candidate_id: int) -> dict[str, Any] | None:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()


def insert_candidates(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    inserted = 0
    with _lock:
        conn = _connect()
        try:
            for item in items:
                try:
                    conn.execute(
                        """
                        INSERT INTO candidates (
                            email_id, internet_id, store_id, mail_url, subject, sender, received_at,
                            title, start_at, end_at, all_day, snippet, matched_text,
                            confidence, fuzzy, kind, task_type, mailbox, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                        """,
                        (
                            item["email_id"],
                            item.get("internet_id"),
                            item.get("store_id") or "",
                            item.get("mail_url") or "",
                            item["subject"],
                            item["sender"],
                            item["received_at"],
                            item["title"],
                            item["start_at"],
                            item["end_at"],
                            1 if item.get("all_day") else 0,
                            item.get("snippet", ""),
                            item.get("matched_text", ""),
                            float(item.get("confidence", 0.5)),
                            1 if item.get("fuzzy") else 0,
                            item.get("kind") or "event",
                            item.get("task_type") or "",
                            item.get("mailbox") or "",
                            now,
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    continue
            conn.commit()
        finally:
            conn.close()
    return inserted


def update_candidate(candidate_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"title", "start_at", "end_at", "all_day"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if "all_day" in updates:
        updates["all_day"] = 1 if updates["all_day"] else 0
    if not updates:
        return get_candidate(candidate_id)
    assignments = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [candidate_id]
    with _lock:
        conn = _connect()
        try:
            conn.execute(f"UPDATE candidates SET {assignments} WHERE id = ?", values)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("conflict_duplicate") from exc
        finally:
            conn.close()
    return get_candidate(candidate_id)


def clear_pending_prefix(prefix: str) -> int:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM candidates WHERE status = 'pending' AND email_id LIKE ?",
                (f"{prefix}%",),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        finally:
            conn.close()


def set_status(
    candidate_id: int,
    status: str,
    calendar_entry_id: str | None = None,
) -> dict[str, Any] | None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE candidates
                SET status = ?, calendar_entry_id = COALESCE(?, calendar_entry_id)
                WHERE id = ?
                """,
                (status, calendar_entry_id, candidate_id),
            )
            row = conn.execute(
                "SELECT email_id FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            if row:
                conn.execute(
                    """
                    INSERT INTO processed_emails(email_id, processed_at)
                    VALUES (?, ?)
                    ON CONFLICT(email_id) DO UPDATE SET processed_at = excluded.processed_at
                    """,
                    (row["email_id"], datetime.now().isoformat(timespec="seconds")),
                )
            conn.commit()
        finally:
            conn.close()
    return get_candidate(candidate_id)


def restore_pending(candidate_id: int) -> dict[str, Any] | None:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT email_id, status FROM candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                """
                UPDATE candidates
                SET status = 'pending', calendar_entry_id = NULL
                WHERE id = ?
                """,
                (candidate_id,),
            )
            remaining = conn.execute(
                """
                SELECT 1 FROM candidates
                WHERE email_id = ? AND status IN ('accepted', 'rejected')
                LIMIT 1
                """,
                (row["email_id"],),
            ).fetchone()
            if remaining is None:
                conn.execute("DELETE FROM processed_emails WHERE email_id = ?", (row["email_id"],))
            conn.commit()
        finally:
            conn.close()
    return get_candidate(candidate_id)


def mark_seen(email_id: str) -> None:
    if not email_id:
        return
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO seen_emails(email_id, seen_at)
                VALUES (?, ?)
                ON CONFLICT(email_id) DO UPDATE SET seen_at = excluded.seen_at
                """,
                (email_id, datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()
        finally:
            conn.close()


def is_handled(email_id: str) -> bool:
    if not email_id:
        return True
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT 1 FROM seen_emails WHERE email_id = ?
                UNION ALL
                SELECT 1 FROM processed_emails WHERE email_id = ?
                LIMIT 1
                """,
                (email_id, email_id),
            ).fetchone()
            return row is not None
        finally:
            conn.close()


def counts() -> dict[str, int]:
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM candidates GROUP BY status"
            ).fetchall()
            result = {"pending": 0, "accepted": 0, "rejected": 0}
            for row in rows:
                result[row["status"]] = row["n"]
            return result
        finally:
            conn.close()


def dump_debug(path: Path | None = None) -> Path:
    path = path or (DATA_DIR / "debug.json")
    path.write_text(json.dumps(list_candidates(None), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _read_settings_file() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _lang_user_set(data: dict[str, Any]) -> bool:
    saved = data.get("lang")
    if data.get("lang_set") is True and saved in {"zh", "en"}:
        return True
    # Legacy files never defaulted to EN, so an explicit EN choice must be kept.
    return saved == "en"


def set_session_backend(backend: str | None) -> None:
    """Use this Outlook backend until the process exits; do not write settings.json."""
    global _session_backend
    if backend in {"auto", "classic", "graph"}:
        _session_backend = backend
    else:
        _session_backend = None


def clear_session_backend() -> None:
    global _session_backend
    _session_backend = None


def get_settings() -> dict[str, Any]:
    data = _read_settings_file()
    backend = data.get("backend", "auto")
    if backend not in {"auto", "classic", "graph"}:
        backend = "auto"
    if _session_backend in {"auto", "classic", "graph"}:
        backend = _session_backend
    client_id = str(data.get("graph_client_id") or "").strip()
    if _lang_user_set(data):
        lang = "en" if data.get("lang") == "en" else "zh"
        lang_set = True
    else:
        lang = system_ui_lang()
        lang_set = False
    return {
        "lang": lang,
        "lang_set": lang_set,
        "backend": backend,
        "graph_client_id": client_id,
    }


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    data = _read_settings_file()
    out: dict[str, Any] = {}
    backend = data.get("backend", "auto")
    if "backend" in patch and patch["backend"] in {"auto", "classic", "graph"}:
        backend = patch["backend"]
        clear_session_backend()
    if backend not in {"auto", "classic", "graph"}:
        backend = "auto"
    out["backend"] = backend
    client_id = str(data.get("graph_client_id") or "").strip()
    if "graph_client_id" in patch and patch["graph_client_id"] is not None:
        client_id = str(patch["graph_client_id"]).strip()
    if client_id:
        out["graph_client_id"] = client_id
    if "lang" in patch and patch["lang"] in {"zh", "en"}:
        out["lang"] = patch["lang"]
        out["lang_set"] = True
    elif _lang_user_set(data):
        out["lang"] = "en" if data.get("lang") == "en" else "zh"
        out["lang_set"] = True
    SETTINGS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return get_settings()
