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
...................................................................................................................................................................

# InkWise AI – Disclosures

This document describes the external APIs, AI models, datasets, libraries, and AI-assisted development tools used in the InkWise AI project.

## 1. APIs and AI Models

- **Google Gemini API:** Used for AI-powered content review and identifying brand guideline violations.
- **Gemini 3.5 Flash Lite:** Used as the primary AI model for content analysis.
- **Backup Gemini Flash Models:** Used as fallback models when the primary model is unavailable.
- **Gemini Embeddings:** Used to convert brand guidelines and approved facts into vector representations for semantic search.

**API Usage:** The project uses the Google Gemini API free tier.

**Data Privacy:** Only synthetic demo data is used in the project. Personal information is masked before API calls.

## 2. Datasets

- **Lumora Brand Kit:** A synthetic brand guideline dataset created by the project team.
- **Evaluation Dataset:** Test and development datasets generated using `eval/build_dataset.py`.
- **Initial Datasets:** The first datasets were generated with Adaption Labs and stored in `eval/raw/`. These initial datasets were not used for evaluation scoring.

The project uses synthetic data and does not depend on real customer or confidential company information.

## 3. Libraries and Frameworks

The following libraries and frameworks are used:

| Library | Purpose |
|---|---|
| Streamlit | Web application interface |
| Pydantic | Data validation and schemas |
| google-genai | Gemini API integration |
| ChromaDB | Vector database and semantic search |
| textstat | Readability analysis |
| PyMuPDF | PDF document processing |
| python-docx | Word document processing |
| Plotly | Data visualization |
| pytest | Testing |

## 4. AI-Assisted Development

The following AI tools supported project development:

- **Google Antigravity:** Assisted with code generation, development, and debugging.
- **Claude:** Assisted with code review, problem-solving, and documentation.

All team members reviewed the generated code and documentation and are responsible for understanding and explaining their contributions.

## 5. Data Privacy and Security

- Synthetic demo data is used for testing and demonstration.
- Personal information is masked before sending content to external AI APIs.
- API keys are stored in environment variables and are not included in the source code.
- Human reviewers make all final approval and rejection decisions.

## 6. Transparency

InkWise AI aims to provide transparent and evidence-based brand governance. Findings cite the relevant guideline or approved fact. If sufficient supporting evidence is unavailable, the finding is marked **UNVERIFIED**.

