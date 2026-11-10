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

# INKWISE AI

Brand governance that reviews content **before** it is published. Every finding cites the exact guideline or approved fact behind it, or is marked **UNVERIFIED**. Humans make every decision.

**Team DECODIANS** · CodeTitans India 2026 (Inkloom AI Hackathon)

## Team Members

| Member | Role |
|---|---|
| Suraj Kumar (Lead) | Backend |
| Riyana S | AI / ML |
| Aashi Yadav | Frontend |
| Pritha S | Product / Research |

## Project Problem

Brands need to ensure that their marketing content follows brand guidelines before publishing. Manual checking takes time and may miss incorrect claims, outdated facts, and inconsistent brand messaging.

InkWise AI addresses this problem by reviewing content using AI and rule-based checks. It identifies potential issues and provides supporting evidence from brand guidelines or approved facts.

## Live Application Link

**Live Demo:** [Open InkWise AI](https://inkwiseai-jobnp9jkgfoutv5jeuvvs7.streamlit.app/)

## Demo Login Credentials

| Username | Role |
|---|---|
| `asha` | Creator |
| `meera` | Manager |

Select the appropriate demo user and role in the application.

## How InkWise AI Works

1. **Content Submission:** Creator enters marketing content into the application.
2. **Content Review:** AI and rule-based checks analyze the submitted content.
3. **Finding Generation:** The system identifies potential brand guideline violations and displays supporting evidence.
4. **Finding Management:** Creator can accept, edit, or reject individual findings.
5. **Approval Request:** Reviewed content is sent to the Manager for approval.
6. **Manager Review:** Manager approves or rejects the submission with comments.
7. **History and Audit:** Review activities, decisions, and versions are recorded for tracking.

## Run Locally

```bash
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Create environment file and add your Gemini API key
cp .env.example .env

# Run application
streamlit run app/Home.py

# Run tests
pytest
```

## Project Layout

```text
engine/             Pure Python review engine (no UI)
  schemas.py        Shared data contracts (Finding, Guideline, Fact, Term)
  knowledge.py      Brand kit loading and ChromaDB search
  review.py         Gemini review with citations
  rules.py          Glossary, expired-fact and readability checks
  redact.py         Masks personal data before API calls
  workflow.py       Roles, approvals, versions and SQLite audit log

app/                Streamlit user interface
data/brand_kit/     Synthetic demo brand "Lumora"
eval/               Labelled evaluation dataset and evaluation script
docs/               Architecture, disclosures and user testing
```

## Application Screenshots

Add the following screenshots of the live application:

1. Home Dashboard
2. Review Page with Findings
3. Expanded Finding with Evidence
4. Approvals Page
5. History Page

## Evaluation Results

InkWise AI is evaluated using a labelled development and test dataset.

### Rules-only Baseline

| Metric | Result |
|---|---:|
| Precision | 96.1% |
| Recall | 51.0% |
| Citation Accuracy | 97.3% |

### Rules + AI Evaluation

Add the final evaluation results from `eval/results.md` after the evaluation is completed.

Include a comparison of:
- Rules-only baseline
- Rules + AI system

**Note:** The baseline values above are not the final Rules + AI results.

## Three Improvements

The following improvements were identified in Round 2 for delivery in Round 3:

1. **Evidence-grounded findings:** Every finding cites its supporting guideline or approved fact, or is marked UNVERIFIED. Measured using citation accuracy.

2. **Fact freshness:** Approved facts include owners and expiry dates so that outdated claims can be identified.

3. **Guideline Clarity Insights:** Reviewer overrides and disagreements help identify unclear guidelines and repeated mistakes.

## Future Roadmap

- **Visual Brand Inspector:** Extend content review to images and visual brand consistency.
- **Voice Input:** Allow users to submit content through voice input.
- **Improved Fact Freshness:** Strengthen monitoring of outdated and expired approved facts.
- **Guideline Insights:** Improve the identification of unclear guidelines and recurring review issues.

## Disclosures

For information about AI models, APIs, datasets, libraries, privacy practices, and AI-assisted development, see [docs/disclosures.md](docs/disclosures.md).

## User Testing

User testing details, feedback, identified issues, and improvements are documented in [docs/user_testing.md](docs/user_testing.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Disclosures](docs/disclosures.md)
- [User Testing](docs/user_testing.md)
- [Evaluation Results](eval/results.md)

