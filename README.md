# Pharmeazor

Pharmeazor is the medication information project for the RCR course brief.

## Current layout

- `ai_api/` — a clean FastAPI starter and a separate medication data collection folder.
- `frontend/` — the React/Vite interface.
- `backend/` — the existing project backend; it is kept separate from the new `ai_api/` folder.

The collector in `ai_api/data/collection/` gathers configured information for 40 target ingredients from Algerian ANPP, BDPM France, DailyMed, and Pharm'Net. It stores collected records and source metadata. ANPP is primary when available; foreign institutional sources are complementary; Pharm'Net is secondary. Interaction-section mentions are not a validated or complete interaction checker. Same-DCI relations are candidate links until ingredient, strength, and dosage form also match. The current `/ask` page does not read this collection.

## Run the new API

```powershell
cd ai_api
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set GROQ_API_KEY
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

The starter exposes `/`, `/health`, `/ask`, and `/docs`. Visit `/ask` for a simple browser form. It calls Groq directly and does not use the collected data.

Set the Groq model and key in `ai_api/.env`:

```dotenv
GROQ_API_KEY=your-groq-secret-key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=openai/gpt-oss-120b
```

`GROQ_MODEL` is the model name; `GROQ_API_KEY` is the secret. The `.env` file is ignored by Git and should remain server-side.

## Collect the data

From `ai_api/`, run `.\data\collection\collect.ps1` in PowerShell. It creates an isolated Python environment, installs collection dependencies, installs Chromium, and runs all collection steps configured in `collector.py`. See `ai_api/data/collection/README.md` for source coverage and limitations.
