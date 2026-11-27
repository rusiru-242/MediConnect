"""Stripe webhook event log and refund reconciliation (Phase 05, B3 / P4-B10).

The signature is verified on the raw request body by ``PaymentService.handle_webhook`` before anything here runs.

Event log (``stripe_webhook_events``): every verified event is stored by its Stripe event id before processing.
A redelivered event that was already processed returns ``duplicate`` without touching any record; an event whose
processing crashed is retried after five minutes. Only the event id, type, livemode, Stripe creation time,
outcome and timestamps are stored, never the payload.

Refund events (``refund.created``, ``refund.updated``, ``refund.failed`` and ``charge.refunded``):

* the refund must belong to a MediConnect refund request or reconciliation refund (matched by Stripe refund id),
  its PaymentIntent must be the payment's intent, its currency the payment's currency, and its amount must not
  exceed what was captured; anything else is recorded as ``rejected_mismatch`` and changes nothing;
* final states are never downgraded. ``pending`` after ``succeeded`` (out-of-order delivery) is ignored. Stripe can
  report a refund as failed after it succeeded; that flags the refund request for human review instead of
  editing financial records automatically;
* a succeeded refund is applied exactly once: the payment's ``refundRequestIds`` guards the increment.

``sync_pending_refunds`` is the polling fallback used by the worker while webhooks cannot be delivered (B3): it
retrieves the current state of refunds that have stayed PROCESSING and applies the same rules.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)
EVENTS = "stripe_webhook_events"
PROCESSING, SUCCEEDED, FAILED = "processing", "succeeded", "failed"  # RefundStatus values
REFUND_EVENT_TYPES = {"refund.created", "refund.updated", "refund.failed", "charge.refunded",
                      "charge.refund.updated"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj[key]
    except (KeyError, TypeError, AttributeError):
        return getattr(obj, key, default)


def begin_event(db: Database, event: Any) -> Optional[str]:
    """Store the event id before processing.

    Returns None to process the event, "duplicate" when it was already processed, or "in_progress" when another
    delivery is processing it right now. Only "duplicate" may be acknowledged with a 2xx: Stripe stops redelivering
    an event once it gets a 2xx, so an in-progress or crashed event must be answered with an error (A03-BUG-001).
    """
    event_id = _get(event, "id")
    if not event_id:
        return None  # signature-verified Stripe events always carry an id; nothing to de-duplicate on
    doc = {"_id": event_id, "type": _get(event, "type"), "livemode": bool(_get(event, "livemode")),
           "stripeCreated": _get(event, "created"), "receivedAt": utc_now(), "status": "processing", "attempts": 1}
    try:
        db[EVENTS].insert_one(doc)
        return None
    except DuplicateKeyError:
        stale = utc_now() - timedelta(minutes=5)
        # A delivery whose processing failed is retried at once; one still "processing" after five minutes is
        # treated as crashed (the process died before it could record the failure).
        retaken = db[EVENTS].find_one_and_update(
            {"_id": event_id, "$or": [{"status": "failed"},
                                      {"status": "processing", "receivedAt": {"$lt": stale}}]},
            {"$set": {"status": "processing", "receivedAt": utc_now()}, "$inc": {"attempts": 1}})
        if retaken:
            return None
        current = db[EVENTS].find_one({"_id": event_id}, {"status": 1}) or {}
        return "duplicate" if current.get("status") == "processed" else "in_progress"


def finish_event(db: Database, event: Any, outcome: str) -> None:
    if not _get(event, "id"):
        return
    db[EVENTS].update_one({"_id": _get(event, "id")},
                          {"$set": {"status": "processed", "outcome": outcome, "processedAt": utc_now()}})


def fail_event(db: Database, event: Any, error: BaseException) -> None:
    """Record that processing raised, so Stripe's redelivery is processed again (only the error type is kept)."""
    if not _get(event, "id"):
        return
    db[EVENTS].update_one({"_id": _get(event, "id"), "status": "processing"},
                          {"$set": {"status": "failed", "lastError": type(error).__name__, "failedAt": utc_now()}})


