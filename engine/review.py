
"""AI review: retrieves sources, asks Gemini, returns cited Findings.
Owner: Riyana (Steps 4 and 8, Round 3 tasks 2 and 3).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Callable, Optional

from engine import knowledge, redact, rules
from engine.schemas import UNVERIFIED, Category, CheckedBy, Finding, ReviewResult

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-latest"
MAX_TRIES = 2
TIMEOUT_MS = 45_000
TOTAL_BUDGET_S = 25
MAX_AI_FINDINGS = 10
UNVERIFIED_MAX_CONFIDENCE = 0.6
MIN_EVIDENCE_CHARS = 8
RECITE_FROM_EVIDENCE = True

_sleep = time.sleep
_last_model = ""

LLM = Callable[[str], str]

PROMPT = """You review marketing text for Lumora, a fictional fintech brand,
against its brand kit.

Use ONLY the SOURCES below. Never invent guidelines or facts.

SOURCES (id: text):
{sources}

TEXT TO REVIEW:
<<<
{text}
>>>

Banned product names and expired facts are checked separately. Do not report them.

Look for:
- hype or jargon
- pushy tone
- guarantees
- claims or superlatives with no support in SOURCES
- unclear fees or availability
- hidden next steps
- hard-to-read wording

Return ONLY a JSON list. Each item:
{{"category": "tone|terminology|claim|outdated_fact|messaging|accessibility",
 "span": "words copied EXACTLY from the text under review",
 "source_id": "an id from SOURCES, or UNVERIFIED",
 "evidence": "words copied EXACTLY from the SOURCE you cite; empty if UNVERIFIED",
 "why": "one plain sentence",
 "suggested_fix": "a rewrite of the span that keeps the writer's intent and adds no new facts",
 "confidence": 0.0 to 1.0}}

