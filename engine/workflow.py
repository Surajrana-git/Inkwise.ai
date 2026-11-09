"""Review and approval workflow with versions and an audit log (SQLite).
Owner: Suraj (Step 6).

Roles
-----
creator   submits content, edits it, accepts/rejects findings on own content
reviewer  reviews findings, can approve or request changes
manager   approves or requests changes
admin     everything, sees all items

Content status
--------------
draft -> in_review -> approved
                   -> changes_requested -> (new version) -> in_review

Every state change is written to audit_log. Finding decisions are kept in their
own table: they feed confidence calibration and Guideline Clarity Insights (R3).
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from engine.schemas import Finding, FindingStatus, ReviewResult

ROLES = ("creator", "manager", "reviewer", "admin")
APPROVER_ROLES = ("manager", "reviewer", "admin")
STATUSES = ("draft", "in_review", "approved", "changes_requested")

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "inkwise.sqlite3"


class WorkflowError(ValueError):
    """Raised for invalid actions (wrong role, unknown item, bad state)."""


def _db_path() -> str:
    return os.getenv("INKWISE_DB", str(DEFAULT_DB))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_ready: set[str] = set()  # DB paths whose tables exist in this process


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if path not in _ready:  # tables are created on first use, so the UI never needs init_db()
        _create_tables(con)
        _ready.add(path)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    current_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL REFERENCES content(id),
    version INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (content_id, version)
);
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL REFERENCES content(id),
    version INTEGER NOT NULL,
    finding_id TEXT NOT NULL,
    category TEXT NOT NULL,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    data TEXT NOT NULL,
    UNIQUE (content_id, version, finding_id)
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL REFERENCES content(id),
    version INTEGER NOT NULL,
    finding_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    user TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER REFERENCES content(id),
    user TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    at TEXT NOT NULL
);
"""


