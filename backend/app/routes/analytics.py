"""FastAPI routes for Admin Analytics Dashboard (Phase 24)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_admin
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AppointmentAnalyticsResponse,
    ContentAnalyticsResponse,
    DoctorAnalyticsResponse,
    PaymentAnalyticsResponse,
)
from app.schemas.user import UserResponseSchema
from app.services.analytics_service import AnalyticsService

analytics_router = APIRouter(
    prefix="/admin/analytics",
    tags=["Admin Analytics Dashboard"],
)


@analytics_router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get high-level platform health overview metrics",
)
async def get_analytics_overview(
    startDate: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    endDate: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AnalyticsOverviewResponse:
    """Retrieve platform aggregate statistics. Requires ADMIN role."""
    return await AnalyticsService.get_overview(
        db=db, start_date=startDate, end_date=endDate
    )


@analytics_router.get(
    "/appointments",
    response_model=AppointmentAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get appointment statistics and daily volume trends",
)
async def get_appointment_analytics(
    startDate: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    endDate: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> AppointmentAnalyticsResponse:
    """Retrieve appointment status distributions, completion rates, and daily trends. Requires ADMIN role."""
    return await AnalyticsService.get_appointments_analytics(
        db=db, start_date=startDate, end_date=endDate
    )


@analytics_router.get(
    "/payments",
    response_model=PaymentAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get revenue totals by currency, test payment counts, and refunds",
)
async def get_payment_analytics(
    startDate: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    endDate: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> PaymentAnalyticsResponse:
    """Retrieve currency-grouped revenue, Stripe test mode tracking, and refund statistics. Requires ADMIN role."""
    return await AnalyticsService.get_payments_analytics(
        db=db, start_date=startDate, end_date=endDate
    )


@analytics_router.get(
    "/doctors",
    response_model=DoctorAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor verification status and specialty breakdown",
)
async def get_doctor_analytics(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> DoctorAnalyticsResponse:
    """Retrieve doctor verification pipeline counts and specialty distributions. Requires ADMIN role."""
    return await AnalyticsService.get_doctors_analytics(db=db)


@analytics_router.get(
    "/content",
    response_model=ContentAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get content publishing metrics and bookmark counts",
)
async def get_content_analytics(
    current_admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
) -> ContentAnalyticsResponse:
    """Retrieve health content catalog stats, categories, and top bookmarked articles. Requires ADMIN role."""
    return await AnalyticsService.get_content_analytics(db=db)
