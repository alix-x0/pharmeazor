"""
FastAPI server — exposes the Darija translator as a REST endpoint.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

from translator import translate_to_darija, translate_interaction_result

app = FastAPI(
    title="Darija Drug Interaction Translator",
    description="Translates DDinter drug interaction descriptions to Algerian Darija",
    version="1.0.0",
)

# Allow requests from any origin during the hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    description: str
    risk_level:  Optional[str] = None   # 'major' | 'moderate' | 'minor'
    drug1:       Optional[str] = None
    drug2:       Optional[str] = None


class TranslateResponse(BaseModel):
    darija_text:  str
    risk_label:   str
    risk_level:   str
    success:      bool
    error:        Optional[str] = None


class InteractionRequest(BaseModel):
    """Accepts the full interaction object your backend produces."""
    description: str
    risk_level:  Optional[str] = None
    drug1:       Optional[str] = None
    drug2:       Optional[str] = None
    # Any extra fields from your backend are forwarded as-is
    class Config:
        extra = "allow"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "darija-translator"}


@app.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    """
    Translate a single description to Darija.

    Example body:
    {
      "description": "Concurrent use may increase the risk of bleeding.",
      "risk_level": "major",
      "drug1": "Aspirin",
      "drug2": "Warfarin"
    }
    """
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="description cannot be empty")

    result = translate_to_darija(req.description, req.risk_level)
    return TranslateResponse(**result)


@app.post("/translate/interaction")
def translate_interaction(req: InteractionRequest):
    """
    Accepts your team's full interaction payload and enriches it with Darija fields.
    Returns the original fields PLUS:
      - darija_description
      - darija_risk_label
      - translation_success
      - translation_error
    """
    interaction_dict = req.model_dump()
    enriched = translate_interaction_result(interaction_dict)
    return enriched


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
