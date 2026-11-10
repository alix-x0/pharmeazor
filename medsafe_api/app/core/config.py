from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "MedSafe API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # External APIs
    OPENAI_API_KEY: str | None = None

    # Paths
    DATA_DIR: Path = BASE_DIR / "app" / "data"
    ML_ARTIFACTS_DIR: Path = BASE_DIR / "ml" / "artifacts"

    # DDInter CSV file prefixes to load (place all ddinter_downloads_code_*.csv here)
    DDINTER_CSV_GLOB: str = "ddinter_downloads_code_*.csv"

    # Fuzzy match threshold for drug name autocomplete (0–100)
    FUZZY_THRESHOLD: int = 70

    # Interaction level → risk label mapping
    LEVEL_MAP: dict = {
        "major": "DANGER",
        "moderate": "CAUTION",
        "minor": "COMPATIBLE",
        "unknown": "UNKNOWN",
    }

    # Risk colours for the front-end
    RISK_COLORS: dict = {
        "DANGER": "#D32F2F",
        "CAUTION": "#F57C00",
        "COMPATIBLE": "#388E3C",
        "UNKNOWN": "#757575",
        "NOT_IN_DB": "#9E9E9E",
    }

    # CatBoost model file name inside ML_ARTIFACTS_DIR
    CATBOOST_MODEL_FILE: str = "catboost_interaction.cbm"
    LABEL_ENCODER_FILE: str = "label_encoder.joblib"
    DRUG_ENCODER_FILE: str = "drug_encoder.joblib"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
