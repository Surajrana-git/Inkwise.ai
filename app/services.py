"""Thin layer between the Streamlit pages and the engine.

Round 3 additions (Suraj): startup-once (seed + overrides), review cache keyed by text
hash, one Gemini call at a time, input limits, and wrappers for login, Fact Register,
Insights and rewording. Pages import this module only; they never import engine.* directly.
"""
import datetime as dt
import hashlib
import importlib
import importlib.util
import json
import sys
import threading
from collections import OrderedDict
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

KIT = ROOT / "data" / "brand_kit"
KIT_FILES = ["guidelines.json", "facts.json", "glossary.json"]

MAX_REVIEW_CHARS = 12_000       # about two pages; longer texts are refused with a message
MAX_IMAGE_BYTES = 5 * 1024 * 1024
REVIEW_CACHE_SIZE = 200

WORKFLOW_FUNCS = ["submit_for_approval", "list_submissions", "decide_submission",
                  "get_recent_activity", "get_dashboard_stats"]
R3_FUNCS = ["authenticate", "demo_accounts", "fact_register", "fact_owners", "can_renew", "renew_fact",
            "guideline_stats", "repeat_issues", "suggest_rewording", "accept_rewording", "global_audit", "health"]

_PARTS = {
    "review": ("AI review engine", "engine/review.py with review_text(text)", "Riyana, Steps 4 and 8"),
    "workflow": ("Workflow and approvals", "engine/workflow.py", "Suraj, Step 6"),
    "knowledge": ("Knowledge base", "data/brand_kit/guidelines.json, facts.json, glossary.json", "Pritha, Step 2"),
    "visual": ("Visual checks", "engine/visual.py with review_image(image_bytes, kb)", "Riyana, Round 3"),
}


class BackendNotConnected(Exception):
    def __init__(self, part: str, needs: str, owner: str):
        self.part, self.needs, self.owner = part, needs, owner
        super().__init__(f"{part} is not connected: {needs}")


class InputError(ValueError):
    """A readable message for the user (empty text, text too long, bad image)."""


# ---------------------------------------------------------------- startup once per process

_started = False
_start_lock = threading.Lock()
_gemini_lock = threading.Lock()


def ensure_started() -> None:
    """Create tables, seed demo data and apply stored overrides. Safe to call on every rerun."""
    global _started
    if _started:
        return
    with _start_lock:
        if _started:
            return
        try:
            from engine import bootstrap

            bootstrap.startup()
        except Exception:  # pages still work with whatever is available
            pass
        _started = True


def _module(part: str, modname: str, funcs: list[str]):
    name, needs, owner = _PARTS[part]
    try:
        spec = importlib.util.find_spec(modname)
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        raise BackendNotConnected(name, needs, owner)
    mod = importlib.import_module(modname)
    missing = [f for f in funcs if not hasattr(mod, f)]
    if missing:
        raise BackendNotConnected(name, f"{modname} is missing: {', '.join(missing)}", owner)
    return mod


def check(part: str) -> None:
    if part == "review":
        _module("review", "engine.review", ["review_text"])
    elif part == "workflow":
        _module("workflow", "engine.workflow", WORKFLOW_FUNCS)
    elif part == "visual":
        _module("visual", "engine.visual", ["review_image"])
    elif part == "knowledge":
        missing = [f for f in KIT_FILES if not (KIT / f).exists()]
        if missing:
            name, _, owner = _PARTS["knowledge"]
            raise BackendNotConnected(name, "data/brand_kit/" + ", ".join(missing), owner)


def backend_status() -> dict:
    out = {}
    for part in _PARTS:
        try:
            check(part)
            out[part] = True
        except BackendNotConnected:
            out[part] = False
    return out


def health() -> dict:
    ensure_started()
    out = {"db": False, "brand_kit": False, "gemini_key": False, "seeded": False}
    try:
        out.update(_wf().health())
    except Exception:
        pass
    out["visual_checks"] = backend_status().get("visual", False)
    return out


# ---------------------------------------------------------------- findings as plain dicts