def handle_payment_intent_canceled(db: Database, intent: Any) -> str:
    payment = db["payments"].find_one({"stripePaymentIntentId": _get(intent, "id")})
    if not payment:
        return "ignored_unknown_payment"
    changed = db["payments"].update_one(
        {"_id": payment["_id"], "status": {"$in": ["PENDING", "FAILED"]}},
        {"$set": {"status": "CANCELLED", "cancellationReason": _get(intent, "cancellation_reason"),
                  "updatedAt": utc_now()}})
    # The reservation itself is released by its own hold expiry; a cancelled intent never confirms anything.
    return "payment_cancelled" if changed.modified_count else "no_change"


def _refund_objects(event_type: str, obj: Any):
    if event_type == "charge.refunded":
        refunds = _get(_get(obj, "refunds") or {}, "data") or []
        return list(refunds)
    return [obj]


def handle_refund_event(db: Database, event_type: str, obj: Any, *, source: str = "webhook") -> str:
    outcomes = [apply_refund_state(db, refund, source=source) for refund in _refund_objects(event_type, obj)]
    return ",".join(outcomes) if outcomes else "no_refunds"


def apply_refund_state(db: Database, refund: Any, *, source: str) -> str:
    """Apply one Stripe Refund object's state to the matching MediConnect records."""
    from app.services.admin_audit_service import AdminAuditService
    refund_id = _get(refund, "id")
    stripe_status = _get(refund, "status")
    amount_minor = int(_get(refund, "amount") or 0)
    currency = (_get(refund, "currency") or "").lower()
    intent_id = _get(refund, "payment_intent")
    request = db["refund_requests"].find_one({"stripeRefundId": refund_id}) if refund_id else None
    if request is None and refund_id:
        # A refund whose create response was lost (A03-BUG-007) is found by the MediConnect refund id that
        # approve_refund puts in its metadata; the intent, currency and amount are still checked below.
        ref = _get(_get(refund, "metadata") or {}, "refundId")
        if ref:
            request = db["refund_requests"].find_one({"refundId": ref, "stripeRefundId": None})
    payment = None
    if request and ObjectId.is_valid(str(request.get("paymentId"))):
        payment = db["payments"].find_one({"_id": ObjectId(request["paymentId"])})
    elif refund_id:
        payment = db["payments"].find_one({"stripeRefundId": refund_id})  # reconciliation refunds
    if not payment:
        return "ignored_unknown_refund"

    captured_minor = int(round(float(payment.get("amount") or 0) * 100))
    if (intent_id and intent_id != payment.get("stripePaymentIntentId")) or \
            (currency and currency != (payment.get("currency") or "").lower()) or amount_minor > captured_minor:
        logger.warning("Stripe refund event did not match its payment; nothing changed.")
        db["payments"].update_one({"_id": payment["_id"]}, {"$set": {"refundEventMismatch": True,
                                                                      "updatedAt": utc_now()}})
        return "rejected_mismatch"

    if request is None:  # admin reconciliation refund recorded on the payment itself
        state = {"succeeded": "REFUNDED", "failed": "REFUND_FAILED", "canceled": "REFUND_FAILED"}.get(stripe_status)
        if state is None or payment.get("reconciliationState") == state:
            return "no_change"
        if payment.get("reconciliationState") == "REFUNDED" and state != "REFUNDED":
            db["payments"].update_one({"_id": payment["_id"]}, {"$set": {"refundRequiresReview": True,
                                                                          "updatedAt": utc_now()}})
            return "flagged_for_review"
        db["payments"].update_one({"_id": payment["_id"]}, {"$set": {
            "reconciliationState": state, "updatedAt": utc_now(), **({"status": "REFUNDED"} if state == "REFUNDED" else {})}})
        return f"reconciliation_{state.lower()}"

    # Refund requests use the lowercase RefundStatus values ("processing", "succeeded", "failed"); this module used
    # uppercase names and so never matched a real request (A03-BUG-006). Legacy uppercase values are normalised.
    current = (request.get("status") or "").lower()
    if stripe_status == "succeeded":
        if current == SUCCEEDED:
            return "no_change"
        amount = round(amount_minor / 100.0, 2)
        _apply_refund_success(db, request, payment, amount, refund_id, source)
        AdminAuditService.log_action(
            db=db, actor_id=f"system:{source}", actor_role="SYSTEM", action_type="REFUND_RECONCILIATION",
            target_id=request["refundId"], target_type="refund_request", previous_state=current,
            new_state=SUCCEEDED, reason=f"Stripe reported the refund as succeeded ({source})",
            metadata={"stripeRefundId": refund_id, "amount": amount})
        return "refund_succeeded"
    if stripe_status in {"failed", "canceled"}:
        if current == SUCCEEDED:
            db["refund_requests"].update_one({"_id": request["_id"]}, {"$set": {
                "requiresReview": True, "reviewReason": f"Stripe reported {stripe_status} after success",
                "stripeRefundStatus": stripe_status, "updatedAt": utc_now()}})
            AdminAuditService.log_action(
                db=db, actor_id=f"system:{source}", actor_role="SYSTEM", action_type="REFUND_RECONCILIATION",
                target_id=request["refundId"], target_type="refund_request", previous_state=current,
                new_state=current, status="REVIEW_REQUIRED",
                reason=f"Stripe reported {stripe_status} after the refund had succeeded; human review required")
            return "flagged_for_review"
        if current == FAILED:
            return "no_change"
        db["refund_requests"].update_one({"_id": request["_id"], "status": {"$nin": [SUCCEEDED, "SUCCEEDED"]}}, {"$set": {
            "status": FAILED, "stripeRefundId": refund_id, "stripeRefundStatus": stripe_status,
            "failureReason": _get(refund, "failure_reason") or stripe_status, "updatedAt": utc_now()}})
        AdminAuditService.log_action(
            db=db, actor_id=f"system:{source}", actor_role="SYSTEM", action_type="REFUND_RECONCILIATION",
            target_id=request["refundId"], target_type="refund_request", previous_state=current, new_state=FAILED,
            status="FAILED", reason=f"Stripe reported the refund as {stripe_status} ({source})")
        return "refund_failed"
    # pending / requires_action: never downgrade a final state (out-of-order delivery)
    if current in {SUCCEEDED, FAILED}:
        return "ignored_out_of_order"
    db["refund_requests"].update_one({"_id": request["_id"]}, {"$set": {"stripeRefundStatus": stripe_status,
                                                                        "lastStripeSyncAt": utc_now()}})
    return "still_pending"


