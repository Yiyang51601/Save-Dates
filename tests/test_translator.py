from save_dates.translator import cache_get, cache_put, translate_to_zh


def test_translator_returns_chinese_from_helper(monkeypatch, tmp_path):
    monkeypatch.setattr("save_dates.translator.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.translator.TRANSLATE_CACHE_PATH", tmp_path / "title_zh_cache.json")
    monkeypatch.setattr("save_dates.translator._cache", None)
    monkeypatch.setattr(
        "save_dates.translator._fetch_zh",
        lambda text: "匹兹堡最新的名人堂成员" if "Pitt" in text else "智能体、MCP 与技能",
    )
    out = translate_to_zh("Pitt's newest hall-of-famer", network=True)
    assert any("\u4e00" <= ch <= "\u9fff" for ch in out)
    assert "匹兹堡" in out
    assert cache_get("Pitt's newest hall-of-famer") == out


def test_translator_falls_back_when_offline(monkeypatch, tmp_path):
    monkeypatch.setattr("save_dates.translator.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.translator.TRANSLATE_CACHE_PATH", tmp_path / "title_zh_cache.json")
    monkeypatch.setattr("save_dates.translator._cache", None)

    def boom(_text):
        raise RuntimeError("blocked")

    monkeypatch.setattr("save_dates.translator._fetch_zh", boom)
    assert translate_to_zh("Agents, MCP, skills", network=True) == ""


def test_attach_uses_cached_translation_for_english_subject(monkeypatch, tmp_path):
    monkeypatch.setattr("save_dates.translator.DATA_DIR", tmp_path)
    monkeypatch.setattr("save_dates.translator.TRANSLATE_CACHE_PATH", tmp_path / "title_zh_cache.json")
    monkeypatch.setattr("save_dates.translator._cache", None)
    monkeypatch.setattr("save_dates.display_title._want_zh_display", lambda: True)
    cache_put("Pitt's newest hall-of-famer", "匹兹堡最新的名人堂成员")
    from save_dates.display_title import attach_display_titles

    row = attach_display_titles(
        {
            "title": "Pitt's newest hall-of-famer",
            "subject": "Pitt's newest hall-of-famer",
            "snippet": "Join us Friday.",
            "kind": "event",
        }
    )
    assert "匹兹堡" in row["title_zh"]
    assert row["title"] == "Pitt's newest hall-of-famer"