def _plain(value):
    if isinstance(value, Enum):
        return _plain(value.value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def _clean_label(value, default: str) -> str:
    if value is None or value == "":
        return default
    text = str(_plain(value))
    return text.split(".")[-1].strip().lower() if text.startswith(("FindingStatus.", "Category.", "CheckedBy.")) else text.strip().lower()


def _to_dict(f) -> dict:
    if isinstance(f, dict):
        d = dict(f)
    elif hasattr(f, "model_dump"):
        d = f.model_dump(mode="json")
    elif hasattr(f, "dict"):
        d = f.dict()
    else:
        d = dict(vars(f))
    d = _plain(d)
    d["status"] = _clean_label(d.get("status"), "open")
    d["category"] = _clean_label(d.get("category"), "")
    d["checked_by"] = _clean_label(d.get("checked_by"), "rule")
    d["source_text"] = d.get("source_text") or ""
    d["source_id"] = d.get("source_id") or "UNVERIFIED"
    d["owner"] = d.get("owner") or d.get("fact_owner") or ""
    d["fact_owner"] = d.get("fact_owner") or ""
    d["freshness"] = d.get("freshness") or ""
    d["evidence"] = d.get("evidence") or ""
    d["evidence_verified"] = bool(d.get("evidence_verified", False))
    d["occurrences"] = [list(o) for o in (d.get("occurrences") or [])]
    d["why"] = d.get("why") or ""
    d["suggested_fix"] = d.get("suggested_fix") or ""
    d["span_text"] = d.get("span_text") or d.get("span") or ""
    try:
        d["confidence"] = float(d.get("confidence") or 0.0)
    except (TypeError, ValueError):
        d["confidence"] = 0.0
    return d


def _positions(text: str, findings: list[dict]) -> None:
    """Fill start/end for the first occurrence and `occurrences` for every one (if the engine did not)."""
    for d in findings:
        span = d.get("span_text") or ""
        if not d["occurrences"] and span:
            i, occ = text.find(span), []
            while i >= 0 and len(occ) < 50:
                occ.append([i, i + len(span)])
                i = text.find(span, i + max(len(span), 1))
            d["occurrences"] = occ
        if d["occurrences"]:
            d["start"], d["end"] = d["occurrences"][0]
        else:
            d["start"], d["end"] = None, None


# ---------------------------------------------------------------- review (text and image)

_cache: "OrderedDict[str, dict]" = OrderedDict()


def validate_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n")
    if not text.strip():
        raise InputError("Paste some text first.")
    if len(text) > MAX_REVIEW_CHARS:
        raise InputError(f"That text is {len(text):,} characters; the limit is {MAX_REVIEW_CHARS:,}. "
                         "Review it in two parts.")
    return text


def review_text_full(text: str, use_cache: bool = True) -> dict:
    ensure_started()
    text = validate_text(text)
    key = hashlib.sha256(text.encode()).hexdigest()
    if use_cache and key in _cache:
        hit = dict(_cache[key])
        hit["cached"] = True
        _cache.move_to_end(key)
        return hit
    mod = _module("review", "engine.review", ["review_text"])
    with _gemini_lock:  # free-tier Gemini: one call at a time per process
        result = mod.review_text(text)
    raw = getattr(result, "findings", None)
    if raw is None and isinstance(result, dict):
        raw = result.get("findings", [])
    if raw is None:
        raw = result
    ai_error = result.get("ai_error") if isinstance(result, dict) else getattr(result, "ai_error", None)
    model = result.get("model") if isinstance(result, dict) else getattr(result, "model", "")
    findings = [_to_dict(f) for f in raw]
    _positions(text, findings)
    findings.sort(key=lambda x: (x.get("start") is None, x.get("start") or 0))
    out = {"findings": findings, "ai_error": ai_error or None, "model": model or "", "cached": False}
    if not ai_error:  # do not cache a rules-only result caused by a Gemini outage
        _cache[key] = out
        while len(_cache) > REVIEW_CACHE_SIZE:
            _cache.popitem(last=False)
    return out


def review_text(text: str) -> list[dict]:
    return review_text_full(text)["findings"]


def review_image(image_bytes: bytes, filename: str = "") -> dict:
    """Visual checks (contrast, brand colours, logo). Raises InputError for bad uploads."""
    ensure_started()
    if not image_bytes:
        raise InputError("Choose an image first.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise InputError(f"That image is {len(image_bytes) / 1e6:.1f} MB; the limit is 5 MB.")
    if not (image_bytes.startswith(b"\x89PNG") or image_bytes.startswith(b"\xff\xd8") or image_bytes[:4] == b"RIFF"):
        raise InputError("That file is not a PNG or JPEG image.")
    mod = _module("visual", "engine.visual", ["review_image"])
    from engine import knowledge
    with _gemini_lock:
        result = mod.review_image(image_bytes, knowledge.get_kb())
    raw = getattr(result, "findings", None) or (result.get("findings", []) if isinstance(result, dict) else [])
    ai_error = result.get("ai_error") if isinstance(result, dict) else getattr(result, "ai_error", None)
    return {"findings": [_to_dict(f) for f in raw], "ai_error": ai_error or None}


# ---------------------------------------------------------------- workflow

def _wf():
    ensure_started()
    return _module("workflow", "engine.workflow", WORKFLOW_FUNCS)


def submit_for_approval(title: str, text: str, findings: list[dict], author: str) -> str:
    return _wf().submit_for_approval(title, text, findings, author)


def list_submissions(status: str | None = None) -> list[dict]:
    return [_plain(s) for s in _wf().list_submissions(status)]


def decide_submission(sub_id: str, decision: str, comment: str, user: str, role: str) -> None:
    return _wf().decide_submission(sub_id, decision, comment, user, role)


def get_recent_activity(limit: int = 5) -> list[dict]:
    return [_plain(a) for a in _wf().get_recent_activity(limit)]


def get_dashboard_stats(role: str) -> dict:
    return _plain(_wf().get_dashboard_stats(role))


def global_audit(limit: int = 200, action_prefix: str | None = None) -> list[dict]:
    return [_plain(a) for a in _wf().global_audit(limit, action_prefix)]


# ---------------------------------------------------------------- sign-in

def authenticate(username: str, password: str, role: str) -> dict | None:
    return _wf().authenticate(username, password, role)


def demo_accounts() -> list[dict]:
    """For the login screen: username, password, role, what the account can do."""
    try:
        return _wf().demo_accounts()
    except Exception:
        return []


# ---------------------------------------------------------------- fact register (Improvement 2)

def fact_register(owner: str | None = None, status: str | None = None) -> list[dict]:
    return [_plain(f) for f in _wf().fact_register(owner=owner or None, status=status or None)]


def fact_owners() -> list[str]:
    return _wf().fact_owners()


def can_renew(user: str, role: str, fact_owner: str) -> bool:
    return _wf().can_renew(user, role, fact_owner)


def renew_fact(fact_id: str, user: str, role: str, new_expires_on, note: str = "") -> dict:
    return _plain(_wf().renew_fact(fact_id, user, role, new_expires_on, note))


# ---------------------------------------------------------------- insights (Improvement 3)

def guideline_stats(date_from=None, date_to=None, role: str | None = None) -> list[dict]:
    return [_plain(g) for g in _wf().guideline_stats(date_from, date_to, role or None)]


def repeat_issues(group_by: str = "category", date_from=None, date_to=None) -> list[dict]:
    return [_plain(r) for r in _wf().repeat_issues(group_by, date_from, date_to)]


def suggest_rewording(guideline_id: str) -> str:
    with _gemini_lock:
        return _wf().suggest_rewording(guideline_id)


def accept_rewording(guideline_id: str, text: str, user: str, role: str) -> None:
    return _wf().accept_rewording(guideline_id, text, user, role)


def clarity_thresholds() -> dict:
    wf = _wf()
    return {"min_shown": wf.UNCLEAR_MIN_SHOWN, "override_rate": wf.UNCLEAR_OVERRIDE_RATE,
            "reject_rate": wf.UNCLEAR_REJECT_RATE, "repeat_min": wf.REPEAT_MIN_COUNT}


# ---------------------------------------------------------------- knowledge base page

def _records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    return data


def _join(value) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value or "")


def get_knowledge_base() -> dict:
    check("knowledge")
    ensure_started()
    today = dt.date.today()
    g = _records(KIT / "guidelines.json")
    f = _records(KIT / "facts.json")
    t = _records(KIT / "glossary.json")

    # accepted rewordings and renewed expiry dates come from the live knowledge base
    live_rules, live_exp = {}, {}
    try:
        from engine import knowledge
        kb = knowledge.get_kb()
        live_rules = {x.id: x.rule for x in kb.guidelines}
        live_exp = {x.id: (x.expires_on.isoformat() if x.expires_on else None) for x in kb.facts}
    except Exception:
        pass

    guidelines = [{"id": x.get("id"),
                   "title": x.get("title", ""),
                   "text": live_rules.get(x.get("id"), x.get("rule", "")),
                   "original_text": x.get("rule", ""),
                   "category": x.get("category", ""),
                   "examples_good": x.get("examples_good", []),
                   "examples_bad": x.get("examples_bad", [])} for x in g]

    facts = []
    for x in f:
        exp = live_exp.get(x.get("id"), x.get("expires_on"))
        try:
            expired = bool(exp) and dt.date.fromisoformat(str(exp)[:10]) < today
        except ValueError:
            expired = False
        facts.append({"id": x.get("id"),
                      "text": x.get("statement", ""),
                      "source": x.get("source", ""),
                      "owner": x.get("owner", ""),
                      "expires": exp, "expired": expired})

    glossary = [{"id": x.get("id"),
                 "avoid": _join(x.get("banned_variants")),
                 "use": x.get("approved", ""),
                 "note": x.get("note", "")} for x in t]

    return {"guidelines": guidelines, "facts": facts, "glossary": glossary}
