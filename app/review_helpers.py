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