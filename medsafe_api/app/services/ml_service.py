"""
ML Service - CatBoost Interaction Predictor

Used as a fallback when a drug pair is not found in the DDInter database.
If model artifacts are missing locally, they are downloaded automatically from
HuggingFace (Laufey/Catboost-DDinter).

Feature vector per pair:
  - drug_a_id_num   - numeric part of DDInterID_A (e.g. DDInter576 -> 576)
  - drug_b_id_num   - numeric part of DDInterID_B
  - drug_a_name     - categorical string (CatBoost handles natively)
  - drug_b_name     - categorical string
  - name_len_diff   - abs(len(name_a) - len(name_b))
  - id_diff         - abs(id_num_a - id_num_b)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from huggingface_hub import hf_hub_download

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from catboost import CatBoostClassifier
    import joblib
    _CATBOOST_AVAILABLE = True
except ImportError:
    _CATBOOST_AVAILABLE = False
    logger.warning("catboost or joblib not installed - ML fallback disabled.")


HF_REPO = "Laufey/Catboost-DDinter"

_ID_RE = re.compile(r"\d+")


def _id_to_num(ddinter_id: str) -> int:
    m = _ID_RE.search(ddinter_id or "")
    return int(m.group()) if m else 0


def _ensure_artifact(artifacts_dir: Path, filename: str) -> Path:
    """Return the local path to an artifact, downloading it from HuggingFace if absent."""
    local_path = artifacts_dir / filename
    if not local_path.exists():
        logger.info("Artifact %s not found locally. Downloading from %s.", filename, HF_REPO)
        hf_hub_download(
            repo_id=HF_REPO,
            filename=filename,
            local_dir=str(artifacts_dir),
            local_dir_use_symlinks=False,
        )
        logger.info("Downloaded %s to %s.", filename, artifacts_dir)
    return local_path


class MLService:
    def __init__(self) -> None:
        self._model: Optional["CatBoostClassifier"] = None
        self._label_encoder = None
        self._drug_encoder = None
        self._loaded = False

    def load(self) -> None:
        if not _CATBOOST_AVAILABLE:
            return

        artifacts_dir: Path = settings.ML_ARTIFACTS_DIR
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        try:
            model_path = _ensure_artifact(artifacts_dir, settings.CATBOOST_MODEL_FILE)
            le_path = _ensure_artifact(artifacts_dir, settings.LABEL_ENCODER_FILE)
            de_path = _ensure_artifact(artifacts_dir, settings.DRUG_ENCODER_FILE)
        except Exception as exc:
            logger.error(
                "Failed to download CatBoost artifacts from %s: %s. ML fallback disabled.",
                HF_REPO,
                exc,
            )
            return

        try:
            self._model = CatBoostClassifier()
            self._model.load_model(str(model_path))
            self._label_encoder = joblib.load(le_path)
            self._drug_encoder = joblib.load(de_path)
            self._loaded = True
            logger.info("CatBoost model loaded from %s", model_path)
        except Exception as exc:
            logger.error("Failed to load CatBoost model: %s", exc)

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(
        self,
        drug_a_name: str,
        drug_b_name: str,
        ddinter_id_a: Optional[str] = None,
        ddinter_id_b: Optional[str] = None,
    ) -> Tuple[str, float]:
        """
        Returns (risk_label, confidence).
        risk_label is one of: DANGER, CAUTION, COMPATIBLE, UNKNOWN.
        Falls back to ("UNKNOWN", 0.0) if model is not loaded.
        """
        if not self._loaded or self._model is None:
            return ("UNKNOWN", 0.0)

        id_a = ddinter_id_a or self._resolve_id(drug_a_name)
        id_b = ddinter_id_b or self._resolve_id(drug_b_name)

        id_num_a = _id_to_num(id_a)
        id_num_b = _id_to_num(id_b)

        feature_vector = [
            id_num_a,
            id_num_b,
            drug_a_name.lower(),
            drug_b_name.lower(),
            abs(len(drug_a_name) - len(drug_b_name)),
            abs(id_num_a - id_num_b),
        ]

        try:
            proba = self._model.predict_proba([feature_vector])[0]
            pred_idx = int(np.argmax(proba))
            confidence = float(proba[pred_idx])
            raw_label = self._label_encoder.inverse_transform([pred_idx])[0]
            risk = settings.LEVEL_MAP.get(raw_label.lower(), "UNKNOWN")
            return (risk, confidence)
        except Exception as exc:
            logger.error("CatBoost prediction error: %s", exc)
            return ("UNKNOWN", 0.0)

    def _resolve_id(self, drug_name: str) -> str:
        if self._drug_encoder:
            return self._drug_encoder.get(drug_name.lower(), "DDInter0")
        return "DDInter0"


ml_service = MLService()
