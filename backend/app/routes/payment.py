"""Payment routes for Stripe checkout, webhook handling, and status checking."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_patient
from app.schemas.payment import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    PaymentHistoryResponse,
    PaymentStatusResponse,
)
from app.schemas.user import UserResponseSchema
from app.services.payment_service import PaymentService

payment_router = APIRouter(prefix="/payments", tags=["Payments"])


# ---------------------------------------------------------------------------
# 1. Create PaymentIntent
# ---------------------------------------------------------------------------
@payment_router.post(
    "/create-intent",
    response_model=CreatePaymentIntentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe PaymentIntent",
    description="Patient requests a PaymentIntent for an unexpired appointment hold. The amount is strictly derived from the doctor's consultation fee on the backend.",
)
async def create_payment_intent(
    req: CreatePaymentIntentRequest,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> CreatePaymentIntentResponse:
    """Create Stripe PaymentIntent for held appointment."""
    return await PaymentService.create_payment_intent(
        db=db, patient_user=current_user, req=req
    )


# ---------------------------------------------------------------------------
# 2. Stripe Webhook
# ---------------------------------------------------------------------------
@payment_router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook endpoint",
    description="Receives Stripe webhook events, verifies the cryptographic signature, and idempotently updates payment and appointment records.",
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Database = Depends(get_database),
) -> Dict[str, Any]:
    """Handle Stripe webhooks."""
    payload = await request.body()
    return await PaymentService.handle_webhook(
        db=db, payload=payload, sig_header=stripe_signature
    )


# ---------------------------------------------------------------------------
# 3. Patient Payment History
# ---------------------------------------------------------------------------
@payment_router.get(
    "/me",
    response_model=PaymentHistoryResponse,
    summary="Get patient payment history",
    description="Returns the authenticated patient's past payments without exposing sensitive Stripe secrets.",
)
async def get_patient_payment_history(
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> PaymentHistoryResponse:
    """Get payment history for authenticated patient."""
    return await PaymentService.list_patient_payments(db=db, patient_user=current_user)


# ---------------------------------------------------------------------------
# 4. Check Payment Status
# ---------------------------------------------------------------------------
@payment_router.get(
    "/{payment_id}/status",
    response_model=PaymentStatusResponse,
    summary="Get payment and appointment status",
    description="Authoritative status query endpoint. Flutter queries this endpoint after PaymentSheet completion to confirm payment and appointment status.",
)
async def get_payment_status(
    payment_id: str,
    current_user: UserResponseSchema = Depends(require_patient),
    db: Database = Depends(get_database),
) -> PaymentStatusResponse:
    """Check payment status for given payment ID."""
    return await PaymentService.get_payment_status(
        db=db, payment_id=payment_id, patient_user=current_user
    )
