"""FastAPI route endpoints for Smart Medication Reminders and Tracking (Phase 22)."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import get_current_user, require_patient
from app.schemas.medication_reminder import (
    AdherenceSummaryResponse,
    CreateMedicationReminderRequest,
    MedicationEventListResponse,
    MedicationEventResponse,
    MedicationReminderListResponse,
    MedicationReminderResponse,
    RecordMedicationEventRequest,
    TodayScheduleResponse,
    UpdateMedicationReminderRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.medication_reminder_service import MedicationReminderService

medication_reminder_router = APIRouter(
    prefix="/medication-reminders",
    tags=["Medication Reminders"],
)


@medication_reminder_router.post(
    "",
    response_model=MedicationReminderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create medication reminder from prescription",
    description="Allows a patient to set a medication reminder schedule linked to their doctor's prescription.",
)
async def create_reminder(
    req: CreateMedicationReminderRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> MedicationReminderResponse:
    """Create a new medication reminder schedule."""
    return await MedicationReminderService.create_reminder(
        db=db, patient_user=current_user, req=req
    )


@medication_reminder_router.get(
    "",
    response_model=MedicationReminderListResponse,
    summary="List patient medication reminders",
    description="Returns all active or past medication reminders for the authenticated patient.",
)
async def list_reminders(
    active_only: bool = Query(default=False, description="Filter only active and enabled reminders"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> MedicationReminderListResponse:
    """List reminders for the authenticated patient."""
    return await MedicationReminderService.list_patient_reminders(
        db=db,
        patient_user=current_user,
        active_only=active_only,
        page=page,
        page_size=page_size,
    )


@medication_reminder_router.get(
    "/today",
    response_model=TodayScheduleResponse,
    summary="Get today's medication schedule",
    description="Returns all scheduled dose occurrences for today along with their recorded status (PENDING, TAKEN, SKIPPED, SNOOZED).",
)
async def get_today_schedule(
    timezone: Optional[str] = Query(default=None, description="Patient local timezone e.g. Asia/Colombo"),
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> TodayScheduleResponse:
    """Get today's scheduled medication intake items."""
    return await MedicationReminderService.get_today_schedule(
        db=db, patient_user=current_user, timezone_str=timezone
    )


@medication_reminder_router.get(
    "/history",
    response_model=MedicationEventListResponse,
    summary="Get medication intake event history",
    description="Returns paginated history of taken, skipped, and snoozed medication events.",
)
async def get_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> MedicationEventListResponse:
    """Get medication history events."""
    return await MedicationReminderService.get_history(
        db=db, patient_user=current_user, page=page, page_size=page_size
    )


@medication_reminder_router.get(
    "/adherence",
    response_model=AdherenceSummaryResponse,
    summary="Get adherence summary",
    description="Provides non-judgmental adherence statistics over the past 30 days.",
)
async def get_adherence(
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> AdherenceSummaryResponse:
    """Get patient adherence summary statistics."""
    return await MedicationReminderService.get_adherence_summary(
        db=db, patient_user=current_user
    )


@medication_reminder_router.get(
    "/{reminder_id}",
    response_model=MedicationReminderResponse,
    summary="Get reminder details",
    description="Retrieves a specific medication reminder by ID with patient ownership verification.",
)
async def get_reminder(
    reminder_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> MedicationReminderResponse:
    """Get single reminder details."""
    return await MedicationReminderService.get_reminder(
        db=db, current_user=current_user, reminder_id=reminder_id
    )


@medication_reminder_router.patch(
    "/{reminder_id}",
    response_model=MedicationReminderResponse,
    summary="Update reminder schedule or settings",
    description="Updates reminder times, active status, notes, or timezone.",
)
async def update_reminder(
    reminder_id: str,
    req: UpdateMedicationReminderRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> MedicationReminderResponse:
    """Update medication reminder settings."""
    return await MedicationReminderService.update_reminder(
        db=db, current_user=current_user, reminder_id=reminder_id, req=req
    )


@medication_reminder_router.delete(
    "/{reminder_id}",
    response_model=Dict[str, Any],
    summary="Cancel or delete reminder",
    description="Cancels and disables the medication reminder.",
)
async def delete_reminder(
    reminder_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> Dict[str, Any]:
    """Delete or cancel medication reminder."""
    return await MedicationReminderService.delete_reminder(
        db=db, current_user=current_user, reminder_id=reminder_id
    )


@medication_reminder_router.post(
    "/{reminder_id}/events",
    response_model=MedicationEventResponse,
    summary="Record medication event (taken, skipped, snoozed)",
    description="Idempotently records an intake event for a specific scheduled occurrence.",
)
async def record_medication_event(
    reminder_id: str,
    req: RecordMedicationEventRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> MedicationEventResponse:
    """Record an intake action (taken, skipped, snoozed) for a scheduled dose."""
    return await MedicationReminderService.record_event(
        db=db,
        patient_user=current_user,
        reminder_id=reminder_id,
        req=req,
    )
