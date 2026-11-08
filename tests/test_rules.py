from datetime import date

from engine import rules
from engine.schemas import Category, Fact, SourceMatch, Term

TERMS = [Term(id="T01", approved="Lumora Pay", banned_variants=["LumoraPay", "Lumora pay", "LPay"],
              note="Always two words."),
         Term(id="T05", approved="scheduled payment", banned_variants=["auto debit"]),
         Term(id="T02", approved="Spend Insights", banned_variants=["SI"])]
FACTS = [Fact(id="F01", statement="Lumora Pay has 2 million registered users.", source="x",
              owner="Comms", expires_on=date(2026, 9, 30)),
         Fact(id="F06", statement="Lumora support is available seven days a week.", source="x",
              owner="Support", expires_on=date(2099, 1, 1))]
TODAY = date(2026, 11, 8)


def test_banned_variant_flagged_with_fix():
    f = rules.check_terminology("Try LumoraPay today.", TERMS)
    assert len(f) == 1 and f[0].source_id == "T01" and f[0].suggested_fix == "Lumora Pay"
    assert f[0].category == Category.TERMINOLOGY and f[0].confidence == 1.0


def test_approved_term_not_flagged_even_if_variant_differs_only_by_case():
    assert rules.check_terminology("Lumora Pay is simple.", TERMS) == []
    assert len(rules.check_terminology("Lumora pay is simple.", TERMS)) == 1


def test_case_insensitive_variant_keeps_sentence_capital():
    f = rules.check_terminology("Auto debit is easy.", TERMS)
    assert f[0].suggested_fix == "Scheduled payment"


def test_short_variant_is_case_sensitive():
    assert rules.check_terminology("This is si unusual.", TERMS) == []
    assert len(rules.check_terminology("Use SI now.", TERMS)) == 1


def test_expired_fact_flagged_and_current_fact_ignored():
    text = "Join our 2 million users. Our support is available seven days a week."
    f = rules.check_expired_facts(text, FACTS, today=TODAY)
    assert [x.source_id for x in f] == ["F01"]
    assert f[0].span == "Join our 2 million users."


def test_different_number_is_not_the_expired_fact():
    assert rules.check_expired_facts("Lumora Pay has 12 million registered users.", FACTS, TODAY) == []


def test_readability_flags_dense_text_and_cites_guideline():
    dense = ("Notwithstanding contemporaneous organisational considerations, the implementation "
             "of comprehensive transactional functionality necessitates extraordinarily "
             "sophisticated infrastructural capabilities throughout multinational jurisdictions. "
             "Consequently, stakeholders should anticipate considerable administrative complexity.")
    src = SourceMatch(source_id="G14", source_type="guideline", text="Write for everyone.", score=0)
    f = rules.check_readability(dense, src)
    assert len(f) == 1 and f[0].source_id == "G14" and f[0].category == Category.ACCESSIBILITY
    assert rules.check_readability(dense)[0].source_id == "UNVERIFIED"


def test_readability_ignores_short_or_simple_text():
    assert rules.check_readability("Send money in a few taps.") == []
    assert rules.check_readability("Send money in a few taps. " * 6) == []
