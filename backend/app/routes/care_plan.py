"""FastAPI router for Smart Follow-up Care Plans (Phase 56)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.schemas.care_plan import (
    CancelCarePlanRequest,
    CarePlanListResponse,
    CarePlanResponse,
    CreateCarePlanRequest,
    LinkAppointmentRequest,
    UpdateCarePlanRequest,
    UpdateTaskStatusRequest,
)
from app.schemas.user import UserResponseSchema
from app.services.care_plan_service import CarePlanService
from app.middleware.auth import (
    get_current_user,
    require_doctor,
    require_patient,
)

care_plan_router = APIRouter(prefix="/care-plans", tags=["Care Plans"])


@care_plan_router.post(
    "",
    response_model=CarePlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create follow-up care plan for a consultation (Doctor only)",
)
async def create_care_plan(
    req: CreateCarePlanRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> CarePlanResponse:
    """Doctor creates a follow-up care plan for an eligible consultation."""
    return await CarePlanService.create_care_plan(
        db=db,
        doctor_user=current_user,
        req=req,
    )


@care_plan_router.get(
    "/doctor",
    response_model=CarePlanListResponse,
    status_code=status.HTTP_200_OK,
    summary="List care plans authored by authenticated doctor",
)
async def list_doctor_care_plans(
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, COMPLETED, CANCELLED, etc.)"),
    appointment_id: Optional[str] = Query(None, description="Filter by consultation appointment ID"),
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> CarePlanListResponse:
    """Fetch care plans created by the logged-in doctor."""
    return await CarePlanService.list_doctor_care_plans(
        db=db,
        doctor_user=current_user,
        status_filter=status,
        appointment_id=appointment_id,
    )


@care_plan_router.get(
    "/patient",
    response_model=CarePlanListResponse,
    status_code=status.HTTP_200_OK,
    summary="List care plans assigned to authenticated patient",
)
async def list_patient_care_plans(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> CarePlanListResponse:
    """Fetch care plans assigned to the logged-in patient."""
    return await CarePlanService.list_patient_care_plans(
        db=db,
        patient_user=current_user,
        status_filter=status,
    )


@care_plan_router.get(
    "/{plan_id}",
    response_model=CarePlanResponse,
    status_code=status.HTTP_200_OK,
    summary="View details of a specific care plan (Doctor or Patient)",
)
async def get_care_plan(
    plan_id: str,
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> CarePlanResponse:
    """Fetch a single care plan with strict authorization check."""
    return await CarePlanService.get_care_plan(
        db=db,
        current_user=current_user,
        plan_id=plan_id,
    )


@care_plan_router.put(
    "/{plan_id}",
    response_model=CarePlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Update care plan instructions, dates, or tasks (Doctor only)",
)
async def update_care_plan(
    plan_id: str,
    req: UpdateCarePlanRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> CarePlanResponse:
    """Doctor updates an active care plan."""
    return await CarePlanService.update_care_plan(
        db=db,
        doctor_user=current_user,
        plan_id=plan_id,
        req=req,
    )


@care_plan_router.post(
    "/{plan_id}/cancel",
    response_model=CarePlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a care plan (Doctor only)",
)
async def cancel_care_plan(
    plan_id: str,
    req: CancelCarePlanRequest,
    current_user: UserResponseSchema = Depends(require_doctor),
    db: Database = Depends(get_database),
) -> CarePlanResponse:
    """Doctor cancels a care plan with a stated reason."""
    return await CarePlanService.cancel_care_plan(
        db=db,
        doctor_user=current_user,
        plan_id=plan_id,
        req=req,
    )


@care_plan_router.patch(
    "/{plan_id}/tasks/{task_id}",
    response_model=CarePlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Patient updates completion status of a care task",
)
async def update_task_status(
    plan_id: str,
    task_id: str,
    req: UpdateTaskStatusRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> CarePlanResponse:
    """Patient marks a non-medication task as completed or pending."""
    return await CarePlanService.update_task_status(
        db=db,
        patient_user=current_user,
        plan_id=plan_id,
        task_id=task_id,
        req=req,
    )


@care_plan_router.post(
    "/{plan_id}/link-appointment",
    response_model=CarePlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Patient links a newly booked follow-up appointment to care plan",
)
async def link_booked_appointment(
    plan_id: str,
    req: LinkAppointmentRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> CarePlanResponse:
    """Connect a confirmed follow-up appointment to the care plan."""
    return await CarePlanService.link_booked_appointment(
        db=db,
        patient_user=current_user,
        plan_id=plan_id,
        req=req,
    )


@care_plan_router.post(
    "/check-reminders",
    status_code=status.HTTP_200_OK,
    summary="Trigger smart follow-up reminder check",
)
def check_care_plan_reminders(
    current_user: UserResponseSchema = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> dict:
    """Scan active care plans and dispatch smart follow-up reminders."""
    sent_count = CarePlanService.check_and_send_care_plan_reminders(db)
    return {"status": "success", "remindersSent": sent_count}
