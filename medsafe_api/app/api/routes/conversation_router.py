"""
Conversation Router

POST /api/v1/conversation/chat   - Send a message and receive a clinical reply
GET  /api/v1/conversation/topics - List suggested training topics

Multi-turn pharmacist training assistant backed by BioMistral.
Session history is persisted in SQLite; the client only needs a session_id.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import logging
from sqlalchemy.orm import Session

from app.services.biomistral_service import generate_conversation_reply
from app.data.database import get_db
from app.models.chat_session import ChatSession, ChatMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversation", tags=["Pharmacist Training"])


Role = Literal["user", "assistant"]


class ConversationMessage(BaseModel):
    role: Role = Field(description="'user' or 'assistant'")
    content: str = Field(min_length=1, description="Message text")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's message.")
    session_id: Optional[str] = Field(None, description="Session ID to continue. Omit to start a new session.")
    user_role: Literal["patient", "pharmacist"] = Field("pharmacist", description="The role of the user")
    max_tokens: int = Field(512, ge=64, le=1024, description="Maximum tokens to generate.")
    temperature: float = Field(0.4, ge=0.0, le=1.0, description="Sampling temperature.")


class ChatResponse(BaseModel):
    reply: str = Field(description="The assistant's response.")
    session_id: str = Field(description="The ID of the chat session.")
    turn: int = Field(description="Current turn number (number of user messages so far).")


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to the pharmacist training assistant",
)
async def chat(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """
    Multi-turn clinical knowledge chat powered by BioMistral.
    Session history is stored in the local SQLite database.
    """
    session_id = body.session_id

    if session_id:
        chat_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not chat_session:
            raise HTTPException(status_code=404, detail="Session not found.")
    else:
        chat_session = ChatSession()
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        session_id = chat_session.id

    user_msg = ChatMessage(session_id=session_id, role="user", content=body.message)
    db.add(user_msg)
    db.commit()

    db.refresh(chat_session)
    history_dicts = [{"role": m.role, "content": m.content} for m in chat_session.messages]

    try:
        reply_text = generate_conversation_reply(
            history=history_dicts,
            role=body.user_role,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )
    except Exception as exc:
        logger.error("BioMistral conversation inference failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="The language model is temporarily unavailable. Please retry in a moment.",
        )

    assistant_msg = ChatMessage(session_id=session_id, role="assistant", content=reply_text)
    db.add(assistant_msg)
    db.commit()

    user_turns = sum(1 for m in chat_session.messages if m.role == "user")

    return ChatResponse(
        reply=reply_text,
        session_id=session_id,
        turn=user_turns,
    )