"""Brand knowledge base: loads data/brand_kit and searches it.
Owner: Suraj (Step 3).

Search backends
---------------
1. "semantic": ChromaDB + Gemini embeddings. Used when GEMINI_API_KEY is set.
2. "keyword":  built-in BM25 ranking. No network, no key. Used as fallback
   when there is no key or the embedding call fails, so the demo never breaks.

The backend that answered is reported by `KnowledgeBase.backend`.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

from engine.schemas import Fact, Guideline, SourceMatch, Term

log = logging.getLogger(__name__)

BRAND_KIT_DIR = Path(__file__).resolve().parent.parent / "data" / "brand_kit"
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

EmbedFn = Callable[[list[str]], list[list[float]]]


# ---------------------------------------------------------------- loading

class BrandKitError(ValueError):
    """Raised when a brand-kit file is missing or invalid."""


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        raise BrandKitError(f"Missing brand-kit file: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BrandKitError(f"{path.name} is not valid JSON (line {e.lineno}): {e.msg}") from e
    if not isinstance(data, list):
        raise BrandKitError(f"{path.name} must contain a JSON list")
    return data


def load_brand_kit(folder: Path = BRAND_KIT_DIR) -> tuple[list[Guideline], list[Fact], list[Term]]:
    """Read guidelines.json, facts.json, glossary.json and validate them."""
    folder = Path(folder)
    out = []
    for fname, model in (("guidelines.json", Guideline), ("facts.json", Fact), ("glossary.json", Term)):
        items = []
        for i, raw in enumerate(_read_json(folder / fname)):
            try:
                items.append(model.model_validate(raw))
            except Exception as e:  # pydantic ValidationError -> readable message
                raise BrandKitError(f"{fname} item {i + 1}: {e}") from e
        ids = [x.id for x in items]
        dupes = {x for x in ids if ids.count(x) > 1}
        if dupes:
            raise BrandKitError(f"{fname}: duplicate ids {sorted(dupes)}")
        out.append(items)
    return out[0], out[1], out[2]


def to_documents(guidelines: list[Guideline], facts: list[Fact], terms: list[Term]) -> list[SourceMatch]:
    """Flatten the brand kit into searchable text items (score 0 until searched)."""
    docs: list[SourceMatch] = []
    for g in guidelines:
        text = f"{g.title}. {g.rule}"
        if g.examples_bad:
            text += " Avoid: " + " | ".join(g.examples_bad)
        docs.append(SourceMatch(source_id=g.id, source_type="guideline", text=text, score=0.0))
    for f in facts:
        exp = f" (expires {f.expires_on.isoformat()})" if f.expires_on else ""
        docs.append(SourceMatch(source_id=f.id, source_type="fact",
                                text=f"{f.statement} Source: {f.source}{exp}", score=0.0))
    for t in terms:
        text = f"Approved term: {t.approved}."
        if t.banned_variants:
            text += " Do not write: " + ", ".join(t.banned_variants) + "."
        if t.note:
            text += " " + t.note
        docs.append(SourceMatch(source_id=t.id, source_type="term", text=text, score=0.0))
    return docs


# ---------------------------------------------------------------- keyword (BM25)

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("a an the and or of to in on for with is are be by as at it this that we our you your from not".split())


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class _BM25:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(_tokens(t)) for t in texts]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: str) -> list[float]:
        q = _tokens(query)
        res = []
        for d, ln in zip(self.docs, self.lens):
            s = 0.0
            for t in q:
                tf = d.get(t, 0)
                if tf:
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * ln / (self.avg or 1)))
            res.append(s)
        return res


# ---------------------------------------------------------------- semantic (Chroma)

def gemini_embedder(api_key: Optional[str] = None, model: str = EMBED_MODEL) -> EmbedFn:
    """Return a function that embeds a batch of texts with Gemini."""
    from google import genai  # imported lazily so tests run without the SDK configured

    client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])

    def embed(texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 50):  # stay well inside batch limits
            resp = client.models.embed_content(model=model, contents=texts[i:i + 50])
            out.extend(e.values for e in resp.embeddings)
        return out

    return embed


class KnowledgeBase:
    """Index over the brand kit. Build once at startup, then call search()."""

    def __init__(self, guidelines: list[Guideline], facts: list[Fact], terms: list[Term],
                 embed_fn: Optional[EmbedFn] = None, persist_dir: Optional[str] = None):
        self.guidelines, self.facts, self.terms = guidelines, facts, terms
        self.docs = to_documents(guidelines, facts, terms)
        self._by_id = {d.source_id: d for d in self.docs}
        self._bm25 = _BM25([d.text for d in self.docs])
        self._embed = embed_fn
        self._collection = None
        self.backend = "keyword"
        if embed_fn is not None and self.docs:
            try:
                self._build_chroma(persist_dir)
                self.backend = "semantic"
            except Exception as e:  # network, quota, bad key, chroma issues
                log.warning("Semantic index unavailable, using keyword search: %s", e)

    # -- construction
    @classmethod
    def from_folder(cls, folder: Path = BRAND_KIT_DIR, use_embeddings: Optional[bool] = None,
                    persist_dir: Optional[str] = None) -> "KnowledgeBase":
        g, f, t = load_brand_kit(folder)
        if use_embeddings is None:
            use_embeddings = bool(os.getenv("GEMINI_API_KEY"))
        embed = None
        if use_embeddings:
            try:
                embed = gemini_embedder()
            except Exception as e:
                log.warning("Gemini embedder not available: %s", e)
        return cls(g, f, t, embed_fn=embed, persist_dir=persist_dir)

    def _build_chroma(self, persist_dir: Optional[str]) -> None:
        import chromadb

        client = chromadb.PersistentClient(path=persist_dir) if persist_dir else chromadb.EphemeralClient()
        try:
            client.delete_collection("brand_kit")
        except Exception:
            pass
        col = client.create_collection("brand_kit", metadata={"hnsw:space": "cosine"})
        vectors = self._embed([d.text for d in self.docs])
        col.add(ids=[d.source_id for d in self.docs], documents=[d.text for d in self.docs],
                embeddings=vectors, metadatas=[{"source_type": d.source_type} for d in self.docs])
        self._collection = col

    # -- lookup
    def get(self, source_id: str) -> Optional[SourceMatch]:
        return self._by_id.get(source_id)

    def search(self, text: str, k: int = 6) -> list[SourceMatch]:
        """Return up to k brand-kit items most relevant to `text`, best first."""
        if not text.strip() or not self.docs:
            return []
        k = min(k, len(self.docs))
        if self.backend == "semantic":
            try:
                return self._search_semantic(text, k)
            except Exception as e:
                log.warning("Semantic search failed, falling back to keyword: %s", e)
        return self._search_keyword(text, k)

    def _search_semantic(self, text: str, k: int) -> list[SourceMatch]:
        q = self._embed([text])[0]
        res = self._collection.query(query_embeddings=[q], n_results=k)
        out = []
        for sid, dist in zip(res["ids"][0], res["distances"][0]):
            d = self._by_id[sid]
            out.append(d.model_copy(update={"score": round(1.0 - float(dist), 4)}))
        return out

    def _search_keyword(self, text: str, k: int) -> list[SourceMatch]:
        scores = self._bm25.scores(text)
        ranked = sorted(range(len(self.docs)), key=lambda i: scores[i], reverse=True)
        return [self.docs[i].model_copy(update={"score": round(scores[i], 4)})
                for i in ranked[:k] if scores[i] > 0]


# ---------------------------------------------------------------- module-level helpers

_default: Optional[KnowledgeBase] = None


def build_index(folder: Path = BRAND_KIT_DIR, **kwargs) -> KnowledgeBase:
    """(Re)build the shared index from the brand-kit folder and return it."""
    global _default
    _default = KnowledgeBase.from_folder(folder, **kwargs)
    return _default


def get_kb() -> KnowledgeBase:
    """Shared index, built on first use."""
    return _default or build_index()


def search(text: str, k: int = 6) -> list[SourceMatch]:
    """Return the k brand-kit items most relevant to `text`."""
    return get_kb().search(text, k)
