import hashlib
import json
from pathlib import Path

import pytest

from engine.knowledge import BrandKitError, KnowledgeBase, load_brand_kit

KIT = Path(__file__).parent / "fixtures" / "brand_kit"


def fake_embed(texts):
    """Deterministic bag-of-words vectors, so semantic search is testable offline."""
    out = []
    for t in texts:
        v = [0.0] * 64
        for w in t.lower().split():
            v[int(hashlib.md5(w.strip(".,!?'").encode()).hexdigest(), 16) % 64] += 1.0
        out.append(v)
    return out


def test_load_brand_kit():
    g, f, t = load_brand_kit(KIT)
    assert [x.id for x in g] == ["G01", "G02", "G03"]
    assert len(f) == 3 and len(t) == 2
    assert f[1].expires_on is None


def test_missing_file(tmp_path):
    with pytest.raises(BrandKitError, match="Missing"):
        load_brand_kit(tmp_path)


def test_bad_item_reports_file_and_position(tmp_path):
    for name in ("guidelines.json", "facts.json", "glossary.json"):
        (tmp_path / name).write_text((KIT / name).read_text())
    bad = json.loads((KIT / "facts.json").read_text())
    bad[1]["id"] = "fact-2"
    (tmp_path / "facts.json").write_text(json.dumps(bad))
    with pytest.raises(BrandKitError, match="facts.json item 2"):
        load_brand_kit(tmp_path)


def test_duplicate_ids(tmp_path):
    for name in ("guidelines.json", "facts.json", "glossary.json"):
        (tmp_path / name).write_text((KIT / name).read_text())
    g = json.loads((KIT / "guidelines.json").read_text())
    g[1]["id"] = "G01"
    (tmp_path / "guidelines.json").write_text(json.dumps(g))
    with pytest.raises(BrandKitError, match="duplicate"):
        load_brand_kit(tmp_path)


def test_keyword_search_finds_relevant_sources():
    kb = KnowledgeBase.from_folder(KIT, use_embeddings=False)
    assert kb.backend == "keyword"
    ids = [m.source_id for m in kb.search("We are the fastest, number one payments app!", k=3)]
    assert ids[0] == "G02"
    ids = [m.source_id for m in kb.search("Join our 2 million registered users")]
    assert ids[0] == "F01"
    assert kb.search("   ") == []


def test_semantic_search_with_embedder():
    g, f, t = load_brand_kit(KIT)
    kb = KnowledgeBase(g, f, t, embed_fn=fake_embed)
    assert kb.backend == "semantic"
    res = kb.search("Transfers between Lumora accounts are free", k=2)
    assert res[0].source_id == "F02"
    assert res[0].score > res[1].score


def test_falls_back_when_embeddings_fail():
    def broken(_):
        raise RuntimeError("quota exceeded")
    g, f, t = load_brand_kit(KIT)
    kb = KnowledgeBase(g, f, t, embed_fn=broken)
    assert kb.backend == "keyword"
    assert kb.search("click here to read more")[0].source_id == "G03"


def test_get_by_id():
    kb = KnowledgeBase.from_folder(KIT, use_embeddings=False)
    assert kb.get("T01").source_type == "term"
    assert kb.get("G99") is None
