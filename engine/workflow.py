"""Review and approval workflow with an audit log (SQLite).
Owner: Suraj (Step 6). Interface is fixed now so Aashi can code against it.

Roles: creator, manager, reviewer, admin.
Content status: draft -> in_review -> approved | changes_requested
"""
from __future__ import annotations

from engine.schemas import Finding, FindingStatus, ReviewResult

ROLES = ("creator", "manager", "reviewer", "admin")


def init_db() -> None:
    raise NotImplementedError("Step 6 (Suraj)")


def submit_content(author: str, title: str, text: str) -> int:
    """Save a new draft (version 1) and return its content_id."""
    raise NotImplementedError("Step 6 (Suraj)")


def save_review(content_id: int, result: ReviewResult) -> None:
    raise NotImplementedError("Step 6 (Suraj)")


def decide_finding(content_id: int, finding_id: str, status: FindingStatus,
                   user: str, note: str = "") -> None:
    """Record accept / edit / reject on one finding (logged for Clarity Insights)."""
    raise NotImplementedError("Step 6 (Suraj)")


def approve(content_id: int, user: str, approved: bool, comment: str = "") -> None:
    raise NotImplementedError("Step 6 (Suraj)")


def queue(role: str) -> list[dict]:
    """Items waiting for this role."""
    raise NotImplementedError("Step 6 (Suraj)")


def history(content_id: int) -> list[dict]:
    """Versions + audit-log entries, oldest first."""
    raise NotImplementedError("Step 6 (Suraj)")
