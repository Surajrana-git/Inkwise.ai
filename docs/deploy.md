# Deploying to Streamlit Community Cloud (Step 9)

One-time setup, about 5 minutes. Free.

1. Go to **share.streamlit.io** and sign in with the GitHub account that owns the repo (Surajrana-git).
2. Click **Create app → Deploy a public app from GitHub**.
3. Repository: `Surajrana-git/inkwise.ai` · Branch: `main` · Main file path: `app/Home.py`.
4. **Advanced settings:**
   - Python version: 3.11 or 3.12
   - Secrets:
     ```toml
     GEMINI_API_KEY = "your-key"
     ```
5. Click **Deploy**. Copy the `*.streamlit.app` link into the README and the submission.

## How the app behaves online
- `engine/bootstrap.py` runs once per server process: it creates the SQLite tables and builds the brand-kit index.
- Streamlit Cloud wipes local files when the app restarts, so the database starts empty after a restart. That's expected for the demo.
- If `GEMINI_API_KEY` is missing or the embedding call fails, search falls back to keyword (BM25) ranking, so the app still works.
- Until `data/brand_kit/` has all three files, the app uses the small sample kit in `tests/fixtures/brand_kit` and shows a warning.
- If the log shows a ChromaDB "sqlite3 version" error, `pysqlite3-binary` in requirements.txt fixes it (it's installed on Linux only).

## Secrets locally
Copy `.env.example` to `.env` and add your key. `.env` is in `.gitignore`.
