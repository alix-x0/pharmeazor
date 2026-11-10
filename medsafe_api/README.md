# MedSafe API

Drug-drug interaction checker for the Algerian market. Given a list of drug names, the API checks for interactions against the DDInter database, runs a CatBoost ML fallback for unknown pairs, generates clinical explanations via BioMistral (in English), and translates them to Algerian Darija via OpenAI.

---

## Table of Contents

- [Requirements](#requirements)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [Endpoints](#endpoints)
  - [GET /api/v1/health](#get-apiv1health)
  - [POST /api/v1/interactions/analyze](#post-apiv1interactionsanalyze)
  - [POST /api/v1/conversation/chat](#post-apiv1conversationchat)
  - [GET /api/v1/conversation/topics](#get-apiv1conversationtopics)

---

## Requirements

- Python 3.10+
- NVIDIA GPU with 6+ GB VRAM (for BioMistral GPU inference)
- CUDA 11.8+ and cuDNN installed

---

## Setup

**1. Clone the repository and create a virtual environment:**

```bash
git clone https://github.com/alixxxx-x/hackathon.git
cd medsafe_api
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS
```

**2. Install dependencies:**

```bash
pip install -r requirements.txt
```

> For GPU-accelerated inference, install `llama-cpp-python` with CUDA support:
> ```bash
> pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
> ```

**3. Download DDInter CSV files:**

Download the interaction CSV files from [DDInter](https://ddinter.scbdd.com/) and place them in `app/data/`. The files should be named `ddinter_downloads_code_*.csv`.

**4. CatBoost model (automatic):**

The ML fallback model artifacts are downloaded automatically from [Laufey/Catboost-DDinter](https://huggingface.co/Laufey/Catboost-DDinter) on first startup if they are not already present in `ml/artifacts/`. No manual action is required.

**5. Configure environment variables:**

Copy `.env.example` to `.env` and fill in your values:

```bash
copy .env.example .env
```

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key for Darija translation | `None` (translation disabled) |

All other settings are in `app/core/config.py` and can be overridden via environment variables.

---

## Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On first startup, BioMistral (~4.5 GB GGUF model) is downloaded from HuggingFace into `app/models/`. Subsequent startups use the cached file.

Interactive API docs are available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Endpoints

### GET /api/v1/health

Returns server status and model load state.

**Response:**

```json
{
  "status": "ok",
  "version": "1.0.0",
  "drugs_in_db": 1842,
  "interactions_in_db": 118417,
  "catboost_model_loaded": true
}
```

---

### POST /api/v1/interactions/analyze

The main endpoint. Accepts a list of drug names, checks all pairwise interactions, generates a clinical English explanation for each pair using BioMistral, and translates each explanation to Algerian Darija.

**Request body:**

```json
{
  "drugs": ["Warfarin", "Aspirin", "Metformin"]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `drugs` | array of strings | Yes | At least 2 drug names |

**Response:**

```json
{
  "drugs_submitted": ["Warfarin", "Aspirin", "Metformin"],
  "explained_pairs": [
    {
      "drug_a": "Warfarin",
      "drug_b": "Aspirin",
      "level": "DANGER",
      "original_level": "Major",
      "color": "#D32F2F",
      "medical_explanation": "Drug A and Drug B together significantly increase bleeding risk...",
      "darija_explanation": "هاد الدواوين مع بعضهم يزيدو خطر النزيف...",
      "darija_risk_label": "خطر كبير",
      "translation_success": true,
      "translation_error": null
    }
  ]
}
```

**Interaction levels:**

| Level | Meaning |
|---|---|
| `DANGER` | Major interaction - generally avoid |
| `CAUTION` | Moderate interaction - monitor closely |
| `COMPATIBLE` | Minor or no significant interaction |
| `UNKNOWN` | Pair is in DB but classification is unknown |
| `NOT_IN_DB` | Pair not found in DB and ML model not available |

**Source field:**

| Source | Meaning |
|---|---|
| `database` | Result from DDInter lookup |
| `catboost_model` | Result from ML fallback (includes `confidence` score) |
| `not_found` | Neither source had data |

---

### POST /api/v1/conversation/chat

Multi-turn pharmacist training assistant powered by BioMistral. Replies in French. Session history is stored server-side in SQLite.

**Request body:**

```json
{
  "message": "Explain the mechanism of warfarin.",
  "session_id": null,
  "max_tokens": 512,
  "temperature": 0.4
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | Yes | The user's message |
| `session_id` | string | No | Omit to start a new session; provide to continue |
| `max_tokens` | integer | No | 64-1024, default 512 |
| `temperature` | float | No | 0.0-1.0, default 0.4 |

**Response:**

```json
{
  "reply": "La warfarine est un anticoagulant oral...",
  "session_id": "3f1a2b4c-...",
  "turn": 1
}
```

Save the `session_id` from the first response and pass it in subsequent requests to continue the same conversation.