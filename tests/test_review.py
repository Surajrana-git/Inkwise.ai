import json
from datetime import date

from engine import review
from engine.knowledge import KnowledgeBase
from engine.schemas import Category, Fact, Guideline, Term

KB = KnowledgeBase(
    [Guideline(id="G01", title="Friendly, plain tone", rule="Avoid jargon and hype.", category=Category.TONE),
     Guideline(id="G07", title="Substantiate product claims", rule="Back claims with an approved fact.",
               category=Category.CLAIM)],
    [Fact(id="F01", statement="Lumora Pay has 2 million registered users.", source="x", owner="Comms",
          expires_on=date(2026, 9, 30))],
    [Term(id="T01", approved="Lumora Pay", banned_variants=["LumoraPay"])])


def fake_llm(items):
    seen = {}

    def llm(prompt):
        seen["prompt"] = prompt
        return json.dumps(items)
    llm.seen = seen
    return llm


def test_rules_and_ai_merge_with_sequential_ids_and_citations():
    text = "LumoraPay is the fastest payments app in India. Our revolutionary hype and jargon tool is here."
    llm = fake_llm([
        {"category": "claim", "span": "the fastest payments app in India", "source_id": "G99",
         "why": "No approved fact supports this.", "suggested_fix": "a fast way to pay", "confidence": 0.95},
        {"category": "tone", "span": "revolutionary", "source_id": "G01",
         "why": "Hype word.", "suggested_fix": "new", "confidence": 0.8},
        {"category": "tone", "span": "words not in the text", "source_id": "G01", "why": "x",
         "suggested_fix": "y", "confidence": 0.9}])
    r = review.review_text(text, kb=KB, llm=llm)
    assert [f.id for f in r.findings] == ["f-001", "f-002", "f-003"]
    by = {f.span: f for f in r.findings}
    assert by["LumoraPay"].checked_by.value == "rule" and by["LumoraPay"].source_id == "T01"
    claim = by["the fastest payments app in India"]
    assert claim.source_id == "UNVERIFIED" and claim.confidence <= 0.6 and claim.source_text == ""
    assert by["revolutionary"].source_id == "G01" and by["revolutionary"].source_text
    assert len(r.findings) == 3 and r.model == "injected-llm"


def test_rule_wins_when_ai_flags_same_words():
    llm = fake_llm([{"category": "terminology", "span": "LumoraPay", "source_id": "T01", "why": "x",
                     "suggested_fix": "y", "confidence": 0.5}])
    r = review.review_text("Try LumoraPay now.", kb=KB, llm=llm)
    assert len(r.findings) == 1 and r.findings[0].checked_by.value == "rule"


def test_personal_data_never_reaches_the_model_and_spans_are_restored():
    text = "Email ria@lumora.com about our revolutionary offer."
    llm = fake_llm([{"category": "tone", "span": "[EMAIL_1] about our revolutionary offer", "source_id": "G01",
                     "why": "Hype.", "suggested_fix": "Email [EMAIL_1] about our new offer.", "confidence": 0.7}])
    r = review.review_text(text, kb=KB, llm=llm)
    assert "ria@lumora.com" not in llm.seen["prompt"]
    assert r.redactions == 1 and "ria@lumora.com" not in r.text
    assert r.findings[0].span == "ria@lumora.com about our revolutionary offer"
    assert "ria@lumora.com" in r.findings[0].suggested_fix


def test_gemini_failure_returns_rule_findings_only():
    def boom(prompt):
        raise RuntimeError("quota")
    r = review.review_text("Try LumoraPay now.", kb=KB, llm=boom)
    assert len(r.findings) == 1 and r.model == ""


def test_no_api_key_means_rules_only(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = review.review_text("Try LumoraPay now.", kb=KB)
    assert len(r.findings) == 1 and r.model == ""


def test_bad_json_and_markdown_fences_are_handled():
    r = review.review_text("Try LumoraPay now.", kb=KB, llm=lambda p: "not json")
    assert len(r.findings) == 1
    fenced = "```json\n" + json.dumps([{"category": "tone", "span": "No hype", "source_id": "G01", "why": "w",
                                         "suggested_fix": "f", "confidence": 2}]) + "\n```"
    r = review.review_text("Try LumoraPay now. No hype.", kb=KB, llm=lambda p: fenced)
    assert any(f.span == "No hype" and f.source_id == "G01" and f.confidence == 1.0 for f in r.findings)


def test_429_is_retried(monkeypatch):
    monkeypatch.setattr(review, "_sleep", lambda s: None)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    calls = {"n": 0}

    class Boom(Exception):
        pass

    class Client:
        def __init__(self, api_key, **kw): self.models = self
        def generate_content(self, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                raise Boom("429 RESOURCE_EXHAUSTED")
            return type("R", (), {"text": "[]"})()

    import google.genai as genai
    monkeypatch.setattr(genai, "Client", Client)
    assert review._gemini_generate("hi") == "[]" and calls["n"] == 3
