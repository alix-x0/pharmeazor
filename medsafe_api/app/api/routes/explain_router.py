"""
Explain Router

POST /api/v1/explain
Accepts interaction check output and returns per-pair medical explanations
from BioMistral, with Algerian Darija translations.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import asyncio
from typing import List, Optional, Literal
import logging

from app.services.biomistral_service import generate_explanation
from app.services.translation_service import translate_to_darija, translate_to_french

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/explain", tags=["Explanation"])


class InteractionPair(BaseModel):
    drug_a: str
    drug_b: str
    level: str
    original_level: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[float] = None
    color: Optional[str] = None
    ddinter_id_a: Optional[str] = None
    ddinter_id_b: Optional[str] = None


class ExplainRequest(BaseModel):
    """
    Mirrors the interaction engine output.
    Pass the full /interactions/analyze intermediate result or build manually.
    """
    drugs_submitted: List[str] = Field(default_factory=list)
    pairs: List[InteractionPair]
    user_role: Literal["patient", "pharmacist"] = Field("pharmacist", description="The role of the user requesting the explanation")


class PairExplanation(BaseModel):
    drug_a: str
    drug_b: str
    level: str
    original_level: Optional[str] = None
    color: Optional[str] = None
    medical_explanation: str
    darija_explanation: Optional[str] = None
    french_explanation: Optional[str] = None
    darija_risk_label: Optional[str] = None
    translation_success: Optional[bool] = None
    translation_error: Optional[str] = None


class ExplainResponse(BaseModel):
    drugs_submitted: List[str]
    explained_pairs: List[PairExplanation]


@router.post(
    "",
    response_model=ExplainResponse,
    summary="Generate medical explanations for interaction pairs",
)
async def explain_interactions(body: ExplainRequest) -> ExplainResponse:
    """
    For each interaction pair, calls BioMistral to produce a medical advisory
    focused on mechanism and vulnerable populations, then translates to Darija.
    Pairs with level UNKNOWN or NOT_IN_DB receive a static note instead.
    """
    if not body.pairs:
        raise HTTPException(status_code=400, detail="No interaction pairs provided.")

    partial_results = []
    logger.info("Explaining interactions for role: %s", body.user_role)

    for pair in body.pairs:
        if pair.level in ("UNKNOWN", "NOT_IN_DB"):
            explanation = (
                "No sufficient pharmacological data is available for this combination. "
                "Consult a clinical pharmacist or physician before co-administering."
            )
        else:
            try:
                explanation = generate_explanation(
                    drug_a=pair.drug_a,
                    drug_b=pair.drug_b,
                    level=pair.level,
                    original_level=pair.original_level or pair.level.capitalize(),
                    role=body.user_role,
                )
            except Exception as exc:
                import traceback
                logger.error(
                    "BioMistral inference failed for %s+%s: %s\n%s",
                    pair.drug_a,
                    pair.drug_b,
                    exc,
                    traceback.format_exc()
                )
                explanation = _fallback_explanation(pair.level)

        partial_results.append({"pair": pair, "explanation": explanation})

    async def _translate_item(item: dict) -> PairExplanation:
        pair = item["pair"]
        eng_exp = item["explanation"]
        
        # Parallel translation
        darija_task = translate_to_darija(eng_exp, pair.level)
        french_task = translate_to_french(eng_exp)
        
        darija_res, french_res = await asyncio.gather(darija_task, french_task)
        
        return PairExplanation(
            drug_a=pair.drug_a,
            drug_b=pair.drug_b,
            level=pair.level,
            original_level=pair.original_level,
            color=pair.color,
            medical_explanation=eng_exp,
            darija_explanation=darija_res["darija_text"],
            french_explanation=french_res["french_text"],
            darija_risk_label=darija_res["risk_label"],
            translation_success=darija_res["success"],
            translation_error=darija_res["error"],
        )

    tasks = [_translate_item(item) for item in partial_results]
    explained = await asyncio.gather(*tasks)

    return ExplainResponse(
        drugs_submitted=body.drugs_submitted,
        explained_pairs=explained,
    )


def _fallback_explanation(level: str) -> str:
    """Static fallback if BioMistral inference fails for a pair."""
    fallbacks = {
        "DANGER": (
            "This combination carries a high risk of serious adverse effects. "
            "It should generally be avoided. Consult a physician or pharmacist "
            "immediately before taking these medications together. "
            "Elderly patients and those with kidney or liver problems are at highest risk."
        ),
        "CAUTION": (
            "This combination may cause moderate side effects in some patients. "
            "Monitor for unusual symptoms and seek medical advice if concerned. "
            "Patients with chronic conditions or those taking multiple medications "
            "should be especially cautious."
        ),
        "COMPATIBLE": (
            "No significant interaction is expected under normal conditions. "
            "Continue as directed and report any unexpected symptoms to your pharmacist."
        ),
    }
    return fallbacks.get(level, fallbacks["CAUTION"])
