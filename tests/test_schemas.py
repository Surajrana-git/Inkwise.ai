from datetime import date

import pytest

from engine.schemas import CheckedBy, Category, Fact, Finding, UNVERIFIED


def make(source_id):
    return Finding(id="f-1", category=Category.CLAIM, span="x", source_id=source_id,
                   why="y", suggested_fix="z", confidence=0.5, checked_by=CheckedBy.AI)


def test_valid_sources():
    for sid in ("G04", "F12", "T07", UNVERIFIED):
        assert make(sid).source_id == sid


def test_bad_source_rejected():
    with pytest.raises(ValueError):
        make("guideline 4")


def test_unverified_flag():
    assert not make(UNVERIFIED).is_verified
    assert make("G01").is_verified


def test_fact_expiry():
    f = Fact(id="F01", statement="2M users", source="Q2 report", owner="Comms",
             expires_on=date(2026, 1, 1))
    assert f.is_expired(today=date(2026, 11, 8))
    assert not Fact(id="F02", statement="s", source="s", owner="o").is_expired()
