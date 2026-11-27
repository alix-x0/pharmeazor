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
cd ..
python -m pip install -r ai_api/requirements.txt
if (!(Test-Path ai_api/.env)) { Copy-Item ai_api/.env.example ai_api/.env }
# Edit ai_api/.env and set GROQ_API_KEY and NEO4J_PASSWORD
python -m uvicorn ai_api.main:app --reload --host 127.0.0.1 --port 8001
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

## Neo4j knowledge graph storage

`GraphStorage` persists the pharmaceutical entities and relationships in Neo4j. Configure these values in `ai_api/.env` (the password must match the Neo4j server):

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=replace-with-a-local-password
NEO4J_DATABASE=neo4j
```

Start the local Neo4j 5 Community container from the repository root. Its `/data` and `/logs` directories use persistent Docker volumes:

```powershell
docker compose --env-file ai_api/.env -f ai_api/docker-compose.neo4j.yml up -d
```

Load the corpus into Neo4j. Ingestion creates the schema indexes, extracts each matching JSON monograph, and writes each document in an idempotent transaction. Re-running the command merges entities and accumulates relationship provenance. You can optionally filter by dossier, source, document type, or maximum document count:

```powershell
python -m ai_api.Augmentation.knowledge_graph.ingest_neo4j
python -m ai_api.Augmentation.knowledge_graph.ingest_neo4j --max-docs 10
python -m ai_api.Augmentation.knowledge_graph.ingest_neo4j --dossiers 02_ibuprofene --sources anpp
```

The API exposes `GET /kg/health`, `GET /kg/stats`, `GET /kg/entities/{entity_id}`, and `GET /kg/entities/{entity_id}/neighbors`. These routes return HTTP 503 when Neo4j cannot be reached. The existing `/kg/ontology` endpoint does not require a running database.

## Collect the data

The curated corpus and its inspection instructions are in [`../data/README.md`](../data/README.md). From the repository root, run `python data/inspect_corpus.py` to inspect it. The `/ask` endpoint currently does not load or retrieve from this corpus.

The script creates `ai_api/.venv` if needed, installs the collector dependencies and Playwright Chromium, then runs `collector.py`. To run the collector manually, follow `data/collection/README.md`. It stores downloads and extracted text under `data/collection/data/raw/` and `data/collection/data/text/`, writes a collection report, and compresses JSONL outputs.
