"""Authoritative platform money figures and Asia/Colombo date ranges (Phase 04, P04-N05/N06).

Before Phase 04, four places computed "revenue" in different ways: the dashboard overview, payment analytics,
the admin assistant and the financial report. They excluded REFUNDED payments from the gross and then subtracted
those refunds again (double counting), ignored partial refunds recorded as ``refundedAmount`` on a SUCCEEDED
payment, took refund-request *requested* amounts as refunded amounts, reported a 100% payment success rate when
there were no payments, and invented a "10% platform fee". Dates were UTC days, not Sri Lankan days.

Definitions used everywhere now (per currency, never mixed):

- capturedAmount   ("gross collections"): amount of payments that were actually captured (SUCCEEDED or REFUNDED).
- refundedAmount   : money returned on those payments. ``refundedAmount`` on the payment when recorded, otherwise
                     the full amount for a REFUNDED payment; never more than the captured amount.
- netCollected     ("net collections"): capturedAmount - refundedAmount.
- pendingRefunds   : refund requests still open (requested, under review, approved, processing or failed and
                     retryable) and the amount the policy or the admin set for them. Not yet returned.
- platformRevenue / doctorEarnings: None. MediConnect has no configured platform fee or doctor payout model, so
                     no profit or earnings figure can be derived. Gross collections are not platform profit.

Payments are placed in a date range by ``paidAt`` (falling back to ``createdAt``), using Asia/Colombo calendar days.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any, Dict, Iterable, Optional, Tuple

from fastapi import HTTPException

PLATFORM_TZ = timezone(timedelta(hours=5, minutes=30))  # Asia/Colombo has no daylight saving time
PLATFORM_TZ_NAME = "Asia/Colombo"
OPEN_REFUND_STATUSES = ("requested", "under_review", "approved", "processing", "failed")
CAPTURED_PAYMENT_STATUSES = ("SUCCEEDED", "REFUNDED")
NO_REVENUE_MODEL_NOTE = ("Gross collections are patient payments, not platform profit. No platform fee or doctor "
                         "payout model is configured in MediConnect, so platform revenue and doctor earnings are "
                         "not calculated.")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def platform_today() -> date:
    return datetime.now(PLATFORM_TZ).date()


def parse_platform_date(value: Optional[str], field: str) -> Optional[date]:
    """Parse YYYY-MM-DD strictly; an invalid value is a 400, never silently replaced by a default range."""
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    if not _DATE.match(text):
        raise HTTPException(400, f"Invalid {field} format. Expected YYYY-MM-DD.")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise HTTPException(400, f"Invalid {field} value. Expected a valid YYYY-MM-DD calendar date.")


def platform_range(start: Optional[str], end: Optional[str], *, default_days: Optional[int] = None
                   ) -> Tuple[Optional[datetime], Optional[datetime], Optional[str], Optional[str]]:
    """Asia/Colombo calendar-day bounds as UTC datetimes (end inclusive), plus the YYYY-MM-DD strings.

    With ``default_days`` and no dates, the range is the last ``default_days`` days ending today.
    """
    start_d = parse_platform_date(start, "startDate")
    end_d = parse_platform_date(end, "endDate")
    if default_days and not start_d and not end_d:
        end_d = platform_today()
        start_d = end_d - timedelta(days=default_days - 1)
    if start_d and end_d and start_d > end_d:
        raise HTTPException(400, "startDate cannot be after endDate.")
    start_dt = datetime.combine(start_d, time.min, PLATFORM_TZ).astimezone(timezone.utc) if start_d else None
    end_dt = (datetime.combine(end_d + timedelta(days=1), time.min, PLATFORM_TZ).astimezone(timezone.utc)
              - timedelta(microseconds=1)) if end_d else None
    return start_dt, end_dt, (start_d.isoformat() if start_d else None), (end_d.isoformat() if end_d else None)


def _range_filter(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Dict[str, Any]:
    cond: Dict[str, Any] = {}
    if start_dt:
        cond["$gte"] = start_dt
    if end_dt:
        cond["$lte"] = end_dt
    return cond


def payment_time_query(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Dict[str, Any]:
    """Mongo filter placing a payment in the range by paidAt, or createdAt when it was never paid."""
    cond = _range_filter(start_dt, end_dt)
    if not cond:
        return {}
    return {"$or": [{"paidAt": cond}, {"paidAt": None, "createdAt": cond}]}


def _money(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def payment_refunded_amount(payment: Dict[str, Any]) -> float:
    """Money returned on one payment, capped at what was captured."""
    amount = _money(payment.get("amount"))
    recorded = payment.get("refundedAmount")
    if recorded is not None:
        refunded = _money(recorded)
    else:
        refunded = amount if payment.get("status") == "REFUNDED" else 0.0
    return round(max(0.0, min(refunded, amount)), 2)


def collections(payments: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per-currency captured / refunded / net figures from payment documents."""
    out: Dict[str, Dict[str, Any]] = {}
    for p in payments:
        if p.get("status") not in CAPTURED_PAYMENT_STATUSES:
            continue
        cur = (p.get("currency") or "lkr").lower()
        row = out.setdefault(cur, {"currency": cur, "capturedAmount": 0.0, "refundedAmount": 0.0,
                                   "netCollected": 0.0, "capturedCount": 0, "fullyRefundedCount": 0,
                                   "partiallyRefundedCount": 0})
        amount = _money(p.get("amount"))
        refunded = payment_refunded_amount(p)
        row["capturedAmount"] += amount
        row["refundedAmount"] += refunded
        row["capturedCount"] += 1
        if amount > 0 and refunded >= amount:
            row["fullyRefundedCount"] += 1
        elif refunded > 0:
            row["partiallyRefundedCount"] += 1
    for row in out.values():
        row["capturedAmount"] = round(row["capturedAmount"], 2)
        row["refundedAmount"] = round(row["refundedAmount"], 2)
        row["netCollected"] = round(row["capturedAmount"] - row["refundedAmount"], 2)
    return out


