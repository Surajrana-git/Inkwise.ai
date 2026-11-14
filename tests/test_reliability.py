"""Reliability checklist from the Round 3 plan, as tests: bad input, AI failures, repeats."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from engine import knowledge, review, workflow as wf  # noqa: E402


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("INKWISE_DB", str(tmp_path / "rel.sqlite3"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import services
    wf.init_db()
    services._started = False
    services._cache.clear()
    knowledge.build_index(knowledge.BRAND_KIT_DIR, use_embeddings=False)


def kb():
    return knowledge.get_kb()


def test_gemini_outage_returns_rule_findings_and_a_message():
    def down(_):
        raise RuntimeError("503 UNAVAILABLE")
    r = review.review_text("Open LumoraPay now.", kb=kb(), llm=down)
    assert [f.source_id for f in r.findings] == ["T01"]
    assert "rule checks only" in r.ai_error


def test_malformed_ai_output_never_crashes():
    for raw in ["not json {", "", "null", '{"findings": "x"}', "[1, 2, 3]"]:
        r = review.review_text("Open LumoraPay now.", kb=kb(), llm=lambda _p, raw=raw: raw)
        assert any(f.source_id == "T01" for f in r.findings)


def test_ai_cannot_invent_quotes_or_sources():
    raw = ('[{"category":"claim","span":"words not in the text","source_id":"G07","why":"x","suggested_fix":"y","confidence":0.9},'
           '{"category":"claim","span":"We are fast","source_id":"G99","why":"x","suggested_fix":"y","confidence":0.95}]')
    r = review.review_text("We are fast.", kb=kb(), llm=lambda _p: raw)
    assert [(f.span, f.source_id) for f in r.findings] == [("We are fast", "UNVERIFIED")]
    assert r.findings[0].confidence <= review.UNVERIFIED_MAX_CONFIDENCE


@pytest.mark.parametrize("text", ["🙂🙂🙂", "<script>alert(1)</script> LumoraPay", "नमस्ते LumoraPay ₹2 lakh", "a\r\nb"])
def test_unusual_text_is_handled(text):
    import services
    out = services.review_text_full(text)
    assert isinstance(out["findings"], list)


def test_highlight_escapes_html():
    import theme
    text = "<b>LumoraPay</b>"
    html_out = theme.highlight_html(text, [{"start": 3, "end": 12, "category": "terminology"}])
    assert "<b>" not in html_out.replace("<b>", "", 0) or "&lt;b&gt;" in html_out


@pytest.mark.parametrize("data,msg", [(b"", "Choose an image"), (b"hello", "not a PNG or JPEG"),
                                      (b"\x89PNG" + b"0" * (6 * 1024 * 1024), "limit is 5 MB")])
def test_bad_image_uploads_get_a_message(data, msg):
    import services
    with pytest.raises(services.InputError, match=msg):
        services.review_image(data, "x.png")


def test_deciding_twice_or_after_someone_else():
    sid = wf.submit_for_approval("Post", "text", [], "asha")
    wf.decide_submission(sid, "approved", "ok", "meera", "manager")
    wf.decide_submission(sid, "approved", "ok", "meera", "manager")          # same click again: no error
    with pytest.raises(wf.WorkflowError, match="Only items in review"):
        wf.decide_submission(sid, "rejected", "", "ravi", "admin")            # already decided by meera
    with pytest.raises(wf.WorkflowError, match="not found"):
        wf.decide_submission("99999", "approved", "", "meera", "manager")
    events = [h["action"] for h in wf.history(int(sid)) if h["kind"] == "event"]
    assert events.count("approved") == 1


def test_review_cache_serves_repeat_text():
    import services
    calls = []

    def fake(text, **kw):
        calls.append(text)
        return review.ReviewResult(text=text, findings=[], model="fake")
    services.ensure_started()
    orig = review.review_text
    review.review_text = fake
    try:
        services.review_text_full("Hello there.")
        second = services.review_text_full("Hello there.")
    finally:
        review.review_text = orig
    assert len(calls) == 1 and second["cached"] is True
