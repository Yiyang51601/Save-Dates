"""Write confirmed Save Dates events into a local Obsidian vault."""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from save_dates.display_title import has_chinese
from save_dates.extract import calendar_tz, ensure_aware

_LOG = logging.getLogger(__name__)
_UNSAFE = re.compile(r'[\\/:*?"<>|]')
_WS = re.compile(r"\s+")
_LATIN = re.compile(r"[A-Za-z]{3,}")
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic", ".tif", ".tiff"}

VAULT_FOLDERS = ("Inbox", "Daily", "Events", "课程", "GSR", "生活", "_templates")
DEFAULT_VAULT_D = Path(r"D:\Notes\Pitt")
DEFAULT_VAULT_F = Path(r"F:\Notes\Pitt")


def default_vault_path() -> Path:
    try:
        if Path("D:/").exists():
            return DEFAULT_VAULT_D
    except OSError:
        pass
    return DEFAULT_VAULT_F


def vault_seed_dir() -> Path:
    from save_dates.config import bundle_dir

    return bundle_dir() / "vault_seed"


def sanitize_filename(name: str, max_len: int = 80) -> str:
    text = _UNSAFE.sub(" ", str(name or ""))
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = _WS.sub(" ", text).strip(" .")
    if not text:
        text = "untitled"
    if len(text) > max_len:
        text = text[:max_len].rstrip(" .")
    return text or "untitled"


def event_filename(start: datetime, title: str) -> str:
    wall = _wall(start)
    return f"{wall.strftime('%Y-%m-%d')} {sanitize_filename(title)}.md"


def _wall(value: datetime) -> datetime:
    tz = calendar_tz()
    return ensure_aware(value, tz).astimezone(tz)


def parse_item_start(item: dict[str, Any]) -> datetime:
    raw = str(item.get("start_at") or "").strip()
    if not raw:
        return datetime.now(calendar_tz())
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return _wall(dt)


def format_wall_clock(start: datetime, all_day: bool, end: datetime | None = None) -> str:
    wall = _wall(start)
    date_part = wall.strftime("%Y-%m-%d")
    if all_day:
        return f"{date_part} 全天"
    stamp = wall.strftime("%H:%M")
    if end is not None:
        end_wall = _wall(end)
        if end_wall.date() == wall.date() and end_wall.strftime("%H:%M") != stamp:
            stamp = f"{stamp}–{end_wall.strftime('%H:%M')}"
    return f"{date_part} {stamp}"


def time_label(start: datetime, all_day: bool) -> str:
    if all_day:
        return "全天"
    return _wall(start).strftime("%H:%M")


def daily_bullet_line(title: str, start: datetime, all_day: bool, location: str = "") -> str:
    loc = str(location or "").strip()
    suffix = f" @ {loc}" if loc else ""
    return f"- {time_label(start, all_day)} {title.strip()}{suffix}"


def daily_contains(text: str, title: str, start: datetime, all_day: bool) -> bool:
    wanted_time = time_label(start, all_day)
    wanted_title = str(title or "").strip()
    if not wanted_title:
        return False
    prefix = f"{wanted_time} {wanted_title}"
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            line = line[2:].strip()
        if line == prefix or line.startswith(prefix + " @") or line.startswith(prefix + "　"):
            return True
    return False


def event_note_body(item: dict[str, Any], *, written_title: str | None = None) -> str:
    title = (written_title if written_title is not None else str(item.get("title") or "")).strip()
    start = parse_item_start(item)
    end_raw = str(item.get("end_at") or "").strip()
    end = None
    if end_raw:
        try:
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
        except ValueError:
            end = None
    all_day = bool(item.get("all_day"))
    kind = str(item.get("kind") or "event")
    kind_label = "待办 / task" if kind == "task" else "日程 / event"
    location = str(item.get("location") or "").strip()
    notes = str(item.get("notes") or "").strip()
    keywords = str(item.get("matched_text") or "").strip()
    mailbox = str(item.get("mailbox") or "").strip()
    subject = str(item.get("subject") or "").strip()
    original = str(item.get("title") or "").strip()
    original_en = ""
    if original and original != title and _LATIN.search(original):
        original_en = original
    elif original and original != title and has_chinese(title):
        original_en = original

    lines = [
        f"# {title}",
        "",
        f"- 日期时间: {format_wall_clock(start, all_day, end)}（America/New_York）",
        f"- 地点: {location}" if location else "- 地点:",
        f"- 备注: {notes}" if notes else "- 备注:",
        f"- 关键词: {keywords}" if keywords else "- 关键词:",
        f"- 类型: {kind_label}",
        f"- 来源邮箱: {mailbox}" if mailbox else "- 来源邮箱:",
        f"- 原邮件主题: {subject}" if subject else "- 原邮件主题:",
    ]
    if original_en:
        lines.append(f"- 英文原标题: {original_en}")
    lines.append("- 来源: Save Dates")
    lines.append("")
    return "\n".join(lines)


