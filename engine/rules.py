"""Deterministic checks that need no AI: glossary, expired facts, readability.
Owner: Riyana (Step 4).
"""
from __future__ import annotations

from engine.schemas import Fact, Finding, Term


def check_terminology(text: str, terms: list[Term]) -> list[Finding]:
    """Flag banned variants of approved terms (checked_by='rule')."""
    raise NotImplementedError("Step 4 (Riyana)")


def check_expired_facts(text: str, facts: list[Fact]) -> list[Finding]:
    """Flag text that repeats a fact whose expires_on date has passed."""
    raise NotImplementedError("Step 4 (Riyana)")


def check_readability(text: str) -> list[Finding]:
    """Flag hard-to-read text (e.g. textstat grade too high)."""
    raise NotImplementedError("Step 4 (Riyana)")
