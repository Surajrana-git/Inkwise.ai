import datetime as dt
import importlib
import importlib.util
import json
import sys
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

KIT = ROOT / "data" / "brand_kit"
KIT_FILES = ["guidelines.json", "facts.json", "glossary.json"]

WORKFLOW_FUNCS = ["submit_for_approval", "list_submissions", "decide_submission",
                  "get_recent_activity", "get_dashboard_stats"]

_PARTS = {
    "review": ("AI review engine", "engine/review.py with review_text(text)", "Riyana, Steps 4 and 8"),
    "workflow": ("Workflow and approvals", "engine/workflow.py", "Suraj, Step 6"),
    "knowledge": ("Knowledge base", "data/brand_kit/guidelines.json, facts.json, glossary.json", "Pritha, Step 2"),
}


class BackendNotConnected(Exception):
    def __init__(self, part: str, needs: str, owner: str):
        self.part, self.needs, self.owner = part, needs, owner
        super().__init__(f"{part} is not connected: {needs}")


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


def _plain(value):
    if isinstance(value, Enum):
        return _plain(value.value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
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
    d["owner"] = d.get("owner") or ""
    d["why"] = d.get("why") or ""
    d["suggested_fix"] = d.get("suggested_fix") or ""
    d["span_text"] = d.get("span_text") or d.get("span") or ""
    try:
        d["confidence"] = float(d.get("confidence") or 0.0)
    except (TypeError, ValueError):
        d["confidence"] = 0.0
    return d


def review_text_full(text: str) -> dict:
    mod = _module("review", "engine.review", ["review_text"])
    result = mod.review_text(text)
    raw = getattr(result, "findings", None)
    if raw is None and isinstance(result, dict):
        raw = result.get("findings", [])
    if raw is None:
        raw = result
    if isinstance(result, dict):
        ai_error = result.get("ai_error")
    else:
        ai_error = getattr(result, "ai_error", None)
    findings = [_to_dict(f) for f in raw]
    findings.sort(key=lambda x: (x.get("start") is None, x.get("start") or 0))
    return {"findings": findings, "ai_error": ai_error or None}


def review_text(text: str) -> list[dict]:
    return review_text_full(text)["findings"]


def _wf():
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
    today = dt.date.today()
    g = _records(KIT / "guidelines.json")
    f = _records(KIT / "facts.json")
    t = _records(KIT / "glossary.json")

    guidelines = [{"id": x.get("id"),
                   "title": x.get("title", ""),
                   "text": x.get("rule", ""),
                   "category": x.get("category", ""),
                   "examples_good": x.get("examples_good", []),
                   "examples_bad": x.get("examples_bad", [])} for x in g]

    facts = []
    for x in f:
        exp = x.get("expires_on")
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


def authenticate(username: str, password: str, role: str) -> dict | None:
    mod = _module("workflow", "engine.workflow", ["authenticate"])
    return mod.authenticate(username, password, role)