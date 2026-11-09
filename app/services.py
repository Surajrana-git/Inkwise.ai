"""Bridge between the Streamlit UI and the backend. NO mock data lives here.
If a backend part is missing, the function raises BackendNotConnected and the page
shows which file is needed."""
import datetime as dt
import importlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))          # lets us import `engine`

KIT = ROOT / "data" / "brand_kit"
KIT_FILES = ["guidelines.json", "facts.json", "glossary.json"]

WORKFLOW_FUNCS = ["submit_for_approval", "list_submissions", "decide_submission",
                  "get_recent_activity", "get_dashboard_stats"]

# part -> (display name, what is needed, owner)
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
    """Raise BackendNotConnected if `part` ('review' | 'workflow' | 'knowledge') is not ready."""
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


def _to_dict(f) -> dict:
    """A Finding may come back as a dict, pydantic model or dataclass."""
    if isinstance(f, dict):
        d = dict(f)
    elif hasattr(f, "model_dump"):
        d = f.model_dump()
    elif hasattr(f, "dict"):
        d = f.dict()
    else:
        d = dict(vars(f))
    d.setdefault("status", "open")
    d.setdefault("source_text", "")
    d.setdefault("why", "")
    d.setdefault("suggested_fix", "")
    d.setdefault("confidence", 0.0)
    d.setdefault("checked_by", "ai")
    return d


# ---------------------------------------------------------------- REVIEW (engine/review.py)
def review_text(text: str) -> list[dict]:
    mod = _module("review", "engine.review", ["review_text"])
    result = mod.review_text(text)
    # engine returns a ReviewResult; fall back to a plain list if it ever does
    return [_to_dict(f) for f in getattr(result, "findings", result)]


# ---------------------------------------------------------------- WORKFLOW (engine/workflow.py)
def _wf():
    return _module("workflow", "engine.workflow", WORKFLOW_FUNCS)


def submit_for_approval(title: str, text: str, findings: list[dict], author: str) -> str:
    return _wf().submit_for_approval(title, text, findings, author)


def list_submissions(status: str | None = None) -> list[dict]:
    return _wf().list_submissions(status)


def decide_submission(sub_id: str, decision: str, comment: str, user: str, role: str) -> None:
    return _wf().decide_submission(sub_id, decision, comment, user, role)


def get_recent_activity(limit: int = 5) -> list[dict]:
    return _wf().get_recent_activity(limit)


def get_dashboard_stats(role: str) -> dict:
    return _wf().get_dashboard_stats(role)


# ---------------------------------------------------------------- KNOWLEDGE BASE (data/brand_kit)
def _records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):                      # {"guidelines": [...]} style
        data = next((v for v in data.values() if isinstance(v, list)), [])
    return data


def _join(value) -> str:
    """banned_variants is a list; the UI wants one string."""
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
        exp = x.get("expires_on")          # may be null = never expires
        expired = bool(exp) and dt.date.fromisoformat(str(exp)[:10]) < today
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
    """Returns {"user": ..., "role": ...} on success, or None for wrong details."""
    mod = _module("workflow", "engine.workflow", ["authenticate"])
    return mod.authenticate(username, password, role)