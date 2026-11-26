"""Payment routes for Stripe checkout, webhook handling, and status checking."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pymongo.database import Database

from app.config.database import get_database
from app.middleware.auth import require_admin, require_patient
from app.schemas.payment import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    PaymentHistoryResponse,
    PaymentStatusResponse,
)
from app.schemas.user import UserResponseSchema
from app.services.payment_service import PaymentService
from app.utils.rate_limiter import payment_intent_limiter

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
    payment_intent_limiter.check(str(current_user.id))
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

@payment_router.post("/{payment_id}/reconcile-refund")
async def refund_unconfirmed_ai_payment(
    payment_id: str,
    admin: UserResponseSchema = Depends(require_admin),
    db: Database = Depends(get_database),
):
    """Explicit admin action for money received against a booking that could not confirm."""
    import stripe
    from bson import ObjectId
    from app.config.settings import settings
    from app.models.appointment import utc_now

    if not ObjectId.is_valid(payment_id):
        raise HTTPException(404, "Payment not found.")
    payment = db["payments"].find_one({"_id": ObjectId(payment_id),
                                       "reconciliationState": {"$in": ["REVIEW_REQUIRED", "REFUND_PENDING"]}})
    if not payment or payment.get("status") != "SUCCEEDED":
        raise HTTPException(404, "Payment pending reconciliation not found.")
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(503, "Payment gateway is unavailable.")
    if db["appointments"].find_one({"stripePaymentIntentId": payment["stripePaymentIntentId"], "status": "CONFIRMED"}):
        raise HTTPException(409, "A confirmed booking is linked to this payment.")
    active = db["appointments"].find_one({
        "_id": ObjectId(payment["appointmentId"]), "status": {"$in": ["HOLD", "PENDING"]},
        "holdExpiresAt": {"$gt": utc_now()},
    })
    if active:
        raise HTTPException(409, "Wait for the booking hold to expire before reconciling the payment.")
    refunds = db["payments"]
    refunds.update_one({"_id": payment["_id"]}, {"$set": {
        "reconciliationState": "REFUND_PENDING", "reconciledBy": str(admin.id), "updatedAt": utc_now(),
    }})
    try:
        if payment.get("stripeRefundId"):
            refund = stripe.Refund.retrieve(payment["stripeRefundId"], api_key=settings.STRIPE_SECRET_KEY)
        else:
            refund = stripe.Refund.create(
                payment_intent=payment["stripePaymentIntentId"], api_key=settings.STRIPE_SECRET_KEY,
                idempotency_key=f"mediconnect_reconcile_{payment_id}",
            )
    except stripe.error.StripeError as exc:
        raise HTTPException(502, "Refund verification is pending. Retry this same request.") from exc
    state = {"succeeded": "REFUNDED", "failed": "REFUND_FAILED", "canceled": "REFUND_FAILED"}.get(
        refund.status, "REFUND_PENDING",
    )
    refunds.update_one({"_id": payment["_id"]}, {"$set": {
        "stripeRefundId": refund.id, "reconciliationState": state, "updatedAt": utc_now(),
        **({"status": "REFUNDED"} if state == "REFUNDED" else {}),
    }})
    # P4-O7 (Phase 05): the reconciliation refund is an admin financial action and is audited.
    from app.services.admin_audit_service import AdminAuditService
    AdminAuditService.log_action(
        db=db, actor_id=str(admin.id), actor_role="ADMIN", action_type="PAYMENT_RECONCILIATION_ACTION",
        target_id=payment_id, target_type="payment", previous_state=payment.get("reconciliationState"),
        new_state=state, reason="Refund of a payment whose booking could not be confirmed",
        metadata={"stripeRefundId": refund.id, "stripeStatus": refund.status},
    )
    return {"reconciliationState": state}
