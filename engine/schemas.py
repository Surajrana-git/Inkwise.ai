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


class CheckedBy(str, Enum):
    RULE = "rule"   # deterministic check (glossary, expiry, readability)
    AI = "ai"       # Gemini judgement grounded in retrieved sources


class FindingStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


# ---------- Brand kit (data/brand_kit/*.json) ----------

class Guideline(BaseModel):
    id: str = Field(pattern=r"^G\d{2}$")          # G01..G99
    title: str
    rule: str                                      # the guideline text itself
    category: Category
    examples_good: list[str] = []
    examples_bad: list[str] = []


class Fact(BaseModel):
    id: str = Field(pattern=r"^F\d{2}$")          # F01..F99
    statement: str                                 # approved wording of the fact
    source: str                                    # where it comes from
    owner: str                                     # who keeps it current
    expires_on: Optional[date] = None              # None = does not expire

    def is_expired(self, today: Optional[date] = None) -> bool:
        if self.expires_on is None:
            return False
        return self.expires_on < (today or date.today())


class Term(BaseModel):
    id: str = Field(pattern=r"^T\d{2}$")          # T01..T99
    approved: str                                  # e.g. "Lumora Pay"
    banned_variants: list[str] = []                # e.g. ["LumoraPay", "Lumora pay"]
    note: str = ""


class SourceMatch(BaseModel):
    """One brand-kit item returned by knowledge.search()."""
    source_id: str                                 # G04 / F12 / T07
    source_type: str                               # "guideline" | "fact" | "term"
    text: str                                      # text shown to the reviewer
    score: float                                   # similarity, higher = closer


# ---------- Review output ----------

class Finding(BaseModel):
    id: str                                        # "f-001"
    category: Category
    span: str                                      # exact text flagged
    source_id: str                                 # G04 | F12 | T07 | UNVERIFIED
    source_text: str = ""                          # quoted guideline/fact ("" if UNVERIFIED)
    why: str                                       # plain-language explanation
    suggested_fix: str                             # rewrite that keeps the intent
    confidence: float = Field(ge=0.0, le=1.0)
    checked_by: CheckedBy
    status: FindingStatus = FindingStatus.OPEN

    @field_validator("source_id")
    @classmethod
    def _source_format(cls, v: str) -> str:
        if v == UNVERIFIED:
            return v
        if len(v) == 3 and v[0] in "GFT" and v[1:].isdigit():
            return v
        raise ValueError("source_id must look like G04, F12, T07 or be 'UNVERIFIED'")

    @property
    def is_verified(self) -> bool:
        return self.source_id != UNVERIFIED


class ReviewResult(BaseModel):
    content_id: Optional[int] = None               # set once saved by workflow
    text: str                                      # text that was reviewed (after redaction)
    findings: list[Finding] = []
    redactions: int = 0                            # how many personal-data items were masked
    model: str = ""                                # e.g. "gemini-…" for disclosure
    ai_error: str = ""                             # set when the AI part did not run (UI shows a warning)
