"""Improvement 2: fact freshness. The planted-fact group must stay at 100%, and the number formats hold."""
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import knowledge, rules  # noqa: E402

FACTS = knowledge.load_brand_kit()[1]             # from the files, unaffected by renewals in other tests
DAY = date(2026, 11, 15)


def test_planted_fact_group_is_perfect():
    sys.path.insert(0, str(ROOT / "eval"))
    import run_fact_eval
    r = run_fact_eval.run()
    assert r["misses"] == [] and r["recall"] == 1.0 and r["precision"] == 1.0 and r["cases"] >= 30


@pytest.mark.parametrize("text", ["Join 20 lakh Lumora Pay users.", "Over 2M registered Lumora Pay users.",
                                  "Lumora Pay has two million registered users.", "Lumora Pay has 2,000,000 registered users.",
                                  "Lumora Pay has 2.1M registered users."])
def test_same_figure_in_any_format_is_the_expired_fact(text):
    assert [f.source_id for f in rules.check_expired_facts(text, FACTS, DAY)] == ["F01"]


@pytest.mark.parametrize("text", ["Lumora Pay has 3 million registered users.", "We launched Lumora Pay in 2026.",
                                  "Lumora Pay has 2.5 million registered users."])
def test_different_figures_and_years_are_not_the_fact(text):
    assert rules.check_expired_facts(text, FACTS, DAY) == []


def test_decimals_do_not_split_sentences():
    assert rules._sentences("Rated 4.8 out of 5. Pay 2.1M times!") == ["Rated 4.8 out of 5.", "Pay 2.1M times!"]


def test_expiring_soon_is_advice_with_days_left():
    f = rules.check_expiring_facts("Lumora Pay has 2 million registered users.", FACTS, date(2026, 9, 10))
    assert [(x.source_id, x.freshness) for x in f] == [("F01", "expiring_soon")]
    assert "20 days" in f[0].why and f[0].fact_owner and f[0].confidence < 0.9
    assert rules.check_expiring_facts("Lumora Pay has 2 million registered users.", FACTS, date(2026, 8, 1)) == []
