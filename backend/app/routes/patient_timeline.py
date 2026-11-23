"""FastAPI endpoints for Patient Healthcare Timeline & Visit History (Phase 58)."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.schemas.timeline import (
    TimelineCategory,
    TimelineResponse,
    TimelineSummaryResponse,
    VisitDetailResponse,
)
from app.schemas.user import UserResponseSchema
from app.services.patient_timeline_service import PatientTimelineService
from app.middleware.auth import get_current_user, require_patient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients/me", tags=["Patient Healthcare Timeline"])


@router.get(
    "/healthcare-timeline",
    response_model=TimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient chronological healthcare timeline",
)
async def get_healthcare_timeline(
    category: TimelineCategory = Query(TimelineCategory.ALL, description="Filter category"),
    fromDate: Optional[str] = Query(None, description="Start date filter YYYY-MM-DD"),
    toDate: Optional[str] = Query(None, description="End date filter YYYY-MM-DD"),
    doctorId: Optional[str] = Query(None, description="Filter by doctor user ID"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Page size limit"),
    db: Database = Depends(get_database),
    current_user: UserResponseSchema = Depends(require_patient),
) -> TimelineResponse:
    """Retrieve verified, reverse-chronological healthcare events for the authenticated patient."""
    return await PatientTimelineService.get_patient_timeline(
        db=db,
        patient_user=current_user,
        category=category,
        from_date=fromDate,
        to_date=toDate,
        doctor_id=doctorId,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/healthcare-timeline/summary",
    response_model=TimelineSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient healthcare timeline summary metrics",
)
async def get_healthcare_timeline_summary(
    db: Database = Depends(get_database),
    current_user: UserResponseSchema = Depends(require_patient),
) -> TimelineSummaryResponse:
    """Retrieve quick aggregated metrics for the authenticated patient's care journey."""
    return await PatientTimelineService.get_patient_timeline_summary(
        db=db,
        patient_user=current_user,
    )


@router.get(
    "/visits/{appointment_id}",
    response_model=VisitDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get consolidated visit details for a specific appointment",
)
async def get_patient_visit_detail(
    appointment_id: str,
    db: Database = Depends(get_database),
    current_user: UserResponseSchema = Depends(require_patient),
) -> VisitDetailResponse:
    """Retrieve patient-authorized visit details with clinical linkages and events."""
    return await PatientTimelineService.get_patient_visit_detail(
        db=db,
        patient_user=current_user,
        appointment_id=appointment_id,
    )
