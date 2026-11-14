# Deploying to Streamlit Community Cloud

One-time setup, about 5 minutes. Free.

1. Go to **share.streamlit.io** and sign in with the GitHub account that owns the repo (Surajrana-git).
2. **Create app → Deploy a public app from GitHub.**
3. Repository: `Surajrana-git/Inkwise.ai` · Branch: `main` · Main file path: `app/Home.py`.
4. **Advanced settings**
   - Python version: 3.11 or 3.12
   - Secrets:
     ```toml
     GEMINI_API_KEY = "your-key"
     # optional
     # GEMINI_MODEL = "gemini-flash-latest"
     # INKWISE_DEMO_PASSWORD = "demo123"
     ```
5. **Deploy.** Put the `*.streamlit.app` link in the README and the submission.

After every merge to `main`: open the app menu → **Reboot app**, then run the smoke test in an incognito window
as `asha`, `meera` and `ravi` (password `demo123`).

## How the app behaves online
- `engine/bootstrap.py` runs once per server process (called from `app/services.ensure_started()`):
  it creates the SQLite tables, the three demo accounts, builds the brand-kit index, applies any stored
  fact renewals and accepted guideline rewordings, and loads demo data if the database is empty.
- Streamlit Cloud wipes local files when the app restarts. The database starts empty after a restart and
  `engine/seed.py` loads two weeks of clearly labelled demo activity again, so History, Approvals and
  Insights are never blank for a judge. Renewals and rewordings made before a restart are lost with it;
  this is stated on the Home page and in the limitations.
- Without `GEMINI_API_KEY`, or when every Gemini model is busy, the app shows rule checks only
  (terminology, expired facts, readability) with a clear banner. Search falls back to keyword (BM25).
- Gemini is called one request at a time per server process, and identical texts are served from a cache,
  so a judge clicking Run twice does not spend quota twice.
- If the log shows a ChromaDB "sqlite3 version" error, `pysqlite3-binary` in requirements.txt fixes it
  (installed on Linux only).

## Secrets locally
Copy `.env.example` to `.env` and add your key. `.env` is in `.gitignore`; never commit it.
