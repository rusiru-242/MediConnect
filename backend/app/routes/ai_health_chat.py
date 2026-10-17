"""API routes for AI Symptom Guidance & Doctor Referral Chatbot."""

import time
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_patient
from app.schemas.health_chat import (
    CreateHealthChatSessionRequest,
    DeleteHealthChatSessionResponse,
    HealthChatSessionResponse,
    SendHealthChatMessageRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.health_chat_service import HealthChatService

ai_health_chat_router = APIRouter(prefix="/ai/health-chat", tags=["AI Health Chatbot"])

# Sliding window in-memory rate limiter: max 30 requests per minute per patient
_HEALTH_CHAT_RATE_LIMIT_BUCKET: Dict[str, list] = {}
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30


def _check_rate_limit(user_id: str) -> None:
    """Sliding-window rate limiter per authenticated patient."""
    now = time.time()
    history = _HEALTH_CHAT_RATE_LIMIT_BUCKET.setdefault(user_id, [])
    while history and history[0] <= now - RATE_LIMIT_WINDOW_SECONDS:
        history.pop(0)

    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests to the AI Health Assistant. Please wait a moment before sending another message.",
        )
    history.append(now)


# ---------------------------------------------------------------------------
# 1. Create Health Chat Session
# ---------------------------------------------------------------------------
@ai_health_chat_router.post(
    "/sessions",
    response_model=HealthChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI health chat session",
    description="Initiates a confidential, safe AI symptom guidance session for the authenticated patient.",
)
async def create_health_chat_session(
    req: CreateHealthChatSessionRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> HealthChatSessionResponse:
    """Create a new symptom guidance session."""
    _check_rate_limit(str(current_user.id))
    return await HealthChatService.create_session(
        db=db, patient_user=current_user, req=req
    )


# ---------------------------------------------------------------------------
# 2. Get Health Chat Session
# ---------------------------------------------------------------------------
@ai_health_chat_router.get(
    "/sessions/{session_id}",
    response_model=HealthChatSessionResponse,
    summary="Get AI health chat session",
    description="Fetches current session transcript, triage classification, and doctor referrals with patient ownership checks.",
)
async def get_health_chat_session(
    session_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> HealthChatSessionResponse:
    """Fetch health chat session by ID."""
    return await HealthChatService.get_session(
        db=db, patient_user=current_user, session_id=session_id
    )


# ---------------------------------------------------------------------------
# 3. Send Message in Health Chat Session
# ---------------------------------------------------------------------------
@ai_health_chat_router.post(
    "/sessions/{session_id}/messages",
    response_model=HealthChatSessionResponse,
    summary="Send message to AI health assistant",
    description="Processes patient symptoms in English or Sinhala with deterministic safety triage, anti-hallucination post-filtering, and doctor referrals.",
)
async def send_health_chat_message(
    session_id: str,
    req: SendHealthChatMessageRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> HealthChatSessionResponse:
    """Send conversational turn to health assistant."""
    _check_rate_limit(str(current_user.id))
    return await HealthChatService.send_message(
        db=db, patient_user=current_user, session_id=session_id, req=req
    )


# ---------------------------------------------------------------------------
# 4. Delete Health Chat Session (Privacy & Data Minimization)
# ---------------------------------------------------------------------------
@ai_health_chat_router.delete(
    "/sessions/{session_id}",
    response_model=DeleteHealthChatSessionResponse,
    summary="Delete AI health chat session",
    description="Permanently deletes the health chat session and its transcript to honor patient privacy and data minimization.",
)
async def delete_health_chat_session(
    session_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> DeleteHealthChatSessionResponse:
    """Permanently delete health chat session."""
    return await HealthChatService.delete_session(
        db=db, patient_user=current_user, session_id=session_id
    )
