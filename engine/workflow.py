"""Review and approval workflow with versions and an audit log (SQLite).
Owner: Suraj (Step 6, Round 3 lane: login, persistence, fact register, insights).

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

Round 3 additions
-----------------
users          demo accounts (username, password hash, role, team) shown on the login screen
fact_state     renewed expiry dates that override data/brand_kit/facts.json
rewordings     suggested / accepted clearer wording per guideline
meta           seeded_at and other small flags
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

from engine.schemas import Finding, FindingStatus, ReviewResult

ROLES = ("creator", "manager", "reviewer", "admin")
APPROVER_ROLES = ("manager", "reviewer", "admin")
STATUSES = ("draft", "in_review", "approved", "changes_requested")
OPEN_STATUSES = ("draft", "in_review", "changes_requested")

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "inkwise.sqlite3"

# Fact freshness (Improvement 2)
EXPIRING_SOON_DAYS = 30

# Guideline clarity thresholds (Improvement 3). Documented in docs/clarity_thresholds.md.
UNCLEAR_MIN_SHOWN = 5          # a guideline needs at least this many findings in range
UNCLEAR_OVERRIDE_RATE = 0.40   # creator edited the suggested fix
UNCLEAR_REJECT_RATE = 0.30     # creator or manager rejected the finding
REPEAT_MIN_COUNT = 3           # same category from the same creator this many times = repeat issue

# Demo accounts (Round 3). Passwords are intentionally shown in the app: demo only, no real users.
DEMO_PASSWORD = os.getenv("INKWISE_DEMO_PASSWORD", "demo123")
DEMO_USERS = (
    # username, role, team (owner name in facts.json that this user may renew), display name
    ("asha", "creator", "Comms team", "Asha (Creator)"),
    ("meera", "manager", "Product marketing", "Meera (Manager)"),
    ("ravi", "admin", "", "Ravi (Admin)"),
)


class WorkflowError(ValueError):
    """Raised for invalid actions (wrong role, unknown item, bad state)."""


def _db_path() -> str:
    return os.getenv("INKWISE_DB", str(DEFAULT_DB))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> date:
    return datetime.now(timezone.utc).date()


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
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    team TEXT NOT NULL DEFAULT '',
    display TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS fact_state (
    fact_id TEXT PRIMARY KEY,
    expires_on TEXT NOT NULL,
    renewed_by TEXT NOT NULL,
    renewed_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS rewordings (
    guideline_id TEXT PRIMARY KEY,
    suggested TEXT NOT NULL DEFAULT '',
    suggested_at TEXT NOT NULL DEFAULT '',
    accepted TEXT NOT NULL DEFAULT '',
    accepted_by TEXT NOT NULL DEFAULT '',
    accepted_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
    _seed_users(con)


def init_db() -> None:
    _ready.discard(_db_path())
    with _conn():
        pass


def _log(con: sqlite3.Connection, content_id: Optional[int], user: str, action: str, detail: str = "",
         at: Optional[str] = None) -> None:
    con.execute("INSERT INTO audit_log (content_id, user, action, detail, at) VALUES (?,?,?,?,?)",
                (content_id, user, action, detail, at or _now()))


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


def _meta_get(con: sqlite3.Connection, key: str, default: str = "") -> str:
    row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def _meta_set(con: sqlite3.Connection, key: str, value: str) -> None:
    con.execute("INSERT INTO meta (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value))


# ---------------------------------------------------------------- users and sign-in

def _hash(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _seed_users(con: sqlite3.Connection) -> None:
    for username, role, team, display in DEMO_USERS:
        con.execute("INSERT OR IGNORE INTO users (username, password_hash, role, team, display) VALUES (?,?,?,?,?)",
                    (username, _hash(DEMO_PASSWORD, username), role, team, display))
    con.commit()


def demo_accounts() -> list[dict]:
    """Accounts to print on the login screen: username, password, role, what they can do."""
    can = {
        "creator": "Review text and images, accept / edit / reject findings, send for approval",
        "manager": "Approve or reject with a comment, Insights, History, renew Product-marketing facts",
        "admin": "Everything, plus Fact Register renewals and accepting clearer guideline wording",
    }
    return [{"username": u, "password": DEMO_PASSWORD, "role": r.title(), "team": t, "can": can[r]}
            for u, r, t, _ in DEMO_USERS]


def get_user(username: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT username, role, team, display FROM users WHERE username = ?",
                          (username.strip().lower(),)).fetchone()
    return dict(row) if row else None


def authenticate(username: str, password: str, role: str) -> Optional[dict]:
    """Sign in with a demo account. The chosen role must match the account's role.

    Returns {"user", "role", "team"} or None. Never raises for bad input.
    """
    try:
        role = _check_role(role)
    except WorkflowError:
        return None
    name = (username or "").strip().lower()
    if not name or not password:
        return None
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE username = ?", (name,)).fetchone()
        if row is None:
            return None
        env_pw = os.getenv("INKWISE_DEMO_PASSWORD", "")
        ok = hmac.compare_digest(row["password_hash"], _hash(password, name)) or (
            bool(env_pw) and hmac.compare_digest(password, env_pw))
        if not ok:
            return None
        if row["role"] != role:
            return None
        _log(con, None, name, "signed_in", role)
    return {"user": name, "role": role.title(), "team": row["team"]}


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
    """Record accept / edit / reject on one finding (logged for Clarity Insights).

    Idempotent: repeating the same decision on the same finding changes nothing.
    """
    if status == FindingStatus.OPEN:
        raise WorkflowError("A decision must be accepted, edited or rejected")
    with _conn() as con:
        row = _get_content(con, content_id)
        v = row["current_version"]
        f = con.execute("SELECT * FROM findings WHERE content_id = ? AND version = ? AND finding_id = ?",
                        (content_id, v, finding_id)).fetchone()
        if f is None:
            raise WorkflowError(f"Finding {finding_id} not found on v{v}")
        if f["status"] == status.value:
            return  # same click twice
        con.execute("UPDATE findings SET status = ? WHERE id = ?", (status.value, f["id"]))
        con.execute("INSERT INTO decisions (content_id, version, finding_id, source_id, category, status, user, note, at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (content_id, v, finding_id, f["source_id"], f["category"], status.value, user, note, _now()))
        _log(con, content_id, user, f"finding_{status.value}",
             f"{finding_id} ({f['source_id']})" + (f" · {note}" if note else ""))


# ---------------------------------------------------------------- approver actions

def approve(content_id: int, user: str, role: str, approved: bool, comment: str = "") -> None:
    """Approve, or request changes. Only manager / reviewer / admin may do this.

    Idempotent: deciding an item the same way twice (double-click, refresh) is a no-op.
    """
    role = _check_role(role)
    if role not in APPROVER_ROLES:
        raise WorkflowError(f"Role '{role}' cannot approve content")
    new = "approved" if approved else "changes_requested"
    with _conn() as con:
        row = _get_content(con, content_id)
        if row["status"] == new and row["decided_by"] == user:
            return
        if row["status"] != "in_review":
            raise WorkflowError(f"Only items in review can be decided (status is {row['status']})")
        if role != "admin" and row["author"] == user:
            raise WorkflowError("You cannot approve your own content")
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
    """Per source: how often reviewers accepted vs rejected its findings (kept for the R2 tests)."""
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


def global_audit(limit: int = 200, action_prefix: Optional[str] = None) -> list[dict]:
    """Latest audit rows across all content (History page, Fact Register, Insights)."""
    with _conn() as con:
        if action_prefix:
            rows = con.execute("SELECT a.*, c.title FROM audit_log a LEFT JOIN content c ON c.id = a.content_id "
                               "WHERE a.action LIKE ? ORDER BY a.id DESC LIMIT ?", (action_prefix + "%", limit)).fetchall()
        else:
            rows = con.execute("SELECT a.*, c.title FROM audit_log a LEFT JOIN content c ON c.id = a.content_id "
                               "ORDER BY a.id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- fact freshness (Improvement 2)

def _kb():
    from engine import knowledge
    return knowledge.get_kb()


def _fact_overrides(con: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {r["fact_id"]: r for r in con.execute("SELECT * FROM fact_state")}


def apply_fact_overrides(facts: list) -> int:
    """Set renewed expiry dates on the in-memory Fact objects. Returns how many changed.

    bootstrap.startup() calls this after the knowledge base loads, so a renewal made
    earlier in the process (or before a reboot that kept the DB) is respected by the rules.
    """
    with _conn() as con:
        over = _fact_overrides(con)
    n = 0
    for f in facts:
        o = over.get(f.id)
        if o is not None:
            new = date.fromisoformat(o["expires_on"])
            if f.expires_on != new:
                f.expires_on = new
                n += 1
    return n


def fact_status(expires_on: Optional[date], today: Optional[date] = None) -> tuple[str, Optional[int]]:
    """('expired' | 'expiring_soon' | 'valid', days_left). Facts without an expiry are valid."""
    if expires_on is None:
        return "valid", None
    days = (expires_on - (today or _today())).days
    if days < 0:
        return "expired", days
    if days <= EXPIRING_SOON_DAYS:
        return "expiring_soon", days
    return "valid", days


_RISK_ORDER = {"expired": 0, "expiring_soon": 1, "valid": 2}


def fact_register(today: Optional[date] = None, owner: Optional[str] = None,
                  status: Optional[str] = None) -> list[dict]:
    """Every fact with its risk status, sorted expired -> expiring soon -> valid, then by date."""
    kb = _kb()
    apply_fact_overrides(kb.facts)
    with _conn() as con:
        over = _fact_overrides(con)
    out = []
    for f in kb.facts:
        st, days = fact_status(f.expires_on, today)
        if owner and f.owner != owner:
            continue
        if status and st != status:
            continue
        o = over.get(f.id)
        out.append({
            "id": f.id, "statement": f.statement, "source": f.source, "owner": f.owner,
            "expires_on": f.expires_on.isoformat() if f.expires_on else "",
            "status": st, "days_left": days,
            "renewed_by": o["renewed_by"] if o else "", "renewed_at": o["renewed_at"][:16].replace("T", " ") if o else "",
            "renew_note": o["note"] if o else "",
        })
    out.sort(key=lambda d: (_RISK_ORDER[d["status"]], d["expires_on"] or "9999", d["id"]))
    return out


def fact_owners() -> list[str]:
    return sorted({f.owner for f in _kb().facts if f.owner})


def can_renew(user: str, role: str, fact_owner: str) -> bool:
    """Admins renew anything; other users renew facts owned by their own team."""
    try:
        role = _check_role(role)
    except WorkflowError:
        return False
    if role == "admin":
        return True
    u = get_user(user or "")
    return bool(u and u["team"] and u["team"] == fact_owner)


def renew_fact(fact_id: str, user: str, role: str, new_expires_on, note: str = "") -> dict:
    """Owner or admin re-verifies a fact: new expiry date, audit row, then open drafts are re-checked.

    Returns {"fact_id", "expires_on", "rechecked": [content ids], "cleared": n findings removed}.
    """
    kb = _kb()
    fact = next((f for f in kb.facts if f.id == fact_id), None)
    if fact is None:
        raise WorkflowError(f"Fact {fact_id} not found")
    if not can_renew(user, role, fact.owner):
        raise WorkflowError(f"Only {fact.owner} or an admin can renew {fact_id}")
    if isinstance(new_expires_on, str):
        try:
            new_expires_on = date.fromisoformat(new_expires_on[:10])
        except ValueError:
            raise WorkflowError("Enter the new expiry as YYYY-MM-DD")
    if new_expires_on <= _today():
        raise WorkflowError("The new expiry date must be in the future")
    now = _now()
    with _conn() as con:
        con.execute("INSERT INTO fact_state (fact_id, expires_on, renewed_by, renewed_at, note) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(fact_id) DO UPDATE SET expires_on=excluded.expires_on, renewed_by=excluded.renewed_by, "
                    "renewed_at=excluded.renewed_at, note=excluded.note",
                    (fact_id, new_expires_on.isoformat(), user, now, note))
        _log(con, None, user, "fact_renewed",
             f"{fact_id} · now expires {new_expires_on.isoformat()}" + (f" · {note}" if note else ""))
    fact.expires_on = new_expires_on
    rechecked = _recheck_fact(fact_id, user)
    return {"fact_id": fact_id, "expires_on": new_expires_on.isoformat(), **rechecked}


def _recheck_fact(fact_id: str, user: str) -> dict:
    """Re-run the expired-fact rule on every open draft that cited this fact; drop findings that no longer apply."""
    from engine import rules

    kb = _kb()
    rechecked, cleared = [], 0
    with _conn() as con:
        rows = con.execute(
            "SELECT DISTINCT c.id, c.current_version FROM content c JOIN findings f ON f.content_id = c.id "
            "AND f.version = c.current_version WHERE f.source_id = ? AND c.status IN ('draft','in_review','changes_requested')",
            (fact_id,)).fetchall()
        for r in rows:
            text = con.execute("SELECT text FROM versions WHERE content_id = ? AND version = ?",
                               (r["id"], r["current_version"])).fetchone()["text"]
            still = {f.span for f in rules.check_expired_facts(text, kb.facts) if f.source_id == fact_id}
            old = con.execute("SELECT id, data FROM findings WHERE content_id = ? AND version = ? AND source_id = ?",
                              (r["id"], r["current_version"], fact_id)).fetchall()
            gone = [o["id"] for o in old if json.loads(o["data"]).get("span") not in still]
            for fid in gone:
                con.execute("DELETE FROM findings WHERE id = ?", (fid,))
            cleared += len(gone)
            rechecked.append(r["id"])
            _log(con, r["id"], user, "rechecked", f"{fact_id} renewed · {len(gone)} finding(s) cleared")
    return {"rechecked": rechecked, "cleared": cleared}


# ---------------------------------------------------------------- guideline clarity insights (Improvement 3)

def _range(date_from, date_to) -> tuple[str, str]:
    def iso(d, end: bool) -> str:
        if d is None:
            return "9999" if end else "0000"
        if isinstance(d, str):
            d = date.fromisoformat(d[:10])
        if isinstance(d, datetime):
            d = d.date()
        return d.isoformat() + ("T23:59:59" if end else "T00:00:00")
    return iso(date_from, False), iso(date_to, True)


def _user_roles(con: sqlite3.Connection) -> dict[str, str]:
    return {r["username"]: r["role"] for r in con.execute("SELECT username, role FROM users")}


def guideline_stats(date_from=None, date_to=None, role: Optional[str] = None) -> list[dict]:
    """Per guideline / fact / term: how often its findings were shown, accepted, edited, rejected.

    shown = findings created in range (content.created_at). Rates are over decisions
    made in range by users of `role` (any role when None). Follows docs/clarity_thresholds.md.
    """
    lo, hi = _range(date_from, date_to)
    role = _check_role(role) if role else None
    kb = _kb()
    titles = {}
    for g in kb.guidelines:
        titles[g.id] = g.title
    for f in kb.facts:
        titles[f.id] = f.statement[:60]
    for t in kb.terms:
        titles[t.id] = f"Use '{t.approved}'"

    with _conn() as con:
        roles = _user_roles(con)
        shown = {r["source_id"]: r["n"] for r in con.execute(
            "SELECT f.source_id, COUNT(*) AS n FROM findings f JOIN content c ON c.id = f.content_id "
            "AND f.version = c.current_version WHERE c.created_at BETWEEN ? AND ? GROUP BY f.source_id", (lo, hi))}
        decs = con.execute("SELECT source_id, category, status, user FROM decisions WHERE at BETWEEN ? AND ?",
                           (lo, hi)).fetchall()
        rewords = {r["guideline_id"]: dict(r) for r in con.execute("SELECT * FROM rewordings")}

    agg: dict[str, dict] = {}
    for d in decs:
        if role and roles.get(d["user"], "creator") != role:
            continue
        a = agg.setdefault(d["source_id"], {"category": d["category"], "accepted": 0, "edited": 0, "rejected": 0,
                                            "users": set()})
        a[d["status"]] = a.get(d["status"], 0) + 1
        a["users"].add(d["user"])

    out = []
    for sid in set(shown) | set(agg):
        a = agg.get(sid, {"category": "", "accepted": 0, "edited": 0, "rejected": 0, "users": set()})
        n_shown = max(shown.get(sid, 0), a["accepted"] + a["edited"] + a["rejected"])
        decided = a["accepted"] + a["edited"] + a["rejected"]
        override_rate = round(a["edited"] / decided, 3) if decided else 0.0
        reject_rate = round(a["rejected"] / decided, 3) if decided else 0.0
        unclear = n_shown >= UNCLEAR_MIN_SHOWN and (override_rate >= UNCLEAR_OVERRIDE_RATE or reject_rate >= UNCLEAR_REJECT_RATE)
        reasons = []
        if decided and override_rate >= UNCLEAR_OVERRIDE_RATE:
            reasons.append(f"fix edited {a['edited']} of {decided} times ({override_rate:.0%})")
        if decided and reject_rate >= UNCLEAR_REJECT_RATE:
            reasons.append(f"rejected {a['rejected']} of {decided} times ({reject_rate:.0%})")
        who = f" by {len(a['users'])} different user{'s' if len(a['users']) != 1 else ''}" if a["users"] else ""
        reason = ("; ".join(reasons) + who).capitalize() if unclear else (
            f"Below threshold: shown {n_shown} time(s)" if n_shown < UNCLEAR_MIN_SHOWN else "Accepted most of the time")
        rw = rewords.get(sid, {})
        out.append({
            "source_id": sid, "title": titles.get(sid, sid), "category": a["category"],
            "shown": n_shown, "decided": decided, "accepted": a["accepted"], "edited": a["edited"],
            "rejected": a["rejected"], "override_rate": override_rate, "reject_rate": reject_rate,
            "unclear": unclear, "reason": reason,
            "suggested_rewording": rw.get("suggested", ""), "accepted_rewording": rw.get("accepted", ""),
            "accepted_by": rw.get("accepted_by", ""),
        })
    out.sort(key=lambda d: (not d["unclear"], -(d["reject_rate"] + d["override_rate"]), -d["shown"], d["source_id"]))
    return out


def repeat_issues(group_by: str = "category", date_from=None, date_to=None) -> list[dict]:
    """Issues that keep coming back.

    group_by='category': count of findings per category with how many creators raise it.
    group_by='creator' : (author, category, count) pairs at or above REPEAT_MIN_COUNT.
    """
    lo, hi = _range(date_from, date_to)
    with _conn() as con:
        rows = con.execute(
            "SELECT c.author, f.category, COUNT(*) AS n FROM findings f JOIN content c ON c.id = f.content_id "
            "AND f.version = c.current_version WHERE c.created_at BETWEEN ? AND ? GROUP BY c.author, f.category",
            (lo, hi)).fetchall()
    if group_by == "creator":
        out = [{"creator": r["author"], "category": r["category"], "count": r["n"], "repeat": r["n"] >= REPEAT_MIN_COUNT}
               for r in rows]
        out.sort(key=lambda d: (-d["count"], d["creator"]))
        return out
    cats: dict[str, dict] = {}
    for r in rows:
        c = cats.setdefault(r["category"], {"category": r["category"], "count": 0, "creators": set()})
        c["count"] += r["n"]
        c["creators"].add(r["author"])
    out = [{"category": k, "count": v["count"], "creators": len(v["creators"])} for k, v in cats.items()]
    out.sort(key=lambda d: -d["count"])
    return out


_REWORD_PROMPT = """You help a brand team write clearer content guidelines.
Rewrite the guideline below so a busy copywriter understands exactly what to do and what to avoid.
Keep the meaning. Add no new rules. One or two short sentences, plain words, no jargon.
Reviewers overrode or rejected this guideline's findings often, which suggests it is unclear.

