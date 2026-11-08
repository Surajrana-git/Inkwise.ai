"""AI review: retrieves sources, asks Gemini, returns cited Findings.
Owner: Riyana (Step 4).

Rules for this module:
- Every Finding must cite a source_id from knowledge.search() results, or be
  UNVERIFIED when no source supports or refutes a claim.
- Text passes through redact.redact() before any API call.
"""
from __future__ import annotations

from engine.schemas import ReviewResult


def review_text(text: str) -> ReviewResult:
    """Run rule checks + AI checks and return all findings."""
    raise NotImplementedError("Step 4 (Riyana)")
