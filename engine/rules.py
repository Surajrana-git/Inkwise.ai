"""Deterministic checks that need no AI: glossary, expired facts, readability.
Owner: Riyana (Step 4).

Each check returns Findings with checked_by='rule' and an empty id;
review.py numbers them (f-001, f-002, ...).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

import textstat

from engine.schemas import UNVERIFIED, Category, CheckedBy, Fact, Finding, SourceMatch, Term

READABILITY_GUIDELINE = "G14"   # "Write for everyone" in the Lumora brand kit
MAX_GRADE = 10.0                # Flesch-Kincaid grade above this is flagged
MIN_WORDS = 20                  # whole-text check needs at least this many words
MIN_SENTENCE_WORDS = 10         # a single sentence is judged from this length
MAX_SENTENCE_GRADE = 14.0       # one sentence above this grade is flagged on its own

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")
_STOP = set("a an the and or of to in on for with is are be by as at it this that we our you your "
            "from not has have can will was were its their into than then so but".split())


def _sentences(text: str) -> list[str]:
    return [m.group().strip() for m in _SENTENCE.finditer(text) if m.group().strip()]


# ---------------------------------------------------------------- terminology

def _variant_regex(variant: str, approved: str) -> re.Pattern:
    # Variants that differ from the approved term only by case ("Lumora pay") and very
    # short ones ("SI") must match case-sensitively, otherwise the approved term would match.
    sensitive = variant.lower() == approved.lower() or len(variant) <= 3
    return re.compile(r"(?<!\w)" + re.escape(variant) + r"(?!\w)", 0 if sensitive else re.I)


def check_terminology(text: str, terms: list[Term]) -> list[Finding]:
    """Flag banned variants of approved terms (checked_by='rule')."""
    out: list[Finding] = []
    for t in terms:
        source_text = f"Approved: '{t.approved}'." + (f" {t.note}" if t.note else "")
        for variant in t.banned_variants:
            for m in _variant_regex(variant, t.approved).finditer(text):
                fix = t.approved
                if m.group()[0].isupper() and fix[0].islower():
                    fix = fix[0].upper() + fix[1:]
                out.append(Finding(
                    id="", category=Category.TERMINOLOGY, span=m.group(), source_id=t.id,
                    source_text=source_text,
                    why=f"'{m.group()}' is a banned variant. Use '{t.approved}'.",
                    suggested_fix=fix, confidence=1.0, checked_by=CheckedBy.RULE))
    return out


# ---------------------------------------------------------------- expired facts

def _stem(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def _words(s: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP}


_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "lakh": 1e5, "lakhs": 1e5,
          "crore": 1e7, "crores": 1e7, "b": 1e9, "bn": 1e9, "billion": 1e9}
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|mn|m|million|lakhs?|crores?|bn|b|billion)?\b", re.I)


def _numbers(s: str) -> set[str]:
    """Numbers normalised so '2M', '2 million' and '2,000,000' all become '2000000' (S8)."""
    out = set()
    for num, unit in _NUM.findall(s):
        v = float(num.replace(",", "")) * _SCALE.get(unit.lower(), 1) if unit else float(num.replace(",", ""))
        out.add(f"{v:g}" if v < 1e5 else str(int(v)))
    return out


def check_expired_facts(text: str, facts: list[Fact], today: Optional[date] = None) -> list[Finding]:
    """Flag text that repeats a fact whose expires_on date has passed.

    A sentence repeats a fact when it contains every number in the fact, shares at least
    3 content words with it, and covers at least half of the fact's content words.
    """
    expired = [f for f in facts if f.is_expired(today)]
    out: list[Finding] = []
    for sent in _sentences(text):
        sw, sn = _words(sent), _numbers(sent)
        best, best_ratio = None, 0.0
        for f in expired:
            fw = _words(f.statement)
            overlap = len(sw & fw)
            ratio = overlap / len(fw) if fw else 0.0
            fn = _numbers(f.statement)
            reworded = any(float(n) >= 1000 for n in fn) and overlap >= 2   # S8: '2M users' vs '2 million users'
            if fn <= sn and (reworded or (overlap >= 3 and ratio >= 0.5)) and ratio > best_ratio:
                best, best_ratio = f, ratio
        if best:
            out.append(Finding(
                id="", category=Category.OUTDATED_FACT, span=sent, source_id=best.id,
                source_text=f"{best.statement} (expired {best.expires_on.isoformat()}; owner: {best.owner})",
                why=f"This repeats fact {best.id}, which expired on {best.expires_on.isoformat()}.",
                suggested_fix=f"Remove this claim, or ask {best.owner} for the current figure before using it.",
                confidence=0.9, checked_by=CheckedBy.RULE))
    return out


# ---------------------------------------------------------------- readability

def check_readability(text: str, source: Optional[SourceMatch] = None) -> list[Finding]:
    """Flag hard-to-read text. `source` is the accessibility guideline (G14) if the kit has it."""
    # S7: judge the whole text, and also each long sentence on its own, so one very
    # dense sentence in a short post is still caught.
    sents = [x for x in _sentences(text) if x.strip()]
    dense = [(textstat.flesch_kincaid_grade(x), x) for x in sents if len(x.split()) >= MIN_SENTENCE_WORDS]
    worst = max(dense, default=(0.0, ""))
    whole = textstat.flesch_kincaid_grade(text) if len(text.split()) >= MIN_WORDS else 0.0
    if whole <= MAX_GRADE and worst[0] <= MAX_SENTENCE_GRADE:
        return []
    grade = max(whole, worst[0])
    longest = worst[1] if worst[0] > MAX_SENTENCE_GRADE else max(sents, key=lambda s: len(s.split()))
    return [Finding(
        id="", category=Category.ACCESSIBILITY, span=longest,
        source_id=source.source_id if source else UNVERIFIED,
        source_text=source.text if source else "",
        why=f"The text reads at about grade {grade:.0f} (target {MAX_GRADE:.0f} or lower). "
            "This is its longest sentence.",
        suggested_fix="Split this into shorter sentences and use simpler words.",
        confidence=0.7, checked_by=CheckedBy.RULE)]