Guideline id: {gid}
Title: {title}
Current wording: {rule}
Example of a good sentence: {good}
Example of a bad sentence: {bad}

Return ONLY the rewritten guideline text."""


def suggest_rewording(guideline_id: str, llm=None) -> str:
    """A clearer wording for a guideline (Gemini; template fallback). Cached in the DB."""
    with _conn() as con:
        row = con.execute("SELECT suggested FROM rewordings WHERE guideline_id = ?", (guideline_id,)).fetchone()
    if row and row["suggested"]:
        return row["suggested"]
    kb = _kb()
    g = next((x for x in kb.guidelines if x.id == guideline_id), None)
    if g is None:
        raise WorkflowError(f"{guideline_id} is not a guideline; only guidelines can be reworded")
    text = ""
    try:
        if llm is None and os.getenv("GEMINI_API_KEY"):
            from engine import review
            llm = review._gemini_generate
        if llm is not None:
            raw = llm(_REWORD_PROMPT.format(gid=g.id, title=g.title, rule=g.rule,
                                            good=(g.examples_good or [""])[0], bad=(g.examples_bad or [""])[0]))
            text = _plain_text(raw)
    except Exception:
        text = ""
    if not text:
        bad = (g.examples_bad or [""])[0]
        text = (f"{g.title}: {g.rule.rstrip('.')}. "
                + (f"Do not write things like \"{bad}\"." if bad else "")).strip()
    with _conn() as con:
        con.execute("INSERT INTO rewordings (guideline_id, suggested, suggested_at) VALUES (?,?,?) "
                    "ON CONFLICT(guideline_id) DO UPDATE SET suggested=excluded.suggested, suggested_at=excluded.suggested_at",
                    (guideline_id, text, _now()))
    return text


def _plain_text(raw: str) -> str:
    raw = (raw or "").strip().strip("`")
    try:  # the review client asks for JSON; accept a JSON string or {"text": ...}
        data = json.loads(raw)
        if isinstance(data, str):
            return data.strip()
        if isinstance(data, dict):
            return str(next(iter(data.values()), "")).strip()
        if isinstance(data, list) and data:
            return str(data[0]).strip()
    except (ValueError, TypeError):
        pass
    return raw.strip().strip('"')


def accept_rewording(guideline_id: str, text: str, user: str, role: str) -> None:
    """Admin accepts a clearer wording: stored, logged, and applied to the loaded knowledge base."""
    if _check_role(role) != "admin":
        raise WorkflowError("Only an admin can change guideline wording")
    text = (text or "").strip()
    if len(text) < 10:
        raise WorkflowError("The new wording is too short")
    kb = _kb()
    g = next((x for x in kb.guidelines if x.id == guideline_id), None)
    if g is None:
        raise WorkflowError(f"Guideline {guideline_id} not found")
    now = _now()
    with _conn() as con:
        con.execute("INSERT INTO rewordings (guideline_id, accepted, accepted_by, accepted_at) VALUES (?,?,?,?) "
                    "ON CONFLICT(guideline_id) DO UPDATE SET accepted=excluded.accepted, accepted_by=excluded.accepted_by, "
                    "accepted_at=excluded.accepted_at", (guideline_id, text, user, now))
        _log(con, None, user, "guideline_reworded", f"{guideline_id} · {text[:120]}")
    g.rule = text
    doc = kb.get(guideline_id)
    if doc is not None:
        try:
            doc.text = text
        except Exception:
            pass


def apply_guideline_overrides(guidelines: list) -> int:
    """Apply accepted rewordings to in-memory Guideline objects (called from bootstrap)."""
    with _conn() as con:
        rows = {r["guideline_id"]: r["accepted"] for r in con.execute(
            "SELECT guideline_id, accepted FROM rewordings WHERE accepted != ''")}
    n = 0
    for g in guidelines:
        if g.id in rows and g.rule != rows[g.id]:
            g.rule = rows[g.id]
            n += 1
    return n


# ---------------------------------------------------------------- UI adapters (Aashi's app/services.py)
# The Streamlit pages work with "submissions": one piece of content sent for approval
# together with the findings the creator already accepted / edited / rejected.

_UI_STATUS = {"in_review": "pending", "approved": "approved", "changes_requested": "rejected", "draft": "draft"}


def _finding_from_ui(d: dict) -> Finding:
    data = {k: d[k] for k in Finding.model_fields if k in d}
    data["status"] = d.get("status") or "open"
    return Finding.model_validate(data)


def submit_for_approval(title: str, text: str, findings: list[dict], author: str) -> str:
    """Save content + its findings (with the creator's decisions) and send it for approval.

    A second identical submission within a minute (double-click) returns the first id.
    """
    with _conn() as con:
        recent = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(timespec="seconds")
        dup = con.execute(
            "SELECT c.id FROM content c JOIN versions v ON v.content_id = c.id AND v.version = c.current_version "
            "WHERE c.author = ? AND c.title = ? AND v.text = ? AND c.created_at >= ? ORDER BY c.id DESC LIMIT 1",
            (author, title.strip() or "Untitled", text, recent)).fetchone()
    if dup:
        return str(dup["id"])
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
    try:
        cid = int(sub_id)
    except (TypeError, ValueError):
        raise WorkflowError("Unknown submission")
    approve(cid, user, role, approved=(decision == "approved"), comment=comment)


_ACTIVITY = {
    "created": ("created", "open"), "reviewed": ("ran a review on", "open"),
    "new_version": ("saved a new version of", "open"),
    "finding_accepted": ("accepted a finding in", "ok"), "finding_edited": ("edited a fix in", "ok"),
    "finding_rejected": ("rejected a finding in", "bad"),
    "approved": ("approved", "ok"), "changes_requested": ("requested changes on", "bad"),
    "fact_renewed": ("renewed a fact", "ok"), "rechecked": ("re-checked", "ok"),
    "guideline_reworded": ("reworded a guideline", "ok"), "signed_in": ("signed in", "open"),
    "seeded": ("loaded demo data", "open"),
}


def get_recent_activity(limit: int = 5) -> list[dict]:
    """Latest audit-log events for the dashboard: when, who, what, status (open | ok | bad)."""
    with _conn() as con:
        rows = con.execute("SELECT a.user, a.action, a.at, a.detail, c.title FROM audit_log a "
                           "LEFT JOIN content c ON c.id = a.content_id WHERE a.action != 'signed_in' "
                           "ORDER BY a.id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        verb, status = _ACTIVITY.get(r["action"], (r["action"].replace("_", " "), "open"))
        what = f"{verb} “{r['title']}”" if r["title"] else f"{verb} {r['detail'].split(' · ')[0]}".strip()
        out.append({"when": r["at"][11:16], "day": r["at"][:10], "who": r["user"], "what": what, "status": status})
    return out


def get_dashboard_stats(role: str) -> dict:
    """Numbers for the home screen."""
    _check_role(role)
    today = _today().isoformat()
    with _conn() as con:
        reviews = con.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'reviewed' AND at LIKE ?",
                              (today + "%",)).fetchone()[0]
        open_f = con.execute("SELECT COUNT(*) FROM findings f JOIN content c ON c.id = f.content_id "
                             "AND f.version = c.current_version WHERE f.status = 'open' "
                             "AND c.status != 'approved'").fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM content WHERE status = 'in_review'").fetchone()[0]
        seeded_at = _meta_get(con, "seeded_at")
    expired = expiring = "–"
    try:
        reg = fact_register()
        expired = sum(1 for f in reg if f["status"] == "expired")
        expiring = sum(1 for f in reg if f["status"] == "expiring_soon")
    except Exception:
        pass
    return {"reviews_today": reviews, "open_findings": open_f, "pending_approvals": pending,
            "expired_facts": expired, "expiring_facts": expiring,
            "seeded_at": seeded_at[:16].replace("T", " ") if seeded_at else ""}


def health() -> dict:
    """Quick self-check for the Home page's status expander."""
    out = {"db": False, "brand_kit": False, "gemini_key": bool(os.getenv("GEMINI_API_KEY")), "seeded": False}
    try:
        with _conn() as con:
            con.execute("SELECT 1").fetchone()
            out["db"] = True
            out["seeded"] = bool(_meta_get(con, "seeded_at"))
    except Exception:
        pass
    try:
        out["brand_kit"] = len(_kb().guidelines) > 0
    except Exception:
        pass
    return out
