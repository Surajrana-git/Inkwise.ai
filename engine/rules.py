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

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")

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


def _numbers(text: str) -> set[str]:
    """Extract and normalize numbers from text."""
    pattern = re.compile(
        r"\b\d[\d,]*(?:\.\d+)?\s*(?:million|billion|mn|m|k)?\b",
        re.I,
    )

    return {
        _normalize_number(match.group())
        for match in pattern.finditer(text)
    }


def _fact_content_words(text: str) -> set[str]:
    """Extract meaningful fact words, excluding numbers and number scales."""
    number_words = {"million", "billion", "mn", "m", "k"}

    return {
        word
        for word in _words(text)
        if not word.isdigit() and word not in number_words
    }


def check_expired_facts(
    text: str,
    facts: list[Fact],
    today: Optional[date] = None,
) -> list[Finding]:
    """Flag text that repeats a fact whose expires_on date has passed.

    A sentence repeats an expired fact when:
    - The fact's numbers are present in the sentence.
    - It shares meaningful content words with the fact.
    - It covers at least 25% of the fact's meaningful content words.
    """
    expired = [fact for fact in facts if fact.is_expired(today)]
    out: list[Finding] = []

    for sentence in _sentences(text):
        sentence_words = _fact_content_words(sentence)
        sentence_numbers = _numbers(sentence)

        best = None
        best_ratio = 0.0

        for fact in expired:
            fact_words = _fact_content_words(fact.statement)

            overlap = len(sentence_words & fact_words)

            ratio = (
                overlap / len(fact_words)
                if fact_words
                else 0.0
            )

            fact_numbers = _numbers(fact.statement)

            if (
                fact_numbers
                and fact_numbers <= sentence_numbers
                and overlap >= 1
                and ratio >= 0.25
                and ratio > best_ratio
            ):
                best = fact
                best_ratio = ratio

        if best:
            out.append(
                Finding(
                    id="",
                    category=Category.OUTDATED_FACT,
                    span=sentence,
                    source_id=best.id,
                    source_text=(
                        f"{best.statement} "
                        f"(expired {best.expires_on.isoformat()}; "
                        f"owner: {best.owner})"
                    ),
                    why=(
                        f"This repeats fact {best.id}, which expired on "
                        f"{best.expires_on.isoformat()}."
                    ),
                    suggested_fix=(
                        f"Remove this claim, or ask {best.owner} for the "
                        "current figure before using it."
                    ),
                    confidence=0.9,
                    checked_by=CheckedBy.RULE,
                    evidence=best.statement,
                    evidence_verified=True,
                    fact_owner=best.owner,
                    freshness="expired",
                )
            )

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