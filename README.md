# InkWise AI

**Brand governance that checks content before it is published, and shows its evidence.**

Every finding points to the exact brand guideline, approved fact or glossary term it relates to, or is clearly marked **UNVERIFIED**. InkWise explains each issue, suggests a fix that keeps the writer's intent, and leaves every decision to a human.

**Live demo:** https://inkwiseai-jobnp9jkgfoutv5jeuvvs7.streamlit.app/

Team **DECODIANS** · CodeTitans India 2026 (Inkloom AI Hackathon)

| Member | Role | Built |
|---|---|---|
| Suraj Kumar (Lead) | Backend | Knowledge base, review workflow and audit log, deployment, reliability |
| Riyana S | AI / ML | Gemini review engine with citations, rule checks, privacy masking, evaluation |
| Aashi Yadav | Frontend | Streamlit app: review screen with inline highlights, approvals, history, knowledge base |
| Pritha S | Product / Research | Lumora brand kit, user testing, documentation |

---

## The problem

Organisations publish content through many employees, agencies and AI tools. Wrong claims, outdated statistics, inconsistent product names and off-brand language slip through, and manual review is slow and inconsistent. Generic tone checkers say *that* something is off, but rarely *why* or *according to which rule*.

## What InkWise does

1. **Review**: a creator pastes content. InkWise checks it against the brand kit: guidelines, facts with owners and expiry dates, and approved terminology.
2. **Explain**: each issue is highlighted in the text, with the source it relates to, why it matters, a suggested fix and a confidence score. Anything no approved source supports is marked **UNVERIFIED** instead of guessed.
3. **Decide**: the creator accepts, edits or rejects each finding, then sends the content for approval.
4. **Approve**: a manager or reviewer approves or requests changes, with a comment. Nobody can approve their own content.
5. **Track**: every version, decision and approval is saved in an audit log. Reviewer decisions are recorded per guideline, the base for spotting unclear guidelines (Round 3).

### What makes it different
- **No source, no claim:** findings cite their source; unsupported claims are marked UNVERIFIED.
- **Fact freshness:** approved facts expire, so outdated numbers ("2 million users") are caught, even when reworded ("2M").
- **Rules + AI:** exact checks (banned terms, expired facts, readability) are deterministic; judgement calls (claims, tone, messaging, accessibility) go to Gemini.
- **Privacy first:** names, phone numbers, emails and ID numbers are masked before any text is sent to an AI service.
- **Reliable:** if a Gemini model is overloaded, InkWise switches to a backup model. If AI is unavailable, the user still gets rule checks and a clear warning.

## Try the demo

Open the live link. In the sidebar, type any name and pick a role (there is no password in the demo):

| Name | Role | Try this |
|---|---|---|
| `asha` | Creator | Review → paste the sample below → accept or edit findings → **Send for approval** |
| `meera` | Manager | Approvals → approve or reject with a comment → History |

Use two different names: the creator cannot approve their own content.

**Sample text:**
> Join 2 million happy users of LumoraPay! We are India's fastest payment app and every transfer arrives instantly. Tap the green button above to sign up now or miss your chance.

Expected: expired fact (F01), banned product name (T01), unsupported claims (G07), colour-only instruction (G15), pushy tone (G03).

All demo data is synthetic: **Lumora** is a fictional fintech brand created by the team.

## Screenshots

1.Home Dashboard
<img width="1600" height="757" alt="image" src="https://github.com/user-attachments/assets/82a10684-9c0d-4462-be1c-1ec3cfb90b7f" />

2.Review Page with Findings
<img width="1600" height="763" alt="image" src="https://github.com/user-attachments/assets/8fb9135e-de75-4299-b712-e625156fb3cf" />

3.Approvals Page
<img width="1600" height="757" alt="image" src="https://github.com/user-attachments/assets/4a572241-7221-4d2a-95e0-96595ee00889" />

4.History Page
<img width="1600" height="762" alt="image" src="https://github.com/user-attachments/assets/9aeeab82-71c1-483d-ad9a-ddb55fd22c66" />

5.Knowledge Base
<img width="1600" height="761" alt="image" src="https://github.com/user-attachments/assets/203d4d24-2b3a-4b32-89ed-afe52f1fb822" />

## Evaluation

We measure InkWise on a labelled test set of 100 samples (25 clean, 75 with 1–3 planted errors), where every label is tied to a real brand-kit ID. See [eval/README.md](eval/README.md).

| Setup | Precision | Recall | Citation accuracy | Clean samples wrongly flagged |
|---|---:|---:|---:|---:|
| Rules only (no AI) | 96.1% | 51.0% | 97.3% | 1 / 25 |
| Rules + AI | 100.0% | 1.2% | 100.0% | 0 / 20 |

Rules alone catch terminology (50/50) and expired facts (23/26). The AI review adds claims, tone, accessibility and messaging.

Run it yourself: `python eval/run_eval.py --split test` (add `--rules-only` for the baseline).

## Architecture

A pure Python engine (`engine/`) with a Streamlit UI (`app/`) on top. Full design, key decisions and limitations: [docs/architecture.md](docs/architecture.md).

```text
engine/
  schemas.py     data contracts: Finding, Guideline, Fact, Term, ReviewResult
  knowledge.py   brand kit loading and search (ChromaDB + Gemini embeddings, keyword fallback)
  redact.py      masks personal data before any API call
  rules.py       banned terms, expired facts, readability
  review.py      Gemini review with citations, backup models, validation
  workflow.py    roles, versions, decisions, approvals, audit log (SQLite)
app/             Streamlit pages: Home, Review, Approvals, History, Knowledge Base
data/brand_kit/  Lumora guidelines, facts and glossary (synthetic)
eval/            labelled dev/test sets and evaluation script
docs/            architecture, deployment, disclosures, user testing
tests/           55 automated tests
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # add GEMINI_API_KEY (optional: rule checks work without it)
streamlit run app/Home.py
pytest                               # 55 tests
```

## Three improvements for Round 3

1. **Evidence-grounded findings:** every finding cites its source or is marked UNVERIFIED; measured by citation accuracy.
2. **Fact freshness:** approved facts with owners and expiry dates; outdated claims are caught and the owner is named.
3. **Guideline Clarity Insights:** reviewer accept, edit and reject decisions show which guidelines are unclear and which mistakes repeat.

## Roadmap

- **Round 3:** the three improvements above, plus a **Visual Brand Inspector** (brand-colour and contrast checks on images, logo presence) and PDF/DOCX upload.
- **After the event:** voice input, CMS and Slack integrations, a managed database for production.

## User testing

Five review-and-approval workflows on the live app: [docs/docs/user_testing.md](docs/docs/user_testing.md).

## Responsible design and disclosures

Synthetic data only; personal data masked before AI calls; AI use disclosed in the app; humans approve every change; every action logged. APIs, models, datasets, libraries and AI-assisted development: [docs/disclosures.md](docs/disclosures.md).
