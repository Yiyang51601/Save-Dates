from __future__ import annotations

from typing import Any

from save_dates.config import (
    DEFAULT_GRAPH_CLIENT_ID,
    GRAPH_AUTHORITY,
    GRAPH_SCOPES,
    MSAL_CACHE_PATH,
)


def get_client_id() -> str:
    from save_dates import db

    settings = db.get_settings()
    return str(settings.get("graph_client_id") or DEFAULT_GRAPH_CLIENT_ID).strip()


def has_cached_account() -> bool:
    if not MSAL_CACHE_PATH.exists():
        return False
    try:
        cache = _load_cache()
        app = _pca(get_client_id() or "00000000-0000-0000-0000-000000000000", cache)
        return bool(app.get_accounts())
    except Exception:
        return True


def cached_account_label() -> str:
    client_id = get_client_id()
    if not client_id or not MSAL_CACHE_PATH.exists():
        return ""
    try:
        cache = _load_cache()
        accounts = _pca(client_id, cache).get_accounts()
        if not accounts:
            return ""
        account = accounts[0]
        return str(account.get("username") or account.get("name") or "")
    except Exception:
        return ""


def acquire_token(interactive: bool = False) -> str:
    import msal

    client_id = get_client_id()
    if not client_id:
        raise RuntimeError("graph_client_id_missing")
    cache = _load_cache()
    app = _pca(client_id, cache)
    result: dict[str, Any] | None = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(list(GRAPH_SCOPES), account=accounts[0])
    if (not result or "access_token" not in result) and interactive:
        # Public native client: MSAL opens the system browser on http://localhost
        # (free port). Entra must allow that redirect. Do not add a client secret.
        result = app.acquire_token_interactive(
            list(GRAPH_SCOPES),
            prompt="select_account",
        )
    _save_cache(cache)
    if result and "access_token" in result:
        return str(result["access_token"])
    if not interactive:
        raise RuntimeError("graph_login_needed")
    error = str((result or {}).get("error") or "")
    if error in {"access_denied", "user_cancelled", "canceled"}:
        raise RuntimeError("graph_auth_cancelled")
    raise RuntimeError("graph_auth_failed")


def logout() -> None:
    client_id = get_client_id()
    if client_id and MSAL_CACHE_PATH.exists():
        try:
            cache = _load_cache()
            app = _pca(client_id, cache)
            for account in app.get_accounts():
                app.remove_account(account)
            _save_cache(cache)
        except Exception:
            pass
    if MSAL_CACHE_PATH.exists():
        MSAL_CACHE_PATH.unlink()


def _load_cache():
    import msal

    cache = msal.SerializableTokenCache()
    if MSAL_CACHE_PATH.exists():
        cache.deserialize(MSAL_CACHE_PATH.read_text(encoding="utf-8"))
    return cache


def _save_cache(cache) -> None:
    if getattr(cache, "has_state_changed", False):
        MSAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MSAL_CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")


def _pca(client_id: str, cache):
    import msal

    return msal.PublicClientApplication(
        client_id,
        authority=GRAPH_AUTHORITY,
        token_cache=cache,
    )