def pending_refunds(db, appointment_ids: Optional[Iterable[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Open refund requests and the amount set for them (policy amount, or the admin-approved amount)."""
    query: Dict[str, Any] = {"status": {"$in": list(OPEN_REFUND_STATUSES)}}
    if appointment_ids is not None:
        query["appointmentId"] = {"$in": list(appointment_ids)}
    out: Dict[str, Dict[str, Any]] = {}
    for r in db["refund_requests"].find(query, {"currency": 1, "approvedAmount": 1, "policyEligibility": 1,
                                                "status": 1}):
        cur = (r.get("currency") or "lkr").lower()
        row = out.setdefault(cur, {"currency": cur, "count": 0, "amount": 0.0, "failedCount": 0})
        amount = r.get("approvedAmount")
        if amount is None:
            amount = (r.get("policyEligibility") or {}).get("eligibleAmount")
        row["count"] += 1
        row["amount"] = round(row["amount"] + _money(amount), 2)
        if r.get("status") == "failed":
            row["failedCount"] += 1
    return out


def platform_financials(db, start_dt: Optional[datetime] = None, end_dt: Optional[datetime] = None
                        ) -> Dict[str, Any]:
    """Platform-wide money summary for payments placed in the range (all time when no range)."""
    query = {"status": {"$in": list(CAPTURED_PAYMENT_STATUSES)}, **payment_time_query(start_dt, end_dt)}
    fields = {"amount": 1, "currency": 1, "status": 1, "refundedAmount": 1}
    by_currency = collections(db["payments"].find(query, fields))
    status_query = payment_time_query(start_dt, end_dt)
    counts = {s: db["payments"].count_documents({**status_query, "status": s})
              for s in ("SUCCEEDED", "REFUNDED", "FAILED", "PENDING", "CANCELLED")}
    attempts = counts["SUCCEEDED"] + counts["REFUNDED"] + counts["FAILED"]
    return {
        "byCurrency": by_currency,
        "pendingRefunds": pending_refunds(db),
        "paymentCounts": counts,
        # None, not 100%, when nothing was attempted: there is nothing to compute a rate from.
        "paymentSuccessRate": round((counts["SUCCEEDED"] + counts["REFUNDED"]) / attempts * 100.0, 1) if attempts else None,
        "platformRevenue": None,
        "doctorEarnings": None,
        "note": NO_REVENUE_MODEL_NOTE,
        "timezone": PLATFORM_TZ_NAME,
    }
