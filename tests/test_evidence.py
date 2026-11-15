"""Round 3: evidence is verified by code, not by the model; occurrences list every match."""
import json
from datetime import date

from engine import review
from engine.knowledge import KnowledgeBase
from engine.schemas import Category, Fact, Guideline, Term

KB = KnowledgeBase(
    [Guideline(id="G01", title="Friendly, plain tone", rule="Avoid jargon and hype.", category=Category.TONE),
     Guideline(id="G07", title="Substantiate product claims",
               rule="Back every claim with an approved fact from the brand kit.", category=Category.CLAIM),
     Guideline(id="G08", title="Avoid guarantees",
               rule="Never promise a guaranteed outcome. Back every claim with caution.", category=Category.CLAIM)],
    [Fact(id="F01", statement="Lumora Pay has 2 million registered users.", source="x", owner="Comms",
          expires_on=date(2026, 9, 30))],
    [Term(id="T01", approved="Lumora Pay", banned_variants=["LumoraPay"])])

# the extra words let keyword retrieval find G01, G07 and G08 (sources must be retrieved to be citable)
TEXT = ("Our revolutionary jargon and hype tool is the fastest app in India. "
        "Every claim is a fact and a guaranteed outcome.")


def run(items, text=TEXT):
    return review.review_text(text, kb=KB, llm=lambda p: json.dumps(items))


def item(**kw):
    base = {"category": "tone", "span": "revolutionary", "source_id": "G01", "evidence": "Avoid jargon and hype",
            "why": "Hype.", "suggested_fix": "new", "confidence": 0.9}
    base.update(kw)
    return base


def only(result, span):
    return next(f for f in result.findings if f.span == span)


def test_quote_found_in_cited_source_is_verified_with_exact_slice():
    f = only(run([item(evidence="avoid   JARGON and hype")]), "revolutionary")
    assert f.evidence_verified and f.source_id == "G01"
    assert f.evidence == "Avoid jargon and hype"          # exact slice of the source, original case
    assert f.evidence in f.source_text and f.confidence == 0.9


def test_quote_not_in_any_source_downgrades_to_unverified():
    f = only(run([item(evidence="Always sound exciting")]), "revolutionary")
    assert f.source_id == "UNVERIFIED" and not f.evidence_verified
    assert f.evidence == "" and f.source_text == "" and f.confidence <= 0.6


def test_missing_or_too_short_quote_downgrades():
    for ev in ("", "hype", None):
        f = only(run([item(evidence=ev)]), "revolutionary")
        assert f.source_id == "UNVERIFIED" and not f.evidence_verified


def test_wrong_source_is_corrected_when_quote_belongs_to_exactly_one_other_source():
    f = only(run([item(source_id="G01", category="tone", span="the fastest app in India",
                       evidence="Back every claim with an approved fact")]), "the fastest app in India")
    assert f.source_id == "G07" and f.evidence_verified
    assert f.category == Category.CLAIM                    # category follows the corrected source


def test_quote_that_fits_two_sources_is_not_guessed():
    f = only(run([item(span="the fastest app in India", evidence="Back every claim with")]),
             "the fastest app in India")
    assert f.source_id == "UNVERIFIED" and not f.evidence_verified


def test_recite_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(review, "RECITE_FROM_EVIDENCE", False)
    f = only(run([item(span="the fastest app in India", evidence="Back every claim with an approved fact")]),
             "the fastest app in India")
    assert f.source_id == "UNVERIFIED"


def test_banned_term_used_three_times_gives_one_finding_with_three_occurrences():
    text = "LumoraPay is fast. Try LumoraPay today. LumoraPay again."
    r = review.review_text(text, kb=KB, use_ai=False)
    assert len(r.findings) == 1
    f = r.findings[0]
    assert f.span == "LumoraPay" and len(f.occurrences) == 3
    assert [text[a:b] for a, b in f.occurrences] == ["LumoraPay"] * 3


def test_ai_span_that_repeats_lists_every_occurrence():
    text = "Revolutionary? Our revolutionary app. Truly revolutionary."
    f = only(run([item(span="revolutionary")], text), "revolutionary")
    assert [text[a:b] for a, b in f.occurrences] == ["revolutionary", "revolutionary"]  # exact-case matches


def test_rule_findings_carry_verified_evidence_and_fact_owner():
    r = review.review_text("LumoraPay now has 2 million registered users.", kb=KB, use_ai=False)
    term = next(f for f in r.findings if f.source_id == "T01")
    assert term.evidence == "Lumora Pay" and term.evidence_verified and term.evidence in term.source_text
    fact = next(f for f in r.findings if f.source_id == "F01")
    assert fact.fact_owner == "Comms" and fact.freshness == "expired"
    assert fact.evidence_verified and fact.evidence in fact.source_text