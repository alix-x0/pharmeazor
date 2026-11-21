# Pharmeazor

## Mission

For this RCR milestone, Pharmeazor helps people in Algeria find and understand medicine-use and safety information in product documents for the project's 40 target ingredients. Answers should identify the relevant product and source, distinguish differences between documents, and abstain when the corpus does not support the answer. Pharmeazor does not diagnose, prescribe, or claim live price or stock information.

The evaluation mission is to measure whether retrieval from the corpus improves answers over the same LLM answering without passages. This describes the target system; the current `/ask` endpoint is a model-only baseline and does not read the corpus.

## Fixed test question

Use benchmark item `N1-01` as the canonical smoke question for the model-only run. Send only the question shown below. Keep the expected answer and scoring criteria out of the model prompt; they are evaluator-only in [the test specification](evaluation/mission_and_test_question.md).

> Chez un adulte de 60 kg, quelle est la dose journalière maximale de DOLIPRANE 1000 mg en règle générale, et dans quelle condition peut-on aller jusqu'à 4 g par jour ?

## Current layout

- `ai_api/` — a FastAPI model-only endpoint that calls the configured Groq model.
- `data/` — the curated medication corpus, audit files, loader, and source collection scripts.
- `frontend/` — the React/Vite interface.
- `backend/` — the Django API and user-data backend.

ANPP is the primary source where available; BDPM and DailyMed are complementary, and Pharm'Net is secondary. The corpus loader prepares chunks but no retrieval/indexing pipeline is currently connected to `/ask`. Mentions in interaction sections are not a validated or complete interaction checker. Same-DCI relations are candidate links until ingredient, strength, and dosage form also match.

## Run the new API

```powershell
python -m pip install -r ai_api/requirements.txt
Copy-Item ai_api/.env.example ai_api/.env
# Edit .env and set GROQ_API_KEY
python -m uvicorn ai_api.Retrieval.main:app --reload --host 127.0.0.1 --port 8001
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

The curated corpus is stored under `data/outputs_data/`. From the repository root, inspect the installed corpus with:

```powershell
python data/inspect_corpus.py
```

Source-specific collection utilities live in `data/scrapers/`; the API does not collect or retrieve from this corpus yet. See [`data/README.md`](data/README.md) for the corpus structure and loader.
