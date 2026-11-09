"""Mask personal data before text leaves the machine.
Owner: Riyana (Step 8).

redact()           -> (masked_text, count)       the stub's public contract
redact_with_map()  -> (masked_text, mapping)     lets review.py restore real values
restore()          -> puts the real values back into Gemini's answer
Regex cannot find every name. The demo also uses synthetic data only.
"""
from __future__ import annotations

import re

ALLOW = {"Lumora"}  # brand words that must never be masked as names
# Capitalised words that start sentences or name places/products, never people (S4)
_COMMON = set("""The A An We Our You Your This That These Those It Its Join Open Click Call Contact Get Try
Sign Send Pay New Now Today Download Learn Read See Check Use Visit Start Meet Hi Hello Dear Thanks Team
India Indian UPI RBI Google Apple Play Store App Android Monday Tuesday Wednesday Thursday Friday Saturday
Sunday January February March April May June July August September October November December""".split())
_CAP_RUN = re.compile(r"\b[A-Z][a-z]{1,15}(?:\s+[A-Z][a-z]{1,15})+\b")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_DIGITS = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{8,}\d(?!\w)")
_TITLE_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?")
_CUE_NAME = re.compile(
    r"(?i:\b(?:my name is|dear|regards,?|thanks,?|sincerely,?)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)")


def redact_with_map(text: str, allow: set[str] | None = None) -> tuple[str, dict[str, str]]:
    allow = ALLOW | _COMMON | (allow or set())
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}

    def put(kind: str, value: str) -> str:
        for ph, orig in mapping.items():
            if orig == value:
                return ph
        counters[kind] = counters.get(kind, 0) + 1
        ph = f"[{kind}_{counters[kind]}]"
        mapping[ph] = value
        return ph

    def digits(m: re.Match) -> str:
        v = m.group()
        n = sum(c.isdigit() for c in v)
        if n < 10:
            return v  # prices, years, percentages stay
        return put("PHONE" if n <= 11 or v.startswith("+") else "ID", v)

    def cue(m: re.Match) -> str:
        name = m.group(1)
        if name.split()[0] in allow:
            return m.group()
        return m.group().replace(name, put("NAME", name))

    text = _EMAIL.sub(lambda m: put("EMAIL", m.group()), text)
    text = _PAN.sub(lambda m: put("ID", m.group()), text)
    text = _DIGITS.sub(digits, text)
    text = _TITLE_NAME.sub(lambda m: put("NAME", m.group()), text)
    text = _CUE_NAME.sub(cue, text)
    # S4: runs of capitalised words such as "Call Priya Sharma": drop brand, product and
    # common words from the edges; two or more words left over are treated as a name.
    def full_name(m: re.Match) -> str:
        words = m.group().split()
        i, j = 0, len(words)
        while i < j and words[i] in allow:
            i += 1
        while j > i and words[j - 1] in allow:
            j -= 1
        core = words[i:j]
        if len(core) < 2 or any(w in allow for w in core):
            return m.group()
        name = " ".join(core)
        return m.group().replace(name, put("NAME", name))

    text = _CAP_RUN.sub(full_name, text)
    return text, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    for ph, orig in mapping.items():
        text = text.replace(ph, orig)
    return text


def redact(text: str) -> tuple[str, int]:
    """Return (redacted_text, number_of_items_masked)."""
    masked, mapping = redact_with_map(text)
    return masked, len(mapping)
