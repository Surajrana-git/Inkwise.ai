"""PDF / Word / text import on the Review page (planned Round 3 item: PDF/DOCX review)."""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import services  # noqa: E402


def docx_bytes(*paras, table=None):
    import docx
    d = docx.Document()
    for p in paras:
        d.add_paragraph(p)
    if table:
        t = d.add_table(rows=1, cols=len(table))
        for c, v in zip(t.rows[0].cells, table):
            c.text = v
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def pdf_bytes(*lines, pages=1):
    import pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        p = doc.new_page()
        for i, line in enumerate(lines):
            p.insert_text((72, 72 + 18 * i), line)
    return doc.tobytes()


def test_word_paragraphs_and_tables():
    out = services.extract_document(docx_bytes("Diwali offer", "Join 20 lakh users!", table=["Fees", "Always free"]),
                                    "post.docx")
    assert out["text"] == "Diwali offer\n\nJoin 20 lakh users!\n\nFees | Always free" and not out["truncated"]


def test_pdf_text_and_page_count():
    out = services.extract_document(pdf_bytes("Lumora Pay has 2 million registered users.", pages=2), "brief.pdf")
    assert out["pages"] == 2 and out["text"].count("2 million") == 2


def test_long_text_is_cut_to_the_review_limit():
    out = services.extract_document(("word " * 4000).encode(), "long.txt")
    assert out["truncated"] and len(out["text"]) <= services.MAX_REVIEW_CHARS and out["chars"] > 12_000


@pytest.mark.parametrize("data, name, msg", [
    (b"", "x.txt", "empty"), (b"abc", "old.doc", ".doc files are not supported"),
    (b"abc", "pic.png", "Upload a PDF"), (b"%PDF-1.4 broken", "bad.pdf", "Could not read that file"),
])
def test_unreadable_files_get_a_plain_message(data, name, msg):
    with pytest.raises(services.InputError, match=msg):
        services.extract_document(data, name)


def test_scanned_pdf_without_text_is_explained():
    import pymupdf
    doc = pymupdf.open()
    doc.new_page()
    with pytest.raises(services.InputError, match="scanned"):
        services.extract_document(doc.tobytes(), "scan.pdf")
