# Disclosures

Kept up to date by every member during the build.

## AI models and APIs
- **Google Gemini API** (free tier): reviews content and creates embeddings. Free-tier prompts may be used by Google to improve its products, so the demo uses synthetic data only and masks personal data before every call. Production setting: paid tier.
- **Primary model:** `gemini-3.5-flash-lite`.
- **Backup models:** Gemini Flash models used as fallbacks.
- **Gemini Embeddings:** Used for semantic search across brand guidelines and approved facts.

## Data
- **Lumora brand kit**: fictional, written by the team.
- **Evaluation set**: synthetic samples generated with Adaption Labs, labels checked by hand.
- The evaluation datasets are generated using `eval/build_dataset.py`.
- Initial datasets are stored in `eval/raw/` and were not used for evaluation scoring.

## Libraries
Streamlit, Pydantic, google-genai, ChromaDB, python-dotenv, textstat, PyMuPDF, python-docx, Plotly, pytest.

## AI-assisted development
- Google Antigravity and Claude were used to help write and review code and documents. Every member reviewed and understands the code they committed.
- Initial repository skeleton (folder structure, schemas, interface stubs) was drafted with Claude and reviewed by Suraj.

## Templates / previously written code
None.
