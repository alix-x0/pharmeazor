"""
Interaction Service

Orchestrates the two-layer interaction check:
  Layer 1 - DDInter exact lookup  (authoritative, always preferred)
  Layer 2 - CatBoost prediction   (fallback for pairs not in DB)

Handles drug name resolution (exact then fuzzy) and builds the full
response model used by the API route.
"""

from __future__ import annotations

import itertools
import logging
from typing import List

from app.core.config import settings
from app.models.schemas import (
    DrugMatch,
    InteractionResponse,
    InteractionSummary,
    PairResult,
)
from app.services.ddinter_service import ddinter_service
from app.services.ml_service import ml_service

logger = logging.getLogger(__name__)


def _level_to_risk(raw_level: str) -> str:
    """Map DDInter raw level string to unified risk label."""
    return settings.LEVEL_MAP.get(raw_level.strip().lower(), "UNKNOWN")


def _risk_color(risk: str) -> str:
    return settings.RISK_COLORS.get(risk, "#9E9E9E")


def resolve_drug_name(query: str) -> DrugMatch:
    """
    Try exact match first, then fall back to best fuzzy hit.
    If multi-word query fails, try matching individual words (for long Algerian generic names).
    Returns a DrugMatch with score=100 for exact hits.
    """
    clean_query = query.strip()
    if not clean_query:
        return DrugMatch(name=query, ddinter_id=None, score=0)

    # 1. Try exact/simple lookup
    info = ddinter_service.resolve_drug(clean_query)
    if info:
        return DrugMatch(name=info.name, ddinter_id=info.ddinter_id, score=100)

    # 2. Try fuzzy search on full query
    hits = ddinter_service.fuzzy_search(clean_query, limit=1)
    if hits and hits[0][2] >= settings.FUZZY_THRESHOLD:
        name, ddinter_id, score = hits[0]
        return DrugMatch(name=name, ddinter_id=ddinter_id, score=score)

    # 3. Fallback: Try word-by-word matching for long names (e.g. "ATORVASTATINE CALCIUM...")
    words = [w for w in clean_query.replace('/', ' ').replace(',', ' ').split() if len(w) > 3]
    best_match = None
    
    for word in words:
        word_hits = ddinter_service.fuzzy_search(word, limit=1)
        if word_hits and word_hits[0][2] > (best_match.score if best_match else 60):
            name, ddinter_id, score = word_hits[0]
            # Boost score slightly because it's a partial match that we are confident in
            best_match = DrugMatch(name=name, ddinter_id=ddinter_id, score=score)

    if best_match and best_match.score >= settings.FUZZY_THRESHOLD:
        return best_match

    return DrugMatch(name=clean_query, ddinter_id=None, score=0)


def check_interactions(drug_names: List[str]) -> InteractionResponse:
    """
    Full interaction check for a list of drug names.
    Returns a structured InteractionResponse ready for serialisation.
    """
    resolved: List[DrugMatch] = [resolve_drug_name(d) for d in drug_names]

    pairs: List[PairResult] = []
    for dm_a, dm_b in itertools.combinations(resolved, 2):
        pairs.append(_check_pair(dm_a, dm_b))

    _ORDER = {"DANGER": 0, "CAUTION": 1, "UNKNOWN": 2, "COMPATIBLE": 3, "NOT_IN_DB": 4}
    pairs.sort(key=lambda p: _ORDER.get(p.level, 9))

    summary = InteractionSummary(
        total_pairs=len(pairs),
        danger_count=sum(1 for p in pairs if p.level == "DANGER"),
        caution_count=sum(1 for p in pairs if p.level == "CAUTION"),
        compatible_count=sum(1 for p in pairs if p.level == "COMPATIBLE"),
        unknown_count=sum(1 for p in pairs if p.level == "UNKNOWN"),
        not_in_db_count=sum(1 for p in pairs if p.level == "NOT_IN_DB"),
    )

    return InteractionResponse(
        drugs_submitted=drug_names,
        resolved_drugs=resolved,
        pairs=pairs,
        summary=summary,
    )


def _check_pair(dm_a: DrugMatch, dm_b: DrugMatch) -> PairResult:
    """Return a PairResult for two resolved DrugMatch objects."""
    lower_a = dm_a.name.lower()
    lower_b = dm_b.name.lower()

    record = ddinter_service.lookup(lower_a, lower_b)

    if record is not None:
        risk = _level_to_risk(record.level)
        return PairResult(
            drug_a=dm_a.name,
            drug_b=dm_b.name,
            level=risk,
            source="database",
            confidence=None,
            color=_risk_color(risk),
            ddinter_id_a=record.ddinter_id_a,
            ddinter_id_b=record.ddinter_id_b,
            original_level=record.level,
        )

    if ml_service.is_loaded:
        risk, confidence = ml_service.predict(
            drug_a_name=dm_a.name,
            drug_b_name=dm_b.name,
            ddinter_id_a=dm_a.ddinter_id,
            ddinter_id_b=dm_b.ddinter_id,
        )
        return PairResult(
            drug_a=dm_a.name,
            drug_b=dm_b.name,
            level=risk,
            source="catboost_model",
            confidence=confidence,
            color=_risk_color(risk),
            ddinter_id_a=dm_a.ddinter_id,
            ddinter_id_b=dm_b.ddinter_id,
            original_level=None,
        )

    return PairResult(
        drug_a=dm_a.name,
        drug_b=dm_b.name,
        level="NOT_IN_DB",
        source="not_found",
        confidence=None,
        color=_risk_color("NOT_IN_DB"),
        ddinter_id_a=dm_a.ddinter_id,
        ddinter_id_b=dm_b.ddinter_id,
        original_level=None,
    )