def _apply_refund_success(db: Database, request: dict, payment: dict, amount: float, refund_id: str, source: str):
    from app.services.refund_service import _money_text, _notify_patient
    now = utc_now()
    db["refund_requests"].update_one(
        {"_id": request["_id"], "status": {"$nin": [SUCCEEDED, "SUCCEEDED"]}},
        {"$set": {"status": SUCCEEDED, "stripeRefundId": refund_id, "stripeRefundStatus": "succeeded", "refundedAmount": amount,
                  "completedAt": now, "updatedAt": now, "completedBy": source}})
    updated = db["payments"].find_one_and_update(
        {"_id": payment["_id"], "refundRequestIds": {"$ne": request["refundId"]}},
        {"$inc": {"refundedAmount": amount}, "$push": {"refundRequestIds": request["refundId"]},
         "$set": {"updatedAt": now}}, return_document=ReturnDocument.AFTER) or payment
    captured = float(payment.get("amount") or 0)
    full = round(float(updated.get("refundedAmount") or 0), 2) >= captured
    if full:
        db["payments"].update_one({"_id": payment["_id"]}, {"$set": {"status": "REFUNDED"}})
        if ObjectId.is_valid(str(request.get("appointmentId"))):
            db["appointments"].update_one({"_id": ObjectId(request["appointmentId"])},
                                          {"$set": {"paymentStatus": "REFUNDED", "updatedAt": now}})
    try:
        from app.services.appointment_events import record_appointment_event
        record_appointment_event(db, request["appointmentId"], "REFUND_SUCCEEDED", actor_role="SYSTEM",
                                 actor_id=source, details={"refundId": request["refundId"], "amount": amount,
                                                           "full": full},
                                 idempotency_key=f"refund_succeeded_{request['refundId']}")
    except Exception:
        pass
    money = _money_text(request.get("currency"), amount)
    _notify_patient(db, request, "Refund issued",
                    f"Your refund of {money} for your cancelled appointment was issued. Your bank may take several "
                    "days to show it.", f"refund_succeeded_{request['refundId']}")


