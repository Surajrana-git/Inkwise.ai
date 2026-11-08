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


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
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


def init_db() -> None:
    with _conn() as con:
        con.executescript(SCHEMA)


def _log(con: sqlite3.Connection, content_id: Optional[int], user: str, action: str, detail: str = "") -> None:
    con.execute("INSERT INTO audit_log (content_id, user, action, detail, at) VALUES (?,?,?,?,?)",
                (content_id, user, action, detail, _now()))


def _get_content(con: sqlite3.Connection, content_id: int) -> sqlite3.Row:
    row = con.execute("SELECT * FROM content WHERE id = ?", (content_id,)).fetchone()
    if row is None:
        raise WorkflowError(f"Content {content_id} not found")
    return row


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise WorkflowError(f"Unknown role '{role}'")


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
    _check_role(role)
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
        con.execute("UPDATE content SET status = ?, updated_at = ? WHERE id = ?", (new, _now(), content_id))
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
    _check_role(role)
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
