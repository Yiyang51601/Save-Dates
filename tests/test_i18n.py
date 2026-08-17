from __future__ import annotations

import json

from save_dates.i18n import locale_tag_is_chinese


def test_locale_tag_is_chinese():
    assert locale_tag_is_chinese("zh-CN")
    assert locale_tag_is_chinese("zh_TW")
    assert locale_tag_is_chinese("zh-Hans-CN")
    assert locale_tag_is_chinese("Chinese (Simplified)_China")
    assert not locale_tag_is_chinese("en-US")
    assert not locale_tag_is_chinese("ja-JP")
    assert not locale_tag_is_chinese("fr_FR")
    assert not locale_tag_is_chinese("")


def test_unset_language_follows_system(tmp_path, monkeypatch):
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.db.system_ui_lang", lambda: "en")
    from save_dates.db import get_settings, save_settings

    settings = get_settings()
    assert settings["lang"] == "en"
    assert settings["lang_set"] is False
    saved = save_settings({"backend": "classic"})
    assert saved["lang"] == "en"
    assert saved["lang_set"] is False
    raw = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "lang" not in raw
    assert "lang_set" not in raw


def test_saved_language_overrides_system(tmp_path, monkeypatch):
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.db.system_ui_lang", lambda: "en")
    from save_dates.db import get_settings, save_settings

    save_settings({"lang": "zh"})
    monkeypatch.setattr("save_dates.db.system_ui_lang", lambda: "en")
    settings = get_settings()
    assert settings["lang"] == "zh"
    assert settings["lang_set"] is True
    saved = save_settings({"backend": "graph"})
    assert saved["lang"] == "zh"
    raw = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert raw["lang"] == "zh"
    assert raw["lang_set"] is True


def test_legacy_en_is_kept_as_user_choice(tmp_path, monkeypatch):
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.db.system_ui_lang", lambda: "zh")
    (tmp_path / "settings.json").write_text(
        json.dumps({"lang": "en", "backend": "auto"}), encoding="utf-8"
    )
    from save_dates.db import get_settings

    settings = get_settings()
    assert settings["lang"] == "en"
    assert settings["lang_set"] is True


def test_legacy_zh_without_flag_follows_system(tmp_path, monkeypatch):
    monkeypatch.setattr("save_dates.db.SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr("save_dates.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.db.system_ui_lang", lambda: "en")
    (tmp_path / "settings.json").write_text(
        json.dumps({"lang": "zh", "backend": "auto"}), encoding="utf-8"
    )
    from save_dates.db import get_settings

    settings = get_settings()
    assert settings["lang"] == "en"
    assert settings["lang_set"] is False
