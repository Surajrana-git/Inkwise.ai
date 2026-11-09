"""Regression tests for the backend bug list (S2–S8), Mon 9 Nov."""
import json

import pytest

from engine import knowledge, redact, review
from engine.schemas import Category


@pytest.fixture(scope="module")
def kb():
    return knowledge.KnowledgeBase.from_folder(use_embeddings=False)  # real Lumora kit


def test_s2_retry_budget_is_about_a_minute():
    worst = sum(4 * 2 ** i for i in range(review.MAX_TRIES - 1)) + review.MAX_TRIES * review.TIMEOUT_MS / 1000
    assert worst <= 75


def test_s3_ai_error_when_gemini_fails(kb):
    def broken(_):
        raise RuntimeError("503 UNAVAILABLE")
    r = review.review_text("Join 2 million happy users of LumoraPay!", kb=kb, llm=broken)
    assert "unavailable" in r.ai_error and r.findings  # rule findings still returned


def test_s3_ai_error_when_no_key(kb, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert "not set" in review.review_text("Hello", kb=kb).ai_error


def test_s4_full_names_masked_but_products_kept():
    masked, mapping = redact.redact_with_map(
        "Call Priya Sharma about Spend Insights in Lumora Pay. Join Lumora today.",
        allow={"Lumora", "Pay", "Spend", "Insights"})
    assert "Priya Sharma" not in masked and "[NAME_1]" in masked
    assert "Spend Insights" in masked and "Lumora Pay" in masked and "Join Lumora" in masked


def test_s5_claim_guidelines_always_sent(kb):
    seen = {}
    def fake(prompt):
        seen["p"] = prompt
        return json.dumps([{"category": "claim", "span": "fastest", "source_id": "G07",
                            "why": "x", "suggested_fix": "fast", "confidence": 0.9}])
    r = review.review_text("We are the fastest app.", kb=kb, llm=fake)
    assert "G07:" in seen["p"]
    assert [f.source_id for f in r.findings if f.span == "fastest"] == ["G07"]


def test_s6_capitalised_category_kept(kb):
    fake = lambda p: json.dumps([{"category": "Claim", "span": "best", "source_id": "G07",
                                  "why": "x", "suggested_fix": "good", "confidence": 0.8}])
    r = review.review_text("The best app.", kb=kb, llm=fake)
    assert [f.category for f in r.findings if f.span == "best"] == [Category.CLAIM]


def test_s7_one_dense_sentence_flagged(kb):
    t = ("Notwithstanding the aforementioned considerations, comprehensive multidimensional "
         "optimization necessitates institutional collaboration throughout organizational hierarchies.")
    r = review.review_text(t, kb=kb, use_ai=False)
    assert any(f.category == Category.ACCESSIBILITY for f in r.findings)
    assert not review.review_text("Send money in a few taps. It is quick.", kb=kb, use_ai=False).findings


def test_s8_reworded_expired_fact(kb):
    r = review.review_text("Over 2M people use Lumora Pay.", kb=kb, use_ai=False)
    assert "F01" in [f.source_id for f in r.findings]
    r = review.review_text("We have 2,000,000 users.", kb=kb, use_ai=False)
    assert "F01" in [f.source_id for f in r.findings]       # same claim, different number format
    r = review.review_text("Our office has 2,000,000 plants.", kb=kb, use_ai=False)
    assert "F01" not in [f.source_id for f in r.findings]   # same number, unrelated sentence
