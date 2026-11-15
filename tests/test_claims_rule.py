"""Unsupported superlatives and absolute promises are flagged by rule, citing the claims guideline G07."""
from datetime import date

from engine import knowledge, rules
from engine.schemas import Fact


def kb_g07():
    kb = knowledge.KnowledgeBase(*knowledge.load_brand_kit())     # fresh from the files, not the shared instance
    return kb, kb.get("G07")


def test_superlative_without_a_fact_cites_g07():
    kb, g07 = kb_g07()
    out = rules.check_unsupported_claims("Lumora Pay is the fastest payment app in India.", [], g07)
    assert len(out) == 1 and out[0].source_id == "G07" and "fastest payment app in India" in out[0].span
    assert out[0].evidence_verified and out[0].evidence == g07.text


def test_absolute_promise_is_flagged():
    kb, g07 = kb_g07()
    out = rules.check_unsupported_claims("Every transfer arrives instantly.", [], g07)
    assert out and out[0].span.lower().startswith("every transfer arrives instantly")


def test_plain_copy_is_not_flagged():
    kb, g07 = kb_g07()
    text = "Track upcoming payments in one place. Check the app for current availability in your area."
    assert rules.check_unsupported_claims(text, kb.facts, g07) == []


def test_a_current_fact_backs_the_claim():
    kb, g07 = kb_g07()
    fact = Fact(id="F99", statement="Lumora Pay is the fastest payment app in India (2026 survey).",
                source="survey", owner="Data team", expires_on=date(2099, 1, 1))
    assert rules.check_unsupported_claims("Lumora Pay is the fastest payment app in India.", [fact], g07) == []


def test_without_the_guideline_nothing_is_cited():
    assert rules.check_unsupported_claims("The best app for managing money.", [], None) == []


def test_eval_matches_identical_spans_before_overlapping_ones():
    from eval.run_eval import match
    findings = [{"span": "Lumora pay", "source_id": "T01"},
                {"span": "Lumora Pay has 2 million registered users.", "source_id": "F01"}]
    errors = [{"exact_span": "Lumora Pay has 2 million registered users.", "rule_or_fact_id": "F01"},
              {"exact_span": "Lumora pay", "rule_or_fact_id": "T01"}]
    pairs = {(f["source_id"], e["rule_or_fact_id"]) for f, e in match(findings, errors)}
    assert pairs == {("T01", "T01"), ("F01", "F01")}
