"""Brand knowledge base: loads data/brand_kit and searches it.
Owner: Suraj (Step 3). Interface is fixed now so Riyana can code against it.
"""
from __future__ import annotations

from pathlib import Path

from engine.schemas import Fact, Guideline, SourceMatch, Term

BRAND_KIT_DIR = Path(__file__).resolve().parent.parent / "data" / "brand_kit"


def load_brand_kit(folder: Path = BRAND_KIT_DIR) -> tuple[list[Guideline], list[Fact], list[Term]]:
    """Read guidelines.json, facts.json, glossary.json and validate them."""
    raise NotImplementedError("Step 3 (Suraj)")


def build_index(folder: Path = BRAND_KIT_DIR) -> None:
    """Embed every guideline, fact and term into ChromaDB."""
    raise NotImplementedError("Step 3 (Suraj)")


def search(text: str, k: int = 6) -> list[SourceMatch]:
    """Return the k brand-kit items most relevant to `text`."""
    raise NotImplementedError("Step 3 (Suraj)")
