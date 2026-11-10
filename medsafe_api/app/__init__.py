"""
MedSafe API - Application Factory

Startup sequence:
  1. Create database tables
  2. Load DDInter CSV files into memory
  3. Load CatBoost model if available
  4. Pre-load BioMistral GGUF model
  5. Mount all API routes under /api
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import api_router
from app.core.config import settings
from app.data.database import Base, engine
from app.services.ddinter_service import ddinter_service
from app.services.ml_service import ml_service
from app.services import biomistral_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MedSafe API starting up.")

    Base.metadata.create_all(bind=engine)
    ddinter_service.load()
    ml_service.load()

    try:
        biomistral_service.load()
    except Exception as exc:
        logger.warning(
            "BioMistral failed to load at startup: %s. "
            "The /analyze endpoint will be unavailable.",
            exc,
        )

    logger.info("Startup complete.")
    yield
    logger.info("MedSafe API shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Drug-drug interaction checker for the Algerian market. "
            "Powered by the DDInter database with a CatBoost ML fallback, "
            "BioMistral clinical explanations, and Algerian Darija translation."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    return app


app = create_app()
