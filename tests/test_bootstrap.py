from engine import bootstrap


def test_startup_uses_sample_kit_when_brand_kit_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("INKWISE_DB", str(tmp_path / "db.sqlite3"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(bootstrap.knowledge, "BRAND_KIT_DIR", tmp_path / "empty")
    state = bootstrap.startup()
    assert state.using_sample_kit
    assert state.kb.backend == "keyword"
    assert state.kb.search("fastest app")[0].source_id == "G02"
