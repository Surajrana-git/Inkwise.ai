"""AI review: retrieves sources, asks Gemini, returns cited Findings.
Owner: Riyana (Steps 4 and 8).

Rules for this module:
- Every Finding must cite a source_id from knowledge.search() results, or be
  UNVERIFIED when no source supports or refutes a claim.
- Text passes through redact before any API call.
- With no GEMINI_API_KEY, or if Gemini fails, we return the rule findings only
  (result.model is "" in that case) so the demo never breaks.
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
MAX_TRIES = 5
TIMEOUT_MS = 45_000  # give up on one Gemini call after 45 seconds
MAX_AI_FINDINGS = 10
UNVERIFIED_MAX_CONFIDENCE = 0.6
_sleep = time.sleep  # replaced in tests

LLM = Callable[[str], str]

PROMPT = """You review marketing text for Lumora, a fictional fintech brand, against its brand kit.
Use ONLY the SOURCES below. Never invent guidelines or facts.

SOURCES (id: text):
{sources}

TEXT TO REVIEW:
<<<
{text}
>>>

Banned product names and expired facts are checked separately. Do not report them.
Look for: hype or jargon, pushy tone, guarantees, claims or superlatives with no support in SOURCES,
unclear fees or availability, hidden next steps, hard-to-read wording.

Return ONLY a JSON list. Each item:
{{"category": "tone|terminology|claim|outdated_fact|messaging|accessibility",
 "span": "words copied EXACTLY from the text",
 "source_id": "an id from SOURCES, or UNVERIFIED",
 "why": "one plain sentence",
 "suggested_fix": "a rewrite of the span that keeps the writer's intent and adds no new facts",
 "confidence": 0.0 to 1.0}}

Rules:
- Cite a source id from SOURCES for every finding.
- Use UNVERIFIED only for a claim that none of the SOURCES supports or refutes.
- Keep placeholders such as [EMAIL_1] unchanged.
- If nothing is wrong, return [].
"""


# ---------------------------------------------------------------- Gemini call

def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def _retryable(e: Exception) -> bool:
    s = str(e)
    return any(x in s for x in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"))


def _gemini_generate(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                          http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    delay = 4.0
    for attempt in range(MAX_TRIES):
        try:
            resp = client.models.generate_content(
                model=_model_name(), contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
            return resp.text or ""
        except Exception as e:  # retry only rate-limit / overload errors
            if attempt < MAX_TRIES - 1 and _retryable(e):
                log.warning("Gemini busy (%s). Retrying in %.0fs", type(e).__name__, delay)
                _sleep(delay)
                delay *= 2
                continue
            raise
    return ""


def _parse(raw: str) -> list[dict]:
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    data = json.loads(raw) if raw else []
    if isinstance(data, dict):
        data = data.get("findings", [])
    return [d for d in data if isinstance(d, dict)]


# ---------------------------------------------------------------- AI findings

def _exact_slice(span: str, text: str) -> Optional[str]:
    i = text.find(span)
    if i < 0:
        i = text.lower().find(span.lower())
    return text[i:i + len(span)] if i >= 0 and span.strip() else None


def _ai_findings(text: str, safe: str, mapping: dict[str, str], kb, generate: LLM) -> list[Finding]:
    sources = {m.source_id: m.text for m in kb.search(safe)}
    listing = "\n".join(f"{k}: {v}" for k, v in sources.items()) or "(none)"
    items = _parse(generate(PROMPT.format(sources=listing, text=safe)))

    out: list[Finding] = []
    for item in items[:MAX_AI_FINDINGS]:
        masked_span = _exact_slice(str(item.get("span", "")), safe)
        if not masked_span:
            continue                                   # model quoted words that are not in the text
        span = redact.restore(masked_span, mapping)
        if span not in text:
            continue
        try:
            category = Category(item.get("category"))
        except ValueError:
            continue
        sid = item.get("source_id")
        if sid not in sources:
            sid = UNVERIFIED                           # cited something we never retrieved
        try:
            conf = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        if sid == UNVERIFIED:
            conf = min(conf, UNVERIFIED_MAX_CONFIDENCE)
        fix = redact.restore(str(item.get("suggested_fix", "")).strip(), mapping)
        out.append(Finding(
            id="", category=category, span=span, source_id=sid,
            source_text=sources.get(sid, ""),
            why=redact.restore(str(item.get("why", "")).strip(), mapping) or "Flagged by the AI reviewer.",
            suggested_fix=fix or "Rewrite this part to follow the cited guideline.",
            confidence=conf, checked_by=CheckedBy.AI))
    return out


# ---------------------------------------------------------------- merge + public API

def _merge(text: str, rule_f: list[Finding], ai_f: list[Finding]) -> list[Finding]:
    def rng(f: Finding) -> tuple[int, int]:
        s = max(text.find(f.span), 0)
        return s, s + len(f.span)

    kept = list(rule_f)
    for a in ai_f:  # when a rule and the AI flag the same words, the rule wins
        s, e = rng(a)
        if not any(s < re_ and rs < e for rs, re_ in map(rng, kept)):
            kept.append(a)
    kept.sort(key=lambda f: rng(f)[0])
    return [f.model_copy(update={"id": f"f-{i:03d}"}) for i, f in enumerate(kept, 1)]


def review_text(text: str, kb: Optional[knowledge.KnowledgeBase] = None,
                llm: Optional[LLM] = None, use_ai: bool = True) -> ReviewResult:
    """Run rule checks + AI checks and return all findings.

    kb / llm are for tests and evaluation; the app just calls review_text(text).
    """
    kb = kb or knowledge.get_kb()
    safe, mapping = redact.redact_with_map(text)

    rule_f = (rules.check_terminology(text, kb.terms)
              + rules.check_expired_facts(text, kb.facts)
              + rules.check_readability(text, kb.get(rules.READABILITY_GUIDELINE)))

    ai_f: list[Finding] = []
    model = ""
    generate = llm or (_gemini_generate if os.getenv("GEMINI_API_KEY") else None)
    if use_ai and generate and text.strip():
        try:
            ai_f = _ai_findings(text, safe, mapping, kb, generate)
            model = _model_name() if llm is None else "injected-llm"
        except Exception as e:  # never crash the app because Gemini is down
            log.warning("AI review failed, returning rule findings only: %s", e)

    return ReviewResult(text=safe, findings=_merge(text, rule_f, ai_f),
                        redactions=len(mapping), model=model)
