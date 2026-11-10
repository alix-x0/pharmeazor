from fastapi import APIRouter
from app.api.routes.interactions import router as interactions_router
from app.api.routes.explain_router import router as explain_router
from app.api.routes.conversation_router import router as conversation_router

api_router = APIRouter()
api_router.include_router(interactions_router, prefix="/v1")
api_router.include_router(explain_router,      prefix="/v1")
api_router.include_router(conversation_router, prefix="/v1")
