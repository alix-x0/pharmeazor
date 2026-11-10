from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal


class InteractionRequest(BaseModel):
    drugs: List[str] = Field(
        ...,
        min_length=2,
        description="List of drug names (at least 2) to check for interactions.",
        examples=[["Aspirin", "Ibuprofen", "Metformin"]],
    )
    user_role: Literal["patient", "pharmacist"] = Field("pharmacist", description="The role of the user requesting the analysis")

    @field_validator("drugs")
    @classmethod
    def at_least_two_drugs(cls, v: List[str]) -> List[str]:
        cleaned = [d.strip() for d in v if d.strip()]
        if len(cleaned) < 2:
            raise ValueError("At least 2 non-empty drug names are required.")
        return cleaned


class DrugMatch(BaseModel):
    name: str
    ddinter_id: Optional[str] = None
    score: int = Field(description="Match score 0-100")


class PairResult(BaseModel):
    drug_a: str
    drug_b: str
    level: str = Field(description="DANGER | CAUTION | COMPATIBLE | UNKNOWN | NOT_IN_DB")
    source: str = Field(description="'database' | 'catboost_model' | 'not_found'")
    confidence: Optional[float] = Field(
        None, description="Model confidence [0-1] when source is catboost_model"
    )
    color: str
    ddinter_id_a: Optional[str] = None
    ddinter_id_b: Optional[str] = None
    original_level: Optional[str] = Field(
        None, description="Raw level string from DDInter (Major/Moderate/Minor/Unknown)"
    )


class InteractionSummary(BaseModel):
    total_pairs: int
    danger_count: int
    caution_count: int
    compatible_count: int
    unknown_count: int
    not_in_db_count: int


class InteractionResponse(BaseModel):
    drugs_submitted: List[str]
    resolved_drugs: List[DrugMatch]
    pairs: List[PairResult]
    summary: InteractionSummary


class HealthResponse(BaseModel):
    status: str
    version: str
    drugs_in_db: int
    interactions_in_db: int
    catboost_model_loaded: bool
