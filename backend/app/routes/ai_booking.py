"""API routes for AI Conversational Booking Assistant."""

import time
from typing import Dict, Tuple
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_patient
from app.schemas.booking_session import (
    BookingSessionResponse,
    ConfirmBookingRequest,
    CreateSessionRequest,
    SelectDoctorRequest,
    SelectSlotRequest,
    SendMessageRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.booking_session_service import BookingSessionService

ai_booking_router = APIRouter(prefix="/ai/booking", tags=["AI Booking Agent"])

# In-memory sliding window rate limiter: max 30 requests per minute per patient
_RATE_LIMIT_BUCKET: Dict[str, list] = {}
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30


def _check_rate_limit(user_id: str) -> None:
    now = time.time()
    history = _RATE_LIMIT_BUCKET.setdefault(user_id, [])
    # Evict timestamps older than 60s
    while history and history[0] <= now - RATE_LIMIT_WINDOW_SECONDS:
        history.pop(0)

    if len(history) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests to the AI Booking Assistant. Please wait a moment before sending another message.",
        )
    history.append(now)


# ---------------------------------------------------------------------------
# 1. Start or resume booking session
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/sessions",
    response_model=BookingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI booking session",
    description="Initiates an interactive multi-turn AI doctor booking session for the authenticated patient.",
)
async def create_booking_session(
    req: CreateSessionRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Create a new AI booking session."""
    _check_rate_limit(str(current_user.id))
    return await BookingSessionService.create_session(
        db=db, patient_user=current_user, req=req
    )


# ---------------------------------------------------------------------------
# 2. Get active booking session
# ---------------------------------------------------------------------------
@ai_booking_router.get(
    "/sessions/{session_id}",
    response_model=BookingSessionResponse,
    summary="Get AI booking session state",
    description="Fetches current session state, messages, candidates, and hold details with ownership verification.",
)
async def get_booking_session(
    session_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Retrieve booking session by ID."""
    return await BookingSessionService.get_session(
        db=db, patient_user=current_user, session_id=session_id
    )


# ---------------------------------------------------------------------------
# 3. Send conversational message
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/sessions/{session_id}/messages",
    response_model=BookingSessionResponse,
    summary="Send message in booking session",
    description="Sends a patient message in English or Sinhala to the conversational booking assistant.",
)
async def send_session_message(
    session_id: str,
    req: SendMessageRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Post user message to conversational assistant."""
    _check_rate_limit(str(current_user.id))
    return await BookingSessionService.handle_message(
        db=db, patient_user=current_user, session_id=session_id, req=req
    )


# ---------------------------------------------------------------------------
# 4. Explicitly select recommended doctor
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/sessions/{session_id}/select-doctor",
    response_model=BookingSessionResponse,
    summary="Select doctor in session",
    description="Explicitly selects a verified doctor and queries their real discrete appointment slots.",
)
async def select_doctor(
    session_id: str,
    req: SelectDoctorRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Select a doctor."""
    return await BookingSessionService.select_doctor(
        db=db, patient_user=current_user, session_id=session_id, req=req
    )


# ---------------------------------------------------------------------------
# 5. Explicitly select appointment slot
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/sessions/{session_id}/select-slot",
    response_model=BookingSessionResponse,
    summary="Select appointment slot in session",
    description="Explicitly selects a slot and generates the authoritative booking summary before hold confirmation.",
)
async def select_slot(
    session_id: str,
    req: SelectSlotRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Select an appointment slot."""
    return await BookingSessionService.select_slot(
        db=db, patient_user=current_user, session_id=session_id, req=req
    )


# ---------------------------------------------------------------------------
# 6. Explicitly confirm booking hold
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/sessions/{session_id}/confirm",
    response_model=BookingSessionResponse,
    summary="Confirm booking hold",
    description="Explicit user confirmation that creates a 10-minute temporary appointment hold in the database.",
)
async def confirm_booking(
    session_id: str,
    req: ConfirmBookingRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Explicitly confirm booking and create hold."""
    return await BookingSessionService.confirm_booking(
        db=db, patient_user=current_user, session_id=session_id, req=req
    )


# ---------------------------------------------------------------------------
# 7. Cancel session
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/sessions/{session_id}/cancel",
    response_model=BookingSessionResponse,
    summary="Cancel booking session",
    description="Cancels the active booking session and releases any active slot hold.",
)
async def cancel_session(
    session_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Cancel booking session."""
    return await BookingSessionService.cancel_session(
        db=db, patient_user=current_user, session_id=session_id
    )


# ---------------------------------------------------------------------------
# 8. Sync payment & booking status
# ---------------------------------------------------------------------------
@ai_booking_router.get(
    "/sessions/{session_id}/payment-status",
    response_model=BookingSessionResponse,
    summary="Sync payment status with session",
    description="Authoritatively checks database payment and appointment status to advance session to BOOKING_CONFIRMED.",
)
async def sync_payment_status(
    session_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Sync payment and appointment status."""
    return await BookingSessionService.sync_payment_status(
        db=db, patient_user=current_user, session_id=session_id
    )
