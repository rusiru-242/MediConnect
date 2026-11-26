"""API routes for AI Conversational Booking Assistant."""

from pathlib import Path
import time
from typing import Dict, Optional, Tuple
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pymongo.database import Database

from app.agents.medicine_image_agent import MAX_IMAGE_SIZE_BYTES, validate_image_file_bytes

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

# Shared (MongoDB) limiter, 30 requests per minute per patient (Phase 05, BUG-038).
from app.utils.rate_limiter import LimiterResetHandle, ai_booking_limiter  # noqa: E402

_RATE_LIMIT_BUCKET = LimiterResetHandle(ai_booking_limiter)  # tests call .clear()
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30


def _check_rate_limit(user_id: str) -> None:
    ai_booking_limiter.check(user_id)


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
# 3b. Securely upload medicine packaging/label image
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/upload-image",
    summary="Upload medicine packaging image",
    description="Uploads a medicine label or packaging image for the companion assistant with file validation.",
)
async def upload_companion_image(
    file: UploadFile = File(...),
    current_user: UserResponseSchema = Depends(require_patient),
) -> Dict[str, str]:
    """Securely upload a medicine packaging or label photo."""
    # Read at most limit + 1 bytes: an oversized upload is rejected without buffering all of it (A01-N08).
    content = await file.read(MAX_IMAGE_SIZE_BYTES + 1)
    filename = file.filename or "uploaded_image.png"
    is_valid, error_msg = validate_image_file_bytes(content, filename)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "Invalid image file.",
        )

    project_root = Path(__file__).resolve().parent.parent.parent
    upload_dir = project_root / "uploads" / "companion_images"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = upload_dir / safe_name
    from app.services.document_crypto import seal_for_storage  # medicine photos are encrypted at rest too (B8)
    dest_path.write_bytes(seal_for_storage(content, f"companion_images/{safe_name}")[0])

    relative_url = f"/uploads/companion_images/{safe_name}"
    return {
        "imageUrl": relative_url,
        "filename": filename,
    }


# ---------------------------------------------------------------------------
# 3c. Send medicine packaging image in session
# ---------------------------------------------------------------------------
@ai_booking_router.post(
    "/sessions/{session_id}/image",
    response_model=BookingSessionResponse,
    summary="Send medicine packaging image in session",
    description="Uploads and analyzes a medicine package photo in the active conversational companion session.",
)
async def send_session_image(
    session_id: str,
    file: UploadFile = File(...),
    message: Optional[str] = Form(None),
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> BookingSessionResponse:
    """Upload and process medicine image in companion conversation."""
    _check_rate_limit(str(current_user.id))
    # Read at most limit + 1 bytes: an oversized upload is rejected without buffering all of it (A01-N08).
    content = await file.read(MAX_IMAGE_SIZE_BYTES + 1)
    filename = file.filename or "uploaded_image.png"

    is_valid, error_msg = validate_image_file_bytes(content, filename)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "Invalid image file.",
        )

    # The image is analysed in memory and not written to disk: the stored copies were never served
    # to the app and only created an unnecessary retention of sensitive medical imagery.
    return await BookingSessionService.handle_image_message(
        db=db,
        patient_user=current_user,
        session_id=session_id,
        image_bytes=content,
        filename=filename,
        message=message,
        image_url=None,
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
