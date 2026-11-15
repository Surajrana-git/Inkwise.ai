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

from engine.schemas import (
    UNVERIFIED,
    Category,
    CheckedBy,
    Fact,
    Finding,
    SourceMatch,
    Term,
)

READABILITY_GUIDELINE = "G14"
MAX_GRADE = 10.0
MIN_WORDS = 20
MAX_SENTENCE_WORDS = 25

_SENTENCE = re.compile(r"(?:[^.!?\n]|(?<=\d)\.(?=\d))+[.!?]*")   # "2.1M" / "4.8" are not sentence ends

_STOP = set(
    "a an the and or of to in on for with is are be by as at it this that "
    "we our you your from not has have can will was were its their into "
    "than then so but".split()
)


def _sentences(text: str) -> list[str]:
    """Split text into sentences."""
    return [
        match.group().strip()
        for match in _SENTENCE.finditer(text)
        if match.group().strip()
    ]


# ---------------------------------------------------------------- terminology


def _variant_regex(variant: str, approved: str) -> re.Pattern:
    """Create a regex for a banned terminology variant."""
    sensitive = variant.lower() == approved.lower() or len(variant) <= 3

    return re.compile(
        r"(?<!\w)" + re.escape(variant) + r"(?!\w)",
        0 if sensitive else re.I,
    )


def check_terminology(text: str, terms: list[Term]) -> list[Finding]:
    """Flag banned variants of approved terms."""
    out: list[Finding] = []

    for term in terms:
        source_text = f"Approved: '{term.approved}'."

        if term.note:
            source_text += f" {term.note}"

        for variant in term.banned_variants:
            pattern = _variant_regex(variant, term.approved)

            for match in pattern.finditer(text):
                fix = term.approved

                if match.group()[0].isupper() and fix[0].islower():
                    fix = fix[0].upper() + fix[1:]

                out.append(
                    Finding(
                        id="",
                        category=Category.TERMINOLOGY,
                        span=match.group(),
                        source_id=term.id,
                        source_text=source_text,
                        why=(
                            f"'{match.group()}' is a banned variant. "
                            f"Use '{term.approved}'."
                        ),
                        suggested_fix=fix,
                        confidence=1.0,
                        checked_by=CheckedBy.RULE,
                        evidence=term.approved,
                        evidence_verified=True,
                    )
                )

    return out


# ---------------------------------------------------------------- expired facts


def _stem(word: str) -> str:
    """Simple plural normalization."""
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]

    return word


def _words(text: str) -> set[str]:
    """Extract normalized content words."""
    return {
        _stem(word)
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in _STOP
    }


def _normalize_number(value: str) -> str:
    """Normalize numeric forms such as 2M, 2 million, and 2,000,000."""
    cleaned = value.lower().replace(",", "").replace(" ", "")

    multiplier = 1

    if cleaned.endswith(("million", "mn")):
        cleaned = re.sub(r"(million|mn)$", "", cleaned)
        multiplier = 1_000_000
    elif cleaned.endswith("billion"):
        cleaned = cleaned[:-7]
        multiplier = 1_000_000_000
    elif cleaned.endswith("m"):
        cleaned = cleaned[:-1]
        multiplier = 1_000_000
    elif cleaned.endswith("k"):
        cleaned = cleaned[:-1]
        multiplier = 1_000

    try:
        number = float(cleaned) * multiplier

        if number.is_integer():
            return str(int(number))

        return str(number)

    except ValueError:
        return cleaned


_SCALE = {"thousand": 1e3, "k": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
          "million": 1e6, "mn": 1e6, "m": 1e6, "crore": 1e7, "crores": 1e7, "cr": 1e7,
          "billion": 1e9, "bn": 1e9, "b": 1e9}
_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "hundred": 100}
_NUM_RE = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?|" + "|".join(sorted(_WORDNUM, key=len, reverse=True)) + r")"
    r"(?:\s*(%|per\s?cent\b|percent\b|" + "|".join(sorted(_SCALE, key=len, reverse=True)) + r")\b)?",
    re.I)


def _number_values(text: str) -> list[tuple[float, bool]]:
    """Numbers in text as (value, is_percent): 2M = 2 million = 20 lakh = 2,000,000; 2 crore = 20 million;
    "two million" = 2 million; 40% = 40 percent = 40 per cent. Years (1900-2100 without a unit) are skipped."""
    out = []
    for m in _NUM_RE.finditer(text):
        raw, unit = m.group(1).lower(), (m.group(2) or "").lower().replace(" ", "")
        try:
            v = float(_WORDNUM[raw]) if raw in _WORDNUM else float(raw.replace(",", ""))
        except ValueError:
            continue
        pct = unit in ("%", "percent", "percent", "percent") or unit.startswith("per")
        if not pct and unit:
            v *= _SCALE.get(unit, 1)
        if not unit and raw.isdigit() and 1900 <= v <= 2100 and len(raw) == 4:
            continue                                  # "Q1 2026", "in 2026": a date, not a figure
        out.append((v, pct))
    return out


def _same_figure(fact: tuple[float, bool], said: tuple[float, bool]) -> bool:
    """Exact for small counts and ratings; within 10% for big figures, so rounded or restated numbers
    ("over 2 million", "2.1M", "20 lakh") still match the approved one."""
    (fv, fp), (sv, sp) = fact, said
    if fp != sp:
        return False
    if fv >= 1000:
        return abs(sv - fv) <= 0.10 * fv
    return abs(sv - fv) < 1e-9


