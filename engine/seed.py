"""Demo data loaded when the database is empty (Round 3, Suraj).

Streamlit Community Cloud wipes local files on every restart, so a judge who opens
the app after a reboot would otherwise see empty History, Approvals and Insights.
`seed_if_empty()` recreates two weeks of realistic, clearly labelled demo activity:

- 14 pieces of content by three creators, reviewed, decided and (mostly) approved
- finding decisions designed so that a few guidelines come out "likely unclear"
  (see docs/clarity_thresholds.md), and two creators repeat the same category

If data/seed/decisions.json exists (Pritha's hand-written set) it is used instead of
the built-in generator. Format: a list of submissions, each
  {"title", "author", "days_ago", "text", "status": "approved|rejected|pending",
   "decided_by", "comment", "findings": [{"id","category","span","source_id","why",
   "suggested_fix","confidence","checked_by","status","note","decided_by"}]}
All timestamps are back-dated from "now" so the Insights date filters always have data.
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine import workflow as wf

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT / "data" / "seed" / "decisions.json"

# Guidelines whose findings reviewers keep overriding in the demo (come out "likely unclear")
UNCLEAR = {"G02": "rejected", "G12": "edited", "G13": "rejected"}
CREATORS = ("asha", "dev", "priya")
APPROVERS = ("meera", "ravi")


def _ts(days_ago: float, hour: int = 10, minute: int = 0) -> str:
    t = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return t.replace(hour=hour, minute=minute, second=0).isoformat(timespec="seconds")


def _builtin() -> list[dict]:
    """Deterministic demo set built from the brand kit's own bad examples."""
    kb = wf._kb()
    rnd = random.Random(7)
    guides = [g for g in kb.guidelines if g.examples_bad]
    terms = [t for t in kb.terms if t.banned_variants]
    expired = [f for f in kb.facts if f.is_expired()]
    titles = ["Diwali offer post", "Spend Insights launch email", "App update notes", "Referral push notification",
              "Investor newsletter blurb", "Support hours banner", "Onboarding SMS", "Festive season landing page",
              "Transfer fee explainer", "Biometric sign-in announcement", "Monthly statement reminder",
              "Partner co-marketing post", "Dispute form how-to", "Year-end recap"]
    subs = []
    for i, title in enumerate(titles):
        author = CREATORS[i % 3]
        days_ago = 13.5 - i * 0.9
        picks = rnd.sample(guides, 3)
        # make the "unclear" guidelines appear often enough to cross the threshold
        forced = [g for g in guides if g.id in UNCLEAR]
        picks = (picks + forced)[: 4 if i % 2 else 5]
        sentences, findings = [], []
        n = 1
        for g in picks:
            bad = g.examples_bad[0]
            sentences.append(bad)
            status = "accepted"
            if g.id in UNCLEAR:
                status = UNCLEAR[g.id] if rnd.random() < 0.7 else "accepted"
            elif rnd.random() < 0.12:
                status = "edited"
            findings.append({"id": f"f-{n:03d}", "category": g.category.value, "span": bad, "source_id": g.id,
                             "source_text": g.rule, "why": f"This goes against {g.title.lower()}.",
                             "suggested_fix": (g.examples_good or [bad])[0], "confidence": 0.8, "checked_by": "ai",
                             "status": status, "note": "fits the campaign brief" if status == "rejected" else ""})
            n += 1
        # creators asha and dev repeat terminology mistakes (repeat-issue demo)
        if author in ("asha", "dev") and terms:
            t = terms[i % len(terms)]
            bad = f"Open {t.banned_variants[0]} to check your activity."
            sentences.append(bad)
            findings.append({"id": f"f-{n:03d}", "category": "terminology", "span": t.banned_variants[0],
                             "source_id": t.id, "source_text": f"Approved: '{t.approved}'.",
                             "why": f"'{t.banned_variants[0]}' is a banned variant. Use '{t.approved}'.",
                             "suggested_fix": t.approved, "confidence": 1.0, "checked_by": "rule",
                             "status": "accepted", "note": ""})
            n += 1
        if i % 4 == 0 and expired:
            f = expired[i % len(expired)]
            sentences.append(f.statement)
            findings.append({"id": f"f-{n:03d}", "category": "outdated_fact", "span": f.statement,
                             "source_id": f.id, "source_text": f"{f.statement} (expired {f.expires_on}; owner: {f.owner})",
                             "why": f"This repeats fact {f.id}, which expired on {f.expires_on}.",
                             "suggested_fix": f"Remove this claim, or ask {f.owner} for the current figure.",
                             "confidence": 0.9, "checked_by": "rule", "status": "accepted", "note": "",
                             "fact_owner": f.owner, "freshness": "expired"})
        status = "pending" if i >= 12 else ("rejected" if i % 5 == 3 else "approved")
        subs.append({"title": title, "author": author, "days_ago": days_ago, "text": " ".join(sentences),
                     "status": status, "decided_by": APPROVERS[i % 2],
                     "comment": "Please fix the fee wording before this goes out." if status == "rejected" else "Good to go.",
                     "findings": findings})
    return subs


