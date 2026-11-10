# 🇩🇿 Darija Drug Interaction Translator

Translates drug interaction descriptions from English → Algerian Darija using the OpenAi api.

---

## What this module does

1. Receives an English drug interaction description (from DDinter via the team backend)
2. Calls the OpenAi with a carefully crafted Darija prompt
3. Returns the Darija translation + a human-readable risk label in Arabic
4. Exposes everything as a simple REST API that could be called

---

## Folder structure

```
translation-api/
├── src/
│   ├── translator.py   ← core logic, import this in your code
│   └── api.py          ← FastAPI server (optional, for team integration)
├── tests/
│   └── test_translator.py
├── demo.py             ← quick interactive test
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup 

### 1. get ur openAi api key


### 2. Clone / download this folder onto your computer

### 3. Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Set your API key

```bash
# Copy the example
cp .env.example .env

# Open .env and replace the placeholder with your actual key
# OPENAI_API_KEY = ......
```

### 6. Run the quick demo

```bash
python demo.py
```

Paste any English drug interaction description and it will print the Darija translation.

### 7. Run the tests (uses real API calls)

```bash
python tests/test_translator.py
```

This runs 4 realistic DDinter-style examples and prints the Darija output.

---

## Starting the API server

If you want to call this as an HTTP service:

```bash
cd src
python api.py
```

The server starts at **http://localhost:8000**

### API docs (auto-generated)
Open http://localhost:8000/docs in your browser — full interactive Swagger UI.

---

## How to call the API 

### cURL

```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Concurrent use increases risk of bleeding.",
    "risk_level": "major",
    "drug1": "Aspirin",
    "drug2": "Warfarin"
  }'
```

### JavaScript (fetch)

```javascript
const response = await fetch("http://localhost:8000/translate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    description: "Concurrent use increases risk of bleeding.",
    risk_level: "major",
    drug1: "Aspirin",
    drug2: "Warfarin"
  })
});

const data = await response.json();
console.log(data.darija_text);   // الترجمة بالدارجة
console.log(data.risk_label);    // ⛔ خطر كبير
```

### Python (requests)

```python
import requests

res = requests.post("http://localhost:8000/translate", json={
    "description": "Taking ibuprofen with aspirin increases stomach bleeding risk.",
    "risk_level": "moderate"
})
print(res.json()["darija_text"])
```

---

## How to use `translator.py` directly (no server needed)

```python
from src.translator import translate_to_darija, translate_interaction_result

# Option 1: translate a plain string
result = translate_to_darija(
    english_text="Avoid combining these medications. Risk of kidney failure.",
    risk_level="major"
)
print(result["darija_text"])
print(result["risk_label"])   # ⛔ خطر كبير

# Option 2: enrich your team's interaction dict
interaction = {
    "drug1": "Metformin",
    "drug2": "Ibuprofen",
    "risk_level": "moderate",
    "description": "NSAIDs may reduce metformin effectiveness and harm kidneys."
}
enriched = translate_interaction_result(interaction)
# enriched now has all original keys PLUS:
# enriched["darija_description"]
# enriched["darija_risk_label"]
# enriched["translation_success"]
# enriched["translation_error"]
```

---

## Response format

```json
{
  "darija_text": "...",           // Algerian Darija translation
  "risk_label": "⛔ خطر كبير",  // human-readable risk in Arabic
  "risk_level": "major",          // original risk level
  "success": true,
  "error": null
}
```

Risk labels:
| Level    | Label            |
|----------|------------------|
| major    | ⛔ خطر كبير     |
| moderate | ⚠️ خطر متوسط   |
| minor    | ℹ️ خطر خفيف    |
| unknown  | ❓ ما عرفناش    |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` with venv active |
| Translation is in MSA (فصحى) not Darija | The prompt is tuned for Darija — if results feel off, open `translator.py` and adjust `SYSTEM_PROMPT` |
| API server won't start | Make sure you're running from the `src/` folder: `cd src && python api.py` |

---

