"""AI Doctor Recommendation routes."""

from collections import defaultdict
import logging
import time
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.agents.recommendation_engine import RecommendationEngine
from app.config.database import get_database
from app.middleware.auth import require_patient
from app.schemas.recommendation import (
    DoctorRecommendationRequest,
    DoctorRecommendationResponse,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Doctor Recommendation"])

# Shared (MongoDB) limiter, 20 requests per minute per patient (Phase 05, BUG-038).
from app.utils.rate_limiter import LimiterResetHandle, ai_recommendation_limiter  # noqa: E402

_user_request_timestamps = LimiterResetHandle(ai_recommendation_limiter)


def _check_rate_limit(user_id: str) -> None:
    """Enforce the shared per-user rate limit for AI recommendations."""
    ai_recommendation_limiter.check(user_id)


@router.post(
    "/doctor-recommendations",
    response_model=DoctorRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI Doctor Recommendations",
    description=(
        "Analyzes a natural-language request (English or Sinhala) with optional explicit filters, "
        "and returns verified, active doctor recommendations with real available slots and deterministic match reasons."
    ),
)
async def get_doctor_recommendations(
    req: DoctorRecommendationRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> DoctorRecommendationResponse:
    """Patient requests AI doctor recommendations."""
    # 1. Rate limiting check
    _check_rate_limit(str(current_user.id))

    # 2. Input sanity check
    clean_query = req.query.strip()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must not be empty.",
        )

    # 3. Execute hybrid recommendation engine
    try:
        response = await RecommendationEngine.recommend_doctors(db=db, request=req)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error processing doctor recommendations: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating doctor recommendations. Please try again.",
        )
