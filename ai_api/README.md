# Pharmeazor AI API

Simple FastAPI starter for the project. `POST /ask` sends a question directly to Groq and returns its answer. It does not read the collected medicine data, which is kept separately under `data/collection/`.

## Groq settings

Copy `.env.example` to `.env` in this folder, then add your Groq API key:

```dotenv
GROQ_API_KEY=your-groq-secret-key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=openai/gpt-oss-120b
```

The model name is not a key. Keep the secret only in `ai_api/.env`; that file is Git-ignored.

## Run

```powershell
cd ai_api
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set GROQ_API_KEY
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

The health route reports the configured model and whether the key is present. It never returns the key. Open `http://127.0.0.1:8001/` or `/ask` for the question form, or `http://127.0.0.1:8001/docs` to use the POST endpoint interactively.

You can also send a request from PowerShell:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8001/ask `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"question":"What is FastAPI?"}'
```

The JSON response contains `question`, `answer`, and `model`. The assistant answers from its model knowledge and does not provide corpus citations. The browser form shows the answer on the same page.

## Collect the data

Run one command from the `ai_api` folder to set up the collection environment and collect the configured source data:

```powershell
.\data\collection\collect.ps1
```

The script creates `ai_api/.venv` if needed, installs the collector dependencies and Playwright Chromium, then runs `collector.py`. To run the collector manually, follow `data/collection/README.md`. It stores downloads and extracted text under `data/collection/data/raw/` and `data/collection/data/text/`, writes a collection report, and compresses JSONL outputs.