Rules:
- Cite a source id from SOURCES for every finding and copy exact words from that source into evidence.
- G07 claim guidelines must be considered when reviewing claims and superlatives.
- If two sources fit, cite the one whose title is most specific to the problem.
- Use UNVERIFIED only for a claim that none of the SOURCES supports or refutes.
- Report an issue only when the text clearly breaks the cited rule.
- Text that follows the rules must produce no finding.
- If unsure, return [].
- Keep placeholders such as [EMAIL_1] unchanged.
- If nothing is wrong, return [].
"""


# ---------------------------------------------------------------- Gemini call


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def _fallback_models() -> list[str]:
    raw = os.getenv("GEMINI_FALLBACK_MODELS", "")
    return [
        model.strip()
        for model in raw.split(",")
        if model.strip() and model.strip() != _model_name()
    ]


def _retryable(e: Exception) -> bool:
    message = str(e).upper()
    return any(
        token in message
        for token in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "HIGH DEMAND")
    )


def _gemini_generate(prompt: str) -> str:
    """Call Gemini with retries and configured fallback models."""
    global _last_model

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=TIMEOUT_MS),
    )

    primary = _model_name()
    models = [primary] + _fallback_models()
    last_error: Optional[Exception] = None

    for model_index, model in enumerate(models):
        attempts = MAX_TRIES if model_index == 0 else 1

        for attempt in range(attempts):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                _last_model = model
                return response.text or ""

            except Exception as exc:
                last_error = exc
                is_retryable = _retryable(exc)

                if is_retryable and attempt < attempts - 1:
                    delay = 4.0 * (2 ** attempt)
                    log.warning(
                        "Gemini busy on %s. Retrying in %.0fs",
                        model,
                        delay,
                    )
                    _sleep(delay)
                    continue

                # Retryable failures can move to the next fallback model.
                # Non-retryable errors (e.g. model not found) also move on.
                break

    if last_error:
        raise last_error

    return ""


# ---------------------------------------------------------------- Parsing


def _parse(raw: str) -> list[dict]:
    raw = re.sub(
        r"^```(?:json)?|```$",
        "",
        (raw or "").strip(),
        flags=re.M,
    ).strip()

    data = json.loads(raw) if raw else []

    if isinstance(data, dict):
        data = data.get("findings", [])

    return [item for item in data if isinstance(item, dict)]


# ---------------------------------------------------------------- Evidence check


def _find_in_source(evidence: str, source_text: str) -> Optional[str]:
    """Find exact evidence in source, ignoring case and whitespace differences."""
    words = (evidence or "").strip().strip("\"'").strip(" .,;:").split()

    if not words or len(" ".join(words)) < MIN_EVIDENCE_CHARS:
        return None

    pattern = r"\s+".join(re.escape(word) for word in words)
    match = re.search(pattern, source_text or "", re.I)

    return match.group() if match else None


def _verify_evidence(
    source_id: str,
    evidence: str,
    sources: dict[str, str],
) -> tuple[str, str, bool]:
    """Return (source_id, evidence_text, verified)."""

    if source_id in sources:
        hit = _find_in_source(evidence, sources[source_id])
        if hit:
            return source_id, hit, True

    if RECITE_FROM_EVIDENCE and evidence:
        owners = [
            key
            for key, source_text in sources.items()
            if _find_in_source(evidence, source_text)
        ]

        if len(owners) == 1:
            owner = owners[0]
            hit = _find_in_source(evidence, sources[owner]) or ""
            return owner, hit, True

    return UNVERIFIED, "", False


# ---------------------------------------------------------------- AI findings


def _exact_slice(span: str, text: str) -> Optional[str]:
    index = text.find(span)

    if index < 0:
        index = text.lower().find(span.lower())

    if index >= 0 and span.strip():
        return text[index:index + len(span)]

    return None


def _source_listing(kb, safe: str) -> tuple[dict[str, str], dict[str, object]]:
    """Retrieve relevant sources and ensure G07 is included for claim checking."""
    matches = list(kb.search(safe))

    # Ensure the claim guideline G07 is available to the AI reviewer.
    g07 = kb.get("G07")
    if g07 and all(match.source_id != "G07" for match in matches):
        matches.append(g07)

    sources = {match.source_id: match.text for match in matches}
    category_of = {
        guideline.id: guideline.category
        for guideline in kb.guidelines
    }

    return sources, category_of


def _ai_findings(
    text: str,
    safe: str,
    mapping: dict[str, str],
    kb,
    generate: LLM,
) -> list[Finding]:
    sources, category_of = _source_listing(kb, safe)

    listing = "\n".join(
        f"{source_id}: {source_text}"
        for source_id, source_text in sources.items()
    ) or "(none)"

    items = _parse(
        generate(PROMPT.format(sources=listing, text=safe))
    )

    out: list[Finding] = []

    for item in items[:MAX_AI_FINDINGS]:
        masked_span = _exact_slice(str(item.get("span", "")), safe)

        if not masked_span:
            continue

        span = redact.restore(masked_span, mapping)

        if span not in text:
            continue

        category_value = str(item.get("category", "")).strip().lower()

        try:
            category = Category(category_value)
        except ValueError:
            continue

        cited = str(item.get("source_id", UNVERIFIED))
        raw_evidence = str(item.get("evidence", "")).strip()

        sid, evidence, verified = _verify_evidence(
            cited,
            raw_evidence,
            sources,
        )

        # If the model cited a known source but supplied no quote,
        # retain the citation as unverified. A wrong quote is UNVERIFIED.
        if not raw_evidence and cited in sources:
            sid = cited
            evidence = ""
            verified = False

        if verified and sid != cited and sid in category_of:
            try:
                category = Category(str(category_of[sid]).lower())
            except ValueError:
                pass

        try:
            confidence = max(
                0.0,
                min(1.0, float(item.get("confidence", 0.5))),
            )
        except (TypeError, ValueError):
            confidence = 0.5

        if not verified:
            confidence = min(confidence, UNVERIFIED_MAX_CONFIDENCE)

        suggested_fix = redact.restore(
            str(item.get("suggested_fix", "")).strip(),
            mapping,
        )

        why = redact.restore(
            str(item.get("why", "")).strip(),
            mapping,
        )

        out.append(
            Finding(
                id="",
                category=category,
                span=span,
                source_id=sid,
                source_text=sources.get(sid, "") if verified else "",
                why=why or "Flagged by the AI reviewer.",
                suggested_fix=(
                    suggested_fix
                    or "Rewrite this part to follow the cited guideline."
                ),
                confidence=confidence,
                checked_by=CheckedBy.AI,
                evidence=evidence,
                evidence_verified=verified,
            )
        )

    return out


# ---------------------------------------------------------------- Merge + public API


def _all_occurrences(text: str, span: str) -> list[tuple[int, int]]:
    return [
        (match.start(), match.end())
        for match in re.finditer(re.escape(span), text)
    ]


def _merge(
    text: str,
    rule_f: list[Finding],
    ai_f: list[Finding],
) -> list[Finding]:
    def rng(finding: Finding) -> tuple[int, int]:
        start = max(text.find(finding.span), 0)
        return start, start + len(finding.span)

    kept: list[Finding] = []
    seen: set[tuple[str, str, str]] = set()

    for finding in rule_f:
        key = (
            finding.category.value,
            finding.source_id,
            finding.span,
        )

        if key in seen:
            continue

        seen.add(key)
        kept.append(finding)

    for finding in ai_f:
        key = (
            finding.category.value,
            finding.source_id,
            finding.span,
        )

        start, end = rng(finding)

        if key in seen or any(
            start < rule_end and rule_start < end
            for rule_start, rule_end in map(rng, kept)
        ):
            continue

        seen.add(key)
        kept.append(finding)

    kept.sort(key=lambda finding: rng(finding)[0])

    return [
        finding.model_copy(
            update={
                "id": f"f-{index:03d}",
                "occurrences": _all_occurrences(text, finding.span),
            }
        )
        for index, finding in enumerate(kept, 1)
    ]


def review_text(
    text: str,
    kb: Optional[knowledge.KnowledgeBase] = None,
    llm: Optional[LLM] = None,
    use_ai: bool = True,
) -> ReviewResult:
    """Run deterministic checks and AI review, returning all findings."""

    kb = kb or knowledge.get_kb()
    safe, mapping = redact.redact_with_map(text)

    rule_findings = (
        rules.check_terminology(text, kb.terms)
        + rules.check_expired_facts(text, kb.facts)
        + rules.check_readability(
            text,
            kb.get(rules.READABILITY_GUIDELINE),
        )
    )

    ai_findings: list[Finding] = []
    model = ""
    ai_error = ""

    generate = llm

    if use_ai and text.strip():
        if generate is None:
            if os.getenv("GEMINI_API_KEY"):
                generate = _gemini_generate
            else:
                ai_error = "GEMINI_API_KEY is not set."

        if generate:
            try:
                ai_findings = _ai_findings(
                    text,
                    safe,
                    mapping,
                    kb,
                    generate,
                )

                model = (
                    _last_model
                    if llm is None
                    else "injected-llm"
                )

            except Exception as exc:
                ai_error = (
                    f"AI review unavailable; returning rule checks only: {exc}"
                )
                log.warning(
                    "AI review failed, returning rule findings only: %s",
                    exc,
                )

    return ReviewResult(
        text=safe,
        findings=_merge(text, rule_findings, ai_findings),
        redactions=len(mapping),
        model=model,
        ai_error=ai_error,
    )
