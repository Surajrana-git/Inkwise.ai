from __future__ import annotations

import html
import re
from datetime import date

EXPIRING_DAYS = 30

_STOP = set("a an the and or of to in on for with is are be by as at it this that we our you your "
            "from not has have can will was were its their into than then so but".split())



def _norm_occ(occ) -> list[tuple[int, int]]:
    """Accept [(s, e), ...] or [{"start": s, "end": e}, ...] from the backend."""
    out = []
    for o in occ or []:
        s, e = (o.get("start"), o.get("end")) if isinstance(o, dict) else (o[0], o[1])
        if s is not None and e is not None and e > s:
            out.append((int(s), int(e)))
    return out


def find_occurrences(text: str, span: str) -> list[tuple[int, int]]:
    """Every occurrence of span. Case-sensitive first (the glossary rule is case-sensitive,
    e.g. 'Lumora pay' vs approved 'Lumora Pay'), case-insensitive only if nothing matched."""
    if not span:
        return []
    hits = [(m.start(), m.end()) for m in re.finditer(re.escape(span), text)]
    if not hits:
        hits = [(m.start(), m.end()) for m in re.finditer(re.escape(span), text, re.I)]
    return hits


def locate(findings: list[dict], text: str) -> list[dict]:
    """Set f["occurrences"] (all places), f["start"]/f["end"] (first place) and f["n"]."""
    for f in findings:
        if f.get("where") == "image":           # found in the creative, not in the copy
            f["occurrences"], f["start"], f["end"] = [], None, None
            continue
        occ = _norm_occ(f.get("occurrences")) or find_occurrences(text, f.get("span_text") or "")
        if not occ and f.get("start") is not None and f.get("end") is not None:
            occ = [(f["start"], f["end"])]
        f["occurrences"] = occ
        f["start"], f["end"] = occ[0] if occ else (None, None)
    findings.sort(key=lambda x: (x["start"] is None, x["start"] or 0))
    for n, f in enumerate(findings, 1):
        f["n"] = n
    return findings


def highlight_items(findings: list[dict]) -> list[dict]:
    """One pseudo-finding per occurrence, to pass to theme.highlight_html()."""
    seen, items = set(), []
    for f in findings:
        for s, e in f.get("occurrences") or []:
            if (s, e) in seen:
                continue
            seen.add((s, e))
            items.append({**f, "start": s, "end": e})
    return sorted(items, key=lambda x: x["start"])



def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower())
            if t not in _STOP and (len(t) >= 4 or t.isdigit())}


def evidence_terms(f: dict) -> list[str]:
    """Phrases to highlight inside f["source_text"].

    Uses f["evidence"] if the backend provides it (str or list). Otherwise:
    terminology -> the quoted approved term; everything else -> words/numbers shared
    between the flagged span and the source quote."""
    ev = f.get("evidence")
    if ev:
        return [ev] if isinstance(ev, str) else [str(x) for x in ev if x]
    src, span = f.get("source_text") or "", f.get("span_text") or ""
    terms: set[str] = set()
    if str(f.get("source_id", "")).startswith("T"):
        terms.update(re.findall(r"'([^']+)'", src))
    terms |= _tokens(span) & _tokens(src)
    return sorted(terms, key=len, reverse=True)


def evidence_html(source_text: str, terms: list[str]) -> str:
    safe = html.escape(source_text)
    terms = [t for t in terms if t]
    if terms:
        alts = "|".join(re.escape(html.escape(t)) for t in terms)
        pat = re.compile(rf"(?<!\w)(?:{alts})(?!\w)", re.I)
        safe = pat.sub(lambda m: f'<mark style="background:#99f6e4;color:#111;padding:0 2px;'
                                 f'border-radius:3px;font-weight:600">{m.group(0)}</mark>', safe)
    return safe


def quote_html(source_text: str, source_id: str, owner: str, terms: list[str]) -> str:
    owner_part = f" · owner: {html.escape(owner)}" if owner else ""
    return ('<div style="border-left:3px solid #0f9d8a;background:rgba(15,157,138,.08);'
            'padding:8px 12px;border-radius:6px;margin:6px 0">'
            f'<div style="font-size:12px;opacity:.7">{html.escape(source_id)}{owner_part}</div>'
            f'{evidence_html(source_text, terms)}</div>')



