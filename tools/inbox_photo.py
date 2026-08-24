"""Create an Obsidian note for each new image in the vault Inbox. No OCR."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from save_dates.obsidian import default_vault_path, ensure_vault, process_inbox_photos  # noqa: E402


def main() -> int:
    vault = default_vault_path()
    try:
        from save_dates.db import get_settings

        settings = get_settings()
        saved = str(settings.get("obsidian_vault") or settings.get("obsidian_vault_path") or "").strip()
        if saved:
            vault = Path(saved)
    except Exception:
        pass
    ensure_vault(vault)
    result = process_inbox_photos(vault)
    created = result.get("created") or []
    skipped = result.get("skipped") or []
    print(f"Vault: {vault}")
    print(f"Inbox: {result.get('inbox')}")
    if created:
        print("Created:")
        for name in created:
            print(f"  {name}")
    else:
        print("No new photo notes.")
    if skipped:
        print("Already had notes:")
        for name in skipped:
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