def append_daily_bullet(daily_path: Path, start: datetime, bullet: str, title: str, all_day: bool) -> bool:
    """Append one bullet if this title+time is not already present. Returns True if written."""
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if daily_path.exists():
        existing = daily_path.read_text(encoding="utf-8")
        if daily_contains(existing, title, start, all_day):
            return False
    heading = f"# {_wall(start).strftime('%Y-%m-%d')}"
    parts: list[str] = []
    if not existing.strip():
        parts.append(heading)
        parts.append("")
        parts.append(bullet)
        parts.append("")
        daily_path.write_text("\n".join(parts), encoding="utf-8")
        return True
    text = existing.rstrip() + "\n" + bullet + "\n"
    daily_path.write_text(text, encoding="utf-8")
    return True


def write_candidate(
    item: dict[str, Any],
    vault: Path,
    written_title: str | None = None,
) -> dict[str, Any]:
    vault = Path(vault)
    ensure_vault(vault)
    kind = str(item.get("kind") or "event")
    written_title = (written_title or str(item.get("title") or "")).strip()
    start = parse_item_start(item)
    all_day = bool(item.get("all_day"))
    location = str(item.get("location") or "").strip()
    events_dir = vault / "Events"
    events_dir.mkdir(parents=True, exist_ok=True)
    note_name = event_filename(start, written_title)
    note_path = events_dir / note_name
    note_path.write_text(event_note_body(item, written_title=written_title), encoding="utf-8")
    daily_path = vault / "Daily" / f"{_wall(start).strftime('%Y-%m-%d')}.md"
    bullet = daily_bullet_line(written_title, start, all_day, location)
    appended = append_daily_bullet(daily_path, start, bullet, written_title, all_day)
    return {
        "ok": True,
        "kind": kind,
        "event_note": str(note_path),
        "daily_note": str(daily_path),
        "daily_appended": appended,
    }


def should_write(item: dict[str, Any], settings: dict[str, Any] | None = None) -> bool:
    settings = settings if settings is not None else _settings()
    enabled = settings.get("obsidian_write")
    if enabled is None:
        enabled = settings.get("obsidian_export_on_join")
    if not enabled:
        return False
    if (item.get("kind") or "event") == "promo":
        return False
    email_id = str(item.get("email_id") or "")
    if email_id.startswith("demo-"):
        return False
    vault = str(settings.get("obsidian_vault") or settings.get("obsidian_vault_path") or "").strip()
    return bool(vault)


def write_from_settings(item: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from save_dates.display_title import calendar_write_title

        settings = _settings()
        if not should_write(item, settings):
            return None
        vault = Path(
            str(settings.get("obsidian_vault") or settings.get("obsidian_vault_path") or default_vault_path())
        )
        title = calendar_write_title(item) or str(item.get("title") or "").strip()
        return write_candidate(item, vault, written_title=title)
    except Exception:
        _LOG.exception("Obsidian write failed")
        return None


def ensure_vault(vault: Path) -> Path:
    vault = Path(vault)
    vault.mkdir(parents=True, exist_ok=True)
    for name in VAULT_FOLDERS:
        (vault / name).mkdir(parents=True, exist_ok=True)
    seed = vault_seed_dir()
    if seed.is_dir():
        _copy_seed(seed, vault)
    return vault


def _copy_seed(seed: Path, vault: Path) -> None:
    for src in seed.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(seed)
        dest = vault / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            try:
                shutil.copy2(src, dest)
            except OSError:
                _LOG.exception("Could not copy vault seed %s", rel)


def process_inbox_photos(vault: Path) -> dict[str, Any]:
    """Create a markdown note with an embed for each new Inbox image. No OCR."""
    inbox = Path(vault) / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    existing_md = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in inbox.glob("*.md")
    )
    created: list[str] = []
    skipped: list[str] = []
    images = [
        path
        for path in inbox.iterdir()
        if path.is_file() and path.suffix.lower() in _IMAGE_EXT
    ]
    images.sort(key=lambda p: p.stat().st_mtime)
    counts: dict[str, int] = {}
    for image in images:
        embed = f"![[{image.name}]]"
        if embed in existing_md:
            skipped.append(image.name)
            continue
        stamp = datetime.fromtimestamp(image.stat().st_mtime, tz=calendar_tz()).strftime("%Y-%m-%d")
        counts[stamp] = counts.get(stamp, 0) + 1
        n = counts[stamp]
        note_name = f"{stamp}-photo.md" if n == 1 else f"{stamp}-photo-{n}.md"
        note_path = inbox / note_name
        while note_path.exists():
            n += 1
            note_path = inbox / f"{stamp}-photo-{n}.md"
        body = (
            f"# 照片 {image.stem}\n\n"
            f"{embed}\n\n"
            f"- 日期: \n"
            f"- 地点: \n"
            f"- 要做: \n"
        )
        note_path.write_text(body, encoding="utf-8")
        existing_md += "\n" + body
        created.append(note_path.name)
    return {"created": created, "skipped": skipped, "inbox": str(inbox)}


def open_vault_folder(vault: Path) -> bool:
    path = Path(vault)
    path.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            os.system(f'xdg-open "{path}"')
        return True
    except OSError:
        _LOG.exception("Could not open vault folder %s", path)
        return False


def _settings() -> dict[str, Any]:
    from save_dates.db import get_settings

    return get_settings()