def _numbers(text: str) -> set[str]:
    """Normalized numbers in text (kept for callers that compare sets of strings)."""
    return {(f"{v:g}%" if p else f"{v:g}") for v, p in _number_values(text)}


def _numbers_match(fact_text: str, sentence: str) -> bool:
    """Every figure in the fact appears in the sentence, allowing the units and rounding above."""
    fact_vals = _number_values(fact_text)
    said = _number_values(sentence)
    return bool(fact_vals) and all(any(_same_figure(f, x) for x in said) for f in fact_vals)


def _fact_content_words(text: str) -> set[str]:
    """Extract meaningful fact words, excluding numbers and number scales."""
    number_words = set(_SCALE) | set(_WORDNUM) | {"percent", "per", "cent"}

    return {
        word
        for word in _words(text)
        if not word.isdigit() and word not in number_words
    }


EXPIRING_DAYS = 30          # a fact expiring within this many days gets an advisory finding


def _best_fact(sentence: str, facts: list[Fact]):
    """The fact a sentence repeats: all its figures present (any unit / rounding) and enough shared words."""
    sentence_words = _fact_content_words(sentence)
    best, best_ratio = None, 0.0
    for fact in facts:
        fact_words = _fact_content_words(fact.statement)
        overlap = len(sentence_words & fact_words)
        ratio = overlap / len(fact_words) if fact_words else 0.0
        if _numbers_match(fact.statement, sentence) and overlap >= 1 and ratio >= 0.25 and ratio > best_ratio:
            best, best_ratio = fact, ratio
    return best


def check_expired_facts(
    text: str,
    facts: list[Fact],
    today: Optional[date] = None,
) -> list[Finding]:
    """Flag every sentence that repeats a fact whose expires_on date has passed.

    A sentence repeats a fact when all of the fact's figures are in it (2M = 2 million = 20 lakh,
    40% = 40 percent, rounded big figures within 10%) and it shares at least 25% of the fact's content words.
    """
    expired = [fact for fact in facts if fact.is_expired(today)]
    out: list[Finding] = []
    for sentence in _sentences(text):
        best = _best_fact(sentence, expired)
        if best:
            out.append(Finding(
                id="", category=Category.OUTDATED_FACT, span=sentence, source_id=best.id,
                source_text=f"{best.statement} (expired {best.expires_on.isoformat()}; owner: {best.owner})",
                why=f"This repeats fact {best.id}, which expired on {best.expires_on.isoformat()}.",
                suggested_fix=f"Remove this claim, or ask {best.owner} for the current figure before using it.",
                confidence=0.9, checked_by=CheckedBy.RULE, evidence=best.statement, evidence_verified=True,
                fact_owner=best.owner, freshness="expired"))
    return out


def check_expiring_facts(
    text: str,
    facts: list[Fact],
    today: Optional[date] = None,
    days: int = EXPIRING_DAYS,
) -> list[Finding]:
    """Advisory: the text repeats a fact that is still valid but expires within `days` days."""
    today = today or date.today()
    soon = [f for f in facts if f.expires_on and not f.is_expired(today) and (f.expires_on - today).days <= days]
    out: list[Finding] = []
    for sentence in _sentences(text):
        best = _best_fact(sentence, soon)
        if best:
            left = (best.expires_on - today).days
            out.append(Finding(
                id="", category=Category.OUTDATED_FACT, span=sentence, source_id=best.id,
                source_text=f"{best.statement} (expires {best.expires_on.isoformat()}; owner: {best.owner})",
                why=(f"This repeats fact {best.id}. It is still valid, but it expires in {left} day"
                     f"{'s' if left != 1 else ''} ({best.expires_on.isoformat()})."),
                suggested_fix=f"Keep it if the campaign ends before then; otherwise ask {best.owner} to re-verify it.",
                confidence=0.7, checked_by=CheckedBy.RULE, evidence=best.statement, evidence_verified=True,
                fact_owner=best.owner, freshness="expiring_soon"))
    return out


# ---------------------------------------------------------------- readability


def check_readability(
    text: str,
    source: Optional[SourceMatch] = None,
) -> list[Finding]:
    """Flag hard-to-read text using grade level and sentence length."""
    words = text.split()
    sentences = _sentences(text)

    if not sentences:
        return []

    longest = max(
        sentences,
        key=lambda sentence: len(sentence.split()),
    )

    longest_word_count = len(longest.split())

    # Do not flag very short, simple text.
    if len(words) < MIN_WORDS and longest_word_count < 10:
        return []

    grade = textstat.flesch_kincaid_grade(text)

    # Flag if grade level is too high OR sentence is excessively long.
    if grade <= MAX_GRADE and longest_word_count < MAX_SENTENCE_WORDS:
        return []

    return [
        Finding(
            id="",
            category=Category.ACCESSIBILITY,
            span=longest,
            source_id=source.source_id if source else UNVERIFIED,
            source_text=source.text if source else "",
            why=(
                f"The text reads at about grade {grade:.0f} "
                f"(target {MAX_GRADE:.0f} or lower), or contains "
                f"a long sentence with {longest_word_count} words."
            ),
            suggested_fix=(
                "Split this into shorter sentences and use simpler words."
            ),
            confidence=0.7,
            checked_by=CheckedBy.RULE,
        )
    ]