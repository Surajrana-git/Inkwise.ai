"""App startup: database + knowledge index. Owner: Suraj (Step 9).

Call `startup()` once per process (the Streamlit app wraps it in st.cache_resource).
Streamlit Community Cloud storage is wiped on restart, so everything here must be
safe to run again from scratch.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

# ChromaDB needs SQLite >= 3.35. Some Linux hosts ship an older one; swap in the
# bundled pysqlite3 build when it is installed (requirements.txt, Linux only).
try:  # pragma: no cover - depends on host
    import pysqlite3  # type: ignore

    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

from engine import knowledge, workflow  # noqa: E402

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_KIT = ROOT / "tests" / "fixtures" / "brand_kit"


@dataclass
class AppState:
    kb: knowledge.KnowledgeBase
    brand_kit_dir: Path
    using_sample_kit: bool


def _kit_ready(folder: Path) -> bool:
    return all((folder / n).exists() for n in ("guidelines.json", "facts.json", "glossary.json"))


def startup() -> AppState:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    workflow.init_db()

    kit = knowledge.BRAND_KIT_DIR
    sample = not _kit_ready(kit)
    if sample:
        log.warning("data/brand_kit is incomplete; using the small sample kit in tests/fixtures")
        kit = SAMPLE_KIT
    kb = knowledge.build_index(kit)
    return AppState(kb=kb, brand_kit_dir=kit, using_sample_kit=sample)
