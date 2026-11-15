
"""Shared data contracts for INKWISE AI.

Every module (knowledge, review, rules, workflow) and the Streamlit app
exchange these objects. Change them only after telling the whole team.
Owner: Suraj (Step 1).
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

UNVERIFIED = "UNVERIFIED"


class Category(str, Enum):
    TONE = "tone"
    TERMINOLOGY = "terminology"
    CLAIM = "claim"
    OUTDATED_FACT = "outdated_fact"
    MESSAGING = "messaging"
    ACCESSIBILITY = "accessibility"
    VISUAL = "visual"          # image checks: brand colours (contrast problems are accessibility)


class CheckedBy(str, Enum):
    RULE = "rule"
    AI = "ai"


class FindingStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


# ---------- Brand kit (data/brand_kit/*.json) ----------

class Guideline(BaseModel):
    id: str = Field(pattern=r"^G\d{2}$")
    title: str
    rule: str
    category: Category
    examples_good: list[str] = []
    examples_bad: list[str] = []


class Fact(BaseModel):
    id: str = Field(pattern=r"^F\d{2}$")
    statement: str
    source: str
    owner: str
    expires_on: Optional[date] = None

    def is_expired(self, today: Optional[date] = None) -> bool:
        if self.expires_on is None:
            return False
        return self.expires_on < (today or date.today())


class Term(BaseModel):
    id: str = Field(pattern=r"^T\d{2}$")
    approved: str
    banned_variants: list[str] = []
    note: str = ""


class SourceMatch(BaseModel):
    """One brand-kit item returned by knowledge.search()."""
    source_id: str
    source_type: str
    text: str
    score: float


# ---------- Review output ----------

class Finding(BaseModel):
    id: str
    category: Category
    span: str
    source_id: str
    source_text: str = ""
    why: str
    suggested_fix: str
    confidence: float = Field(ge=0.0, le=1.0)
    checked_by: CheckedBy
    status: FindingStatus = FindingStatus.OPEN

    # ---------- Round 3: Finding fields ----------

    evidence: str = ""
    evidence_verified: bool = False
    occurrences: list[tuple[int, int]] = Field(default_factory=list)
    fact_owner: str = ""
    freshness: str = ""
    where: str = "text"                            # "text" (the copy) | "image" (the campaign creative)
    box: Optional[list[float]] = None              # image findings: [x0, y0, x1, y1], fractions of width/height

    @field_validator("source_id")
    @classmethod
    def _source_format(cls, v: str) -> str:
        if v == UNVERIFIED:
            return v
        if len(v) == 3 and v[0] in "GFTV" and v[1:].isdigit():
            return v
        raise ValueError(
            "source_id must look like G04, F12, T07, V01 or be 'UNVERIFIED'"
        )

    @property
    def is_verified(self) -> bool:
        return self.source_id != UNVERIFIED


class ReviewResult(BaseModel):
    content_id: Optional[int] = None
    text: str
    findings: list[Finding] = []
    redactions: int = 0
    model: str = ""
    ai_error: str = ""
