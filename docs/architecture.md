# Architecture (Suraj, completed in Step 14)

**Engine + UI.** `engine/` is a pure Python package with a fixed interface; `app/` (Streamlit) only calls it.

```
Content ──► redact ──► rules (glossary, expired facts, readability) ──┐
                 └──► knowledge.search (ChromaDB) ──► Gemini review ──┴─► Findings (cited / UNVERIFIED)
                                                                              │
                                    workflow (SQLite): versions, decisions, approvals, audit log
```

## Key decisions
- TODO: why RAG + rules instead of fine-tuning
- TODO: why UNVERIFIED instead of guessing
- TODO: hardest part and how we handled it