def _create_tables(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    # columns added after Step 6: older local databases get them here
    have = {r[1] for r in con.execute("PRAGMA table_info(content)")}
    for col in ("decided_by", "decided_at", "decision_comment"):
        if col not in have:
            con.execute(f"ALTER TABLE content ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
    con.commit()


def init_db() -> None:
    _ready.discard(_db_path())
    with _conn():
        pass


def _log(con: sqlite3.Connection, content_id: Optional[int], user: str, action: str, detail: str = "") -> None:
    con.execute("INSERT INTO audit_log (content_id, user, action, detail, at) VALUES (?,?,?,?,?)",
                (content_id, user, action, detail, _now()))


def _get_content(con: sqlite3.Connection, content_id: int) -> sqlite3.Row:
    row = con.execute("SELECT * FROM content WHERE id = ?", (content_id,)).fetchone()
    if row is None:
        raise WorkflowError(f"Content {content_id} not found")
    return row


def _check_role(role: str) -> str:
    """Validate a role (any capitalisation, e.g. the UI's "Manager") and return it lower-case."""
    r = (role or "").strip().lower()
    if r not in ROLES:
        raise WorkflowError(f"Unknown role '{role}'")
    return r


# ---------------------------------------------------------------- creator actions

def submit_content(author: str, title: str, text: str) -> int:
    """Save a new draft (version 1) and return its content_id."""
    if not text.strip():
        raise WorkflowError("Content is empty")
    now = _now()
    with _conn() as con:
        cur = con.execute("INSERT INTO content (title, author, created_at, updated_at) VALUES (?,?,?,?)",
                          (title.strip() or "Untitled", author, now, now))
        cid = cur.lastrowid
        con.execute("INSERT INTO versions (content_id, version, text, created_by, created_at) VALUES (?,?,?,?,?)",
                    (cid, 1, text, author, now))
        _log(con, cid, author, "created", f"v1 · {title.strip() or 'Untitled'}")
    return cid


def add_version(content_id: int, text: str, user: str, note: str = "") -> int:
    """Save edited text as a new version. Returns the new version number."""
    if not text.strip():
        raise WorkflowError("Content is empty")
    with _conn() as con:
        row = _get_content(con, content_id)
        if row["status"] == "approved":
            raise WorkflowError("Approved content is locked; submit new content instead")
        v = row["current_version"] + 1
        con.execute("INSERT INTO versions (content_id, version, text, created_by, created_at) VALUES (?,?,?,?,?)",
                    (content_id, v, text, user, _now()))
        con.execute("UPDATE content SET current_version = ?, status = 'draft', updated_at = ? WHERE id = ?",
                    (v, _now(), content_id))
        _log(con, content_id, user, "new_version", f"v{v}" + (f" · {note}" if note else ""))
    return v


def save_review(content_id: int, result: ReviewResult, user: str = "inkwise-ai") -> None:
    """Store findings for the current version and move the item to in_review."""
    with _conn() as con:
        row = _get_content(con, content_id)
        v = row["current_version"]
        con.execute("DELETE FROM findings WHERE content_id = ? AND version = ?", (content_id, v))
        for f in result.findings:
            con.execute(
                "INSERT INTO findings (content_id, version, finding_id, category, source_id, status, data) "
                "VALUES (?,?,?,?,?,?,?)",
                (content_id, v, f.id, f.category.value, f.source_id, f.status.value, f.model_dump_json()))
        con.execute("UPDATE content SET status = 'in_review', updated_at = ? WHERE id = ?", (_now(), content_id))
        unverified = sum(1 for f in result.findings if not f.is_verified)
        _log(con, content_id, user, "reviewed",
             f"v{v} · {len(result.findings)} findings ({unverified} unverified)"
             + (f" · model {result.model}" if result.model else ""))


def decide_finding(content_id: int, finding_id: str, status: FindingStatus,
                   user: str, note: str = "") -> None:
    """Record accept / edit / reject on one finding (logged for Clarity Insights)."""
    if status == FindingStatus.OPEN:
        raise WorkflowError("A decision must be accepted, edited or rejected")
    with _conn() as con:
        row = _get_content(con, content_id)
        v = row["current_version"]
        f = con.execute("SELECT * FROM findings WHERE content_id = ? AND version = ? AND finding_id = ?",
                        (content_id, v, finding_id)).fetchone()
        if f is None:
            raise WorkflowError(f"Finding {finding_id} not found on v{v}")
        con.execute("UPDATE findings SET status = ? WHERE id = ?", (status.value, f["id"]))
        con.execute("INSERT INTO decisions (content_id, version, finding_id, source_id, category, status, user, note, at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (content_id, v, finding_id, f["source_id"], f["category"], status.value, user, note, _now()))
        _log(con, content_id, user, f"finding_{status.value}",
             f"{finding_id} ({f['source_id']})" + (f" · {note}" if note else ""))


# ---------------------------------------------------------------- approver actions

def approve(content_id: int, user: str, role: str, approved: bool, comment: str = "") -> None:
    """Approve, or request changes. Only manager / reviewer / admin may do this."""
    role = _check_role(role)
    if role not in APPROVER_ROLES:
        raise WorkflowError(f"Role '{role}' cannot approve content")
    with _conn() as con:
        row = _get_content(con, content_id)
        if row["status"] != "in_review":
            raise WorkflowError(f"Only items in review can be decided (status is {row['status']})")
        if role != "admin" and row["author"] == user:
            raise WorkflowError("You cannot approve your own content")
        new = "approved" if approved else "changes_requested"
        if approved and not comment:
            open_n = con.execute("SELECT COUNT(*) FROM findings WHERE content_id = ? AND version = ? AND status = 'open'",
                                 (content_id, row["current_version"])).fetchone()[0]
            if open_n:
                raise WorkflowError(f"{open_n} findings are still open; resolve them or add a comment explaining why")
        now = _now()
        con.execute("UPDATE content SET status = ?, updated_at = ?, decided_by = ?, decided_at = ?, "
                    "decision_comment = ? WHERE id = ?", (new, now, user, now, comment, content_id))
        _log(con, content_id, user, new, f"v{row['current_version']} · {role}" + (f" · {comment}" if comment else ""))


# ---------------------------------------------------------------- reads

def get_content(content_id: int) -> dict:
    """Item with its current text and current-version findings."""
    with _conn() as con:
        row = _get_content(con, content_id)
        v = con.execute("SELECT text FROM versions WHERE content_id = ? AND version = ?",
                        (content_id, row["current_version"])).fetchone()
        fs = con.execute("SELECT data, status FROM findings WHERE content_id = ? AND version = ? ORDER BY id",
                         (content_id, row["current_version"])).fetchall()
    findings = []
    for r in fs:
        f = Finding.model_validate_json(r["data"])
        findings.append(f.model_copy(update={"status": FindingStatus(r["status"])}))
    return {**dict(row), "text": v["text"], "findings": findings}


def queue(role: str, user: Optional[str] = None) -> list[dict]:
    """Items waiting for this role. Creators see their own drafts and returned items."""
    role = _check_role(role)
    with _conn() as con:
        if role == "admin":
            rows = con.execute("SELECT * FROM content ORDER BY updated_at DESC").fetchall()
        elif role in ("manager", "reviewer"):
            rows = con.execute("SELECT * FROM content WHERE status = 'in_review' ORDER BY updated_at").fetchall()
        else:
            rows = con.execute("SELECT * FROM content WHERE author = ? AND status IN ('draft','changes_requested','in_review') "
                               "ORDER BY updated_at DESC", (user or "",)).fetchall()
    return [dict(r) for r in rows]


def history(content_id: int) -> list[dict]:
    """Versions + audit-log entries, oldest first."""
    with _conn() as con:
        _get_content(con, content_id)
        vers = con.execute("SELECT version, text, created_by AS user, created_at AS at FROM versions "
                           "WHERE content_id = ?", (content_id,)).fetchall()
        logs = con.execute("SELECT user, action, detail, at FROM audit_log WHERE content_id = ?",
                           (content_id,)).fetchall()
    items = [{"kind": "version", **dict(v)} for v in vers] + [{"kind": "event", **dict(l)} for l in logs]
    return sorted(items, key=lambda x: (x["at"], 0 if x["kind"] == "version" else 1))


def decision_stats() -> list[dict]:
    """Per source: how often reviewers accepted vs rejected its findings.
    A high reject/edit rate suggests the guideline is unclear (input for R3 Clarity Insights)."""
    with _conn() as con:
        rows = con.execute(
            "SELECT source_id, category, "
            "SUM(status='accepted') AS accepted, SUM(status='edited') AS edited, "
            "SUM(status='rejected') AS rejected, COUNT(*) AS total "
            "FROM decisions GROUP BY source_id, category ORDER BY total DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["override_rate"] = round((d["rejected"] + d["edited"]) / d["total"], 3) if d["total"] else 0.0
        out.append(d)
    return out


def export_audit_log() -> str:
    """Whole audit log as JSON lines (for admins / submission evidence)."""
    with _conn() as con:
        rows = con.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    return "\n".join(json.dumps(dict(r)) for r in rows)


# ---------------------------------------------------------------- UI adapters (Aashi's app/services.py)
# The Streamlit pages work with "submissions": one piece of content sent for approval
# together with the findings the creator already accepted / edited / rejected.

_UI_STATUS = {"in_review": "pending", "approved": "approved", "changes_requested": "rejected", "draft": "draft"}


def _finding_from_ui(d: dict) -> Finding:
    data = {k: d[k] for k in Finding.model_fields if k in d}
    data["status"] = d.get("status") or "open"
    return Finding.model_validate(data)


def submit_for_approval(title: str, text: str, findings: list[dict], author: str) -> str:
    """Save content + its findings (with the creator's decisions) and send it for approval."""
    cid = submit_content(author, title, text)
    parsed = [_finding_from_ui(f) for f in findings]
    save_review(cid, ReviewResult(text=text, findings=parsed))
    for f in parsed:  # record creator decisions so they count for Clarity Insights
        if f.status != FindingStatus.OPEN:
            decide_finding(cid, f.id, f.status, author)
    return str(cid)


def _submission(row: sqlite3.Row) -> dict:
    item = get_content(row["id"])
    return {
        "id": str(row["id"]), "title": row["title"], "author": row["author"],
        "status": _UI_STATUS.get(row["status"], row["status"]), "version": row["current_version"],
        "text": item["text"], "findings": [f.model_dump(mode="json") for f in item["findings"]],
        "submitted_at": row["created_at"][:16].replace("T", " "),
        "decided_by": row["decided_by"], "decided_at": row["decided_at"][:16].replace("T", " "),
        "comment": row["decision_comment"],
    }


def list_submissions(status: Optional[str] = None) -> list[dict]:
    """All submissions, newest first. status: pending | approved | rejected | None for all."""
    with _conn() as con:
        rows = con.execute("SELECT * FROM content WHERE status != 'draft' ORDER BY updated_at DESC").fetchall()
    subs = [_submission(r) for r in rows]
    return [s for s in subs if status is None or s["status"] == status]


def decide_submission(sub_id: str, decision: str, comment: str, user: str, role: str) -> None:
    """decision: 'approved' or 'rejected'. Raises WorkflowError with a readable message."""
    if decision not in ("approved", "rejected"):
        raise WorkflowError(f"Unknown decision '{decision}'")
    approve(int(sub_id), user, role, approved=(decision == "approved"), comment=comment)


_ACTIVITY = {
    "created": ("created", "open"), "reviewed": ("ran a review on", "open"),
    "new_version": ("saved a new version of", "open"),
    "finding_accepted": ("accepted a finding in", "ok"), "finding_edited": ("edited a fix in", "ok"),
    "finding_rejected": ("rejected a finding in", "bad"),
    "approved": ("approved", "ok"), "changes_requested": ("requested changes on", "bad"),
}


def get_recent_activity(limit: int = 5) -> list[dict]:
    """Latest audit-log events for the dashboard: when, who, what, status (open | ok | bad)."""
    with _conn() as con:
        rows = con.execute("SELECT a.user, a.action, a.at, c.title FROM audit_log a "
                           "LEFT JOIN content c ON c.id = a.content_id ORDER BY a.id DESC LIMIT ?",
                           (limit,)).fetchall()
    out = []
    for r in rows:
        verb, status = _ACTIVITY.get(r["action"], (r["action"].replace("_", " "), "open"))
        out.append({"when": r["at"][11:16], "who": r["user"], "what": f"{verb} “{r['title'] or ''}”",
                    "status": status})
    return out


def get_dashboard_stats(role: str) -> dict:
    """Numbers for the home screen."""
    _check_role(role)
    today = datetime.now(timezone.utc).date().isoformat()
    with _conn() as con:
        reviews = con.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'reviewed' AND at LIKE ?",
                              (today + "%",)).fetchone()[0]
        open_f = con.execute("SELECT COUNT(*) FROM findings f JOIN content c ON c.id = f.content_id "
                             "AND f.version = c.current_version WHERE f.status = 'open' "
                             "AND c.status != 'approved'").fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM content WHERE status = 'in_review'").fetchone()[0]
    try:
        from engine import knowledge
        expired = sum(f.is_expired() for f in knowledge.get_kb().facts)
    except Exception:
        expired = "–"
    return {"reviews_today": reviews, "open_findings": open_f, "pending_approvals": pending,
            "expired_facts": expired}


def authenticate(username: str, password: str, role: str) -> Optional[dict]:
    """Demo sign-in: any username with the shared demo password (INKWISE_DEMO_PASSWORD)."""
    import hmac

    _check_role(role)
    expected = os.getenv("INKWISE_DEMO_PASSWORD", "inkwise-demo")
    if username.strip() and hmac.compare_digest(password.encode(), expected.encode()):
        with _conn() as con:
            _log(con, None, username.strip(), "signed_in", role)
        return {"user": username.strip(), "role": role}
    return None