def _insert(sub: dict) -> int:
    created = _ts(sub["days_ago"], 9 + int(sub["days_ago"] * 3) % 8, int(sub["days_ago"] * 17) % 60)
    decided = _ts(sub["days_ago"] - 0.1, 15, int(sub["days_ago"] * 23) % 60)
    status = {"approved": "approved", "rejected": "changes_requested", "pending": "in_review"}[sub["status"]]
    with wf._conn() as con:
        cur = con.execute("INSERT INTO content (title, author, status, created_at, updated_at, decided_by, decided_at, "
                          "decision_comment) VALUES (?,?,?,?,?,?,?,?)",
                          (sub["title"], sub["author"], status, created, decided if status != "in_review" else created,
                           sub["decided_by"] if status != "in_review" else "",
                           decided if status != "in_review" else "", sub.get("comment", "") if status != "in_review" else ""))
        cid = cur.lastrowid
        con.execute("INSERT INTO versions (content_id, version, text, created_by, created_at) VALUES (?,?,?,?,?)",
                    (cid, 1, sub["text"], sub["author"], created))
        wf._log(con, cid, sub["author"], "created", f"v1 · {sub['title']}", at=created)
        for f in sub["findings"]:
            data = {k: v for k, v in f.items() if k not in ("note", "decided_by")}
            data.setdefault("status", "open")
            con.execute("INSERT INTO findings (content_id, version, finding_id, category, source_id, status, data) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (cid, 1, f["id"], f["category"], f["source_id"], f.get("status", "open"), json.dumps(data)))
        wf._log(con, cid, "inkwise-ai", "reviewed", f"v1 · {len(sub['findings'])} findings (seeded demo)", at=created)
        for f in sub["findings"]:
            st = f.get("status", "open")
            if st == "open":
                continue
            who = f.get("decided_by", sub["author"])
            at = _ts(sub["days_ago"] - 0.02, 11, int(sub["days_ago"] * 31) % 60)
            con.execute("INSERT INTO decisions (content_id, version, finding_id, source_id, category, status, user, note, at) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (cid, 1, f["id"], f["source_id"], f["category"], st, who, f.get("note", ""), at))
            wf._log(con, cid, who, f"finding_{st}", f"{f['id']} ({f['source_id']})", at=at)
        if status != "in_review":
            wf._log(con, cid, sub["decided_by"], status, f"v1 · manager · {sub.get('comment', '')}", at=decided)
    return cid


def seed_if_empty(force: bool = False) -> int:
    """Load demo data when the content table is empty. Returns the number of items inserted."""
    with wf._conn() as con:
        n = con.execute("SELECT COUNT(*) FROM content").fetchone()[0]
    if n and not force:
        return 0
    try:
        subs = json.loads(SEED_FILE.read_text(encoding="utf-8")) if SEED_FILE.exists() else _builtin()
        source = "data/seed/decisions.json" if SEED_FILE.exists() else "built-in"
    except Exception as e:  # a broken seed file must never stop the app
        log.warning("seed file unreadable (%s); using built-in demo data", e)
        subs, source = _builtin(), "built-in"
    for sub in subs:
        _insert(sub)
    with wf._conn() as con:
        wf._meta_set(con, "seeded_at", wf._now())
        wf._log(con, None, "system", "seeded", f"{len(subs)} demo items ({source})")
    return len(subs)