def _list_refunds_for_intent(payment_intent_id: str):
    import stripe
    return list(stripe.Refund.list(payment_intent=payment_intent_id, limit=100).auto_paging_iter())


def find_refund_by_request(payment_intent_id: str, refund_id: str, list_refunds=None):
    """The Stripe refund created for a MediConnect refund request (metadata.refundId), or None. Read-only."""
    for refund in (list_refunds or _list_refunds_for_intent)(payment_intent_id):
        if _get(_get(refund, "metadata") or {}, "refundId") == refund_id:
            return refund
    return None


def sync_pending_refunds(db: Database, *, older_than_minutes: int = 2, limit: int = 20, retrieve=None,
                         list_refunds=None) -> Dict[str, int]:
    """Polling fallback while webhooks are not delivered: re-read refunds that stayed processing.

    A refund whose create call ended in a network error has no Stripe id (outcome uncertain, A03-BUG-007). It is
    looked up by its metadata, never created again; when Stripe has no such refund the request is marked failed so
    an administrator can approve it again.
    """
    from app.config.settings import settings
    if retrieve is None:
        if not (settings.STRIPE_SECRET_KEY or "").startswith(("sk_test_", "sk_live_", "rk_")):
            return {"checked": 0}
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        retrieve = stripe.Refund.retrieve
        list_refunds = list_refunds or _list_refunds_for_intent
    cutoff = utc_now() - timedelta(minutes=older_than_minutes)
    stats: Dict[str, int] = {"checked": 0}
    # Least recently checked first, and every check is stamped: refunds that stay pending for days can no longer
    # occupy the whole batch and starve newer ones (A03-BUG-008).
    query = {"status": {"$in": [PROCESSING, "PROCESSING"]}, "updatedAt": {"$lt": cutoff}}
    for request in db["refund_requests"].find(query).sort([("lastStripeSyncAt", 1), ("_id", 1)]).limit(limit):
        stats["checked"] += 1
        db["refund_requests"].update_one({"_id": request["_id"]}, {"$set": {"lastStripeSyncAt": utc_now()}})
        try:
            if request.get("stripeRefundId"):
                outcome = apply_refund_state(db, retrieve(request["stripeRefundId"]), source="sync")
            elif list_refunds is None:   # a caller that injected only retrieve: no lookup by metadata
                outcome = "skipped_no_lookup"
            else:
                payment = db["payments"].find_one({"_id": ObjectId(request["paymentId"])})                     if ObjectId.is_valid(str(request.get("paymentId"))) else None
                found = find_refund_by_request(payment["stripePaymentIntentId"], request["refundId"], list_refunds)                     if payment and payment.get("stripePaymentIntentId") else None
                if found is not None:
                    outcome = apply_refund_state(db, found, source="sync")
                else:
                    db["refund_requests"].update_one(
                        {"_id": request["_id"], "status": request["status"], "stripeRefundId": None},
                        {"$set": {"status": FAILED, "stripeOutcome": "not_created",
                                  "failureReason": "Stripe has no refund for this request", "updatedAt": utc_now()}})
                    outcome = "uncertain_not_created"
        except Exception as exc:  # network failure: try again next cycle
            outcome = f"error_{type(exc).__name__}"
        stats[outcome] = stats.get(outcome, 0) + 1
    return stats