def expiry_state(f: dict, fact: dict | None = None, today: date | None = None):
    """Return ("expired" | "expiring" | None, days_until_expiry).

    fact is the entry from services.get_knowledge_base()["facts"] (has "expires").
    Falls back to the date in the rule's source_text: '(expired 2026-01-01; owner: ...)'."""
    today = today or date.today()
    if not str(f.get("source_id", "")).startswith("F"):
        return None, None
    days = None
    exp = (fact or {}).get("expires")
    if exp:
        try:
            days = (date.fromisoformat(str(exp)[:10]) - today).days
        except ValueError:
            pass
    if days is None:
        m = re.search(r"expired (\d{4}-\d{2}-\d{2})", f.get("source_text") or "")
        if m:
            days = (date.fromisoformat(m.group(1)) - today).days
    if days is None:
        return ("expired", None) if f.get("category") == "outdated_fact" else (None, None)
    if days < 0:
        return "expired", days
    if days <= EXPIRING_DAYS:
        return "expiring", days
    return None, days


def badge_html(state: str | None, days: int | None) -> str:
    if state == "expired":
        label = "EXPIRED" + (f" {abs(days)}d ago" if days is not None else "")
        return (f'<span style="background:#fee2e2;color:#b91c1c;padding:2px 8px;border-radius:10px;'
                f'font-size:12px;font-weight:700">{label}</span>')
    if state == "expiring":
        label = "EXPIRES TODAY" if days == 0 else f"EXPIRES IN {days}d"
        return (f'<span style="background:#ffedd5;color:#c2410c;padding:2px 8px;border-radius:10px;'
                f'font-size:12px;font-weight:700">{label}</span>')
    return ""

# ---------------------------------------------------------------- live revision after each decision
_REMOVE = re.compile(r"^\s*remove (this|the) ", re.I)
_INSTRUCTION = re.compile(r"^\s*(rewrite|split|rephrase|shorten|simplify|ask|check|review) (this|the|it)\b", re.I)


def fix_action(f: dict) -> tuple[str, str]:
    """What a decision does to the text: ("replace", new) / ("remove", "") / ("keep", "") / ("manual", "") / ("open", "")."""
    st_, fix = f.get("status"), (f.get("suggested_fix") or "").strip()
    if st_ == "open":
        return "open", ""
    if st_ == "rejected":
        return "keep", ""
    if st_ == "edited":
        return ("remove", "") if not fix else ("replace", fix)
    if _REMOVE.match(fix):
        return "remove", ""
    if not fix or _INSTRUCTION.match(fix):
        return "manual", ""          # advice, not wording: the writer still has to rewrite it
    return "replace", fix


def revision(text: str, findings: list[dict]) -> tuple[list[dict], str, list[int]]:
    """Apply every decision to the draft.

    Returns (segments, clean_text, manual_ns). Segments are {"kind", "text", "n", "category"} with kind in
    plain / open / kept / removed / added / manual. An outer change wins over a finding inside it
    (e.g. removing a sentence also removes the brand-name fix inside it); if the outer one is rejected,
    the inner one still applies."""
    spans = []
    for f in findings:
        for s, e in f.get("occurrences") or []:
            spans.append((s, e, f))
    spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    chosen, end_at = [], -1
    applied = [(s, e) for s, e, f in spans if fix_action(f)[0] in ("replace", "remove")]
    for s, e, f in spans:
        act = fix_action(f)[0]
        if s < end_at:
            continue
        # a kept/open outer span should not hide an applied inner change
        if act not in ("replace", "remove") and any(s <= a and b <= e and (a, b) != (s, e) for a, b in applied):
            continue
        chosen.append((s, e, f))
        end_at = e
    segs, clean, pos, manual = [], [], 0, []
    for s, e, f in chosen:
        if s > pos:
            segs.append({"kind": "plain", "text": text[pos:s]}); clean.append(text[pos:s])
        act, new = fix_action(f)
        orig, meta = text[s:e], {"n": f.get("n"), "category": str(f.get("category", "")).lower()}
        if act == "replace":
            nxt = text[e:].lstrip(" \t")[:1]
            if new[-1:] in ".!" and nxt and (nxt.islower() or nxt in ".,;:!?"):
                new = new[:-1]   # the sentence carries on after the span: drop the fix's own full stop
            segs += [{"kind": "removed", "text": orig, **meta}, {"kind": "added", "text": new, **meta}]
            clean.append(new)
        elif act == "remove":
            segs.append({"kind": "removed", "text": orig, **meta})
        else:
            segs.append({"kind": {"keep": "kept"}.get(act, act), "text": orig, **meta}); clean.append(orig)
            if act == "manual" and f.get("n") not in manual:
                manual.append(f.get("n"))
        pos = e
    if pos < len(text):
        segs.append({"kind": "plain", "text": text[pos:]}); clean.append(text[pos:])
    out = "".join(clean)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([.,!?;:])", r"\1", out)
    out = re.sub(r"([.!?])\1+", r"\1", out)
    out = re.sub(r"(^|\n)[ \t]*[.,;:]\s*", r"\1", out)
    return segs, out.strip(), manual
