# Pharmeazor AI API

`POST /ask` is the LLM-only baseline for the Pharmeazor evaluation. It sends the question directly to the configured Groq model and does not read the medicine corpus or retrieve source passages. The project mission and fixed smoke question are documented in [`evaluation/mission_and_test_question.md`](../evaluation/mission_and_test_question.md).

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
  -Body '{"question":"Chez un adulte de 60 kg, quelle est la dose journalière maximale de DOLIPRANE 1000 mg en règle générale, et dans quelle condition peut-on aller jusqu\u0027à 4 g par jour ?"}'
```

The JSON response contains `question`, `answer`, and `model`. For an LLM-only test, send only the question; never include the expected answer or rubric. The model answers from its own knowledge and may not provide verifiable corpus citations. The browser form shows the answer on the same page.

## Collect the data

The curated corpus and its inspection instructions are in [`../data/README.md`](../data/README.md). From the repository root, run `python data/inspect_corpus.py` to inspect it. The `/ask` endpoint currently does not load or retrieve from this corpus.

The script creates `ai_api/.venv` if needed, installs the collector dependencies and Playwright Chromium, then runs `collector.py`. To run the collector manually, follow `data/collection/README.md`. It stores downloads and extracted text under `data/collection/data/raw/` and `data/collection/data/text/`, writes a collection report, and compresses JSONL outputs.
