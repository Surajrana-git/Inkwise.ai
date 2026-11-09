# INKWISE AI

Brand governance that reviews content **before** it is published. Every finding cites the exact guideline or approved fact behind it, or is marked **UNVERIFIED**. Humans make every decision.

Team **DECODIANS** · CodeTitans India 2026 (Inkloom AI hackathon)

| Member | Role |
|---|---|
| Suraj Kumar (lead) | Backend |
| Riyana S | AI / ML |
| Aashi Yadav | Frontend |
| Pritha S | Product / Research |

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add your Gemini API key
streamlit run app/Home.py
pytest                                                # run tests
```

## Layout

```
engine/   pure Python review engine (no UI)
  schemas.py    shared data contracts (Finding, Guideline, Fact, Term)
  knowledge.py  brand kit loading + ChromaDB search
  review.py     Gemini review with citations
  rules.py      glossary, expired-fact and readability checks
  redact.py     masks personal data before any API call
  workflow.py   roles, approvals, versions, audit log (SQLite)
app/      Streamlit UI
data/brand_kit/  synthetic demo brand "Lumora"
eval/     labelled test set + evaluation script
docs/     architecture, disclosures, user testing
```

## Three improvements (named in Round 2, delivered in Round 3)
1. **Evidence-grounded findings**: every flag cites its source or is marked UNVERIFIED; measured by citation accuracy.
2. **Fact freshness**: approved facts have owners and expiry dates, so outdated claims are caught.
3. **Guideline Clarity Insights**: reviewer overrides and disagreements show which guidelines are unclear and which mistakes repeat.

## Disclosures
See [docs/disclosures.md](docs/disclosures.md).
