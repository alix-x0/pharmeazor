from fastapi import APIRouter, HTTPException

from app.models.schemas import HealthResponse, InteractionRequest
from app.services.ddinter_service import ddinter_service
from app.services.interaction_service import check_interactions
from app.services.ml_service import ml_service
from app.api.routes.explain_router import explain_interactions, ExplainRequest, ExplainResponse, InteractionPair
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    tags=["Meta"],
)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        drugs_in_db=ddinter_service.drug_count,
        interactions_in_db=ddinter_service.interaction_count,
        catboost_model_loaded=ml_service.is_loaded,
    )


@router.post(
    "/interactions/analyze",
    response_model=ExplainResponse,
    summary="Check interactions and generate clinical explanations",
    tags=["Interactions"],
)
async def analyze_interactions(body: InteractionRequest) -> ExplainResponse:
    """
    Accepts a list of drug names, checks interactions, and generates
    clinical explanations for all found pairs using BioMistral.
    Results include English explanations and Algerian Darija translations.
    """
    logger.info("analyze_interactions received body: %s", body.model_dump())
    if len(body.drugs) < 2:
        raise HTTPException(status_code=422, detail="At least 2 drugs required.")

    check_result = check_interactions(body.drugs)

    pairs_for_explain = [
        InteractionPair(
            drug_a=p.drug_a,
            drug_b=p.drug_b,
            level=p.level,
            original_level=p.original_level,
            source=p.source,
            confidence=p.confidence,
            color=p.color,
            ddinter_id_a=p.ddinter_id_a,
            ddinter_id_b=p.ddinter_id_b,
        )
        for p in check_result.pairs
    ]

    req = ExplainRequest(
        drugs_submitted=check_result.drugs_submitted,
        pairs=pairs_for_explain,
        user_role=body.user_role,
    )

    return await explain_interactions(req)
