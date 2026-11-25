"""Service implementing aggregation queries and statistics for the Admin Analytics Dashboard (Phase 24)."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.config.settings import Settings
from app.models.appointment import AppointmentStatus, get_appointment_collection
from app.models.doctor_profile import DoctorVerificationStatus, get_doctor_profile_collection
from app.models.health_content import ContentStatus, SUPPORTED_CATEGORIES, get_content_bookmark_collection, get_health_content_collection
from app.models.payment import PaymentStatus, get_payment_collection
from app.models.user import AccountStatus, UserRole, get_user_collection
from app.services.financial_metrics import NO_REVENUE_MODEL_NOTE, payment_time_query, platform_financials, platform_range
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AppointmentAnalyticsResponse,
    CategoryAnalyticsItem,
    ContentAnalyticsResponse,
    CurrencyRevenue,
    DoctorAnalyticsResponse,
    OverviewTotalsSchema,
    PaymentAnalyticsResponse,
    PaymentRevenueBreakdownSchema,
    PaymentTransactionSummary,
    RecentActivityItemSchema,
    SpecialtyCountItem,
    TopContentItem,
    TrendDataPoint,
)

logger = logging.getLogger(__name__)
settings = Settings()


class AnalyticsService:
    """Calculates privacy-preserving aggregate metrics and trends for MediConnect administrators."""

    @classmethod
    def _parse_date_range(
        cls, start_date: Optional[str], end_date: Optional[str]
    ) -> Tuple[Optional[datetime], Optional[datetime], Optional[str], Optional[str]]:
        """Validate YYYY-MM-DD dates and return Asia/Colombo calendar-day bounds in UTC (P04-N06).

        Before Phase 04 the bounds were UTC midnights, so a payment made at 03:00 in Sri Lanka was counted on the
        previous day.
        """
        return platform_range(start_date, end_date)

    @staticmethod
    def _currency_rows(fin: Dict[str, Any]) -> List[CurrencyRevenue]:
        rows = []
        currencies = sorted(set(fin["byCurrency"]) | set(fin["pendingRefunds"])) or ["lkr"]
        for cur in currencies:
            c = fin["byCurrency"].get(cur, {})
            pend = fin["pendingRefunds"].get(cur, {})
            rows.append(CurrencyRevenue(
                currency=cur, grossAmount=c.get("capturedAmount", 0.0), refundedAmount=c.get("refundedAmount", 0.0),
                netAmount=c.get("netCollected", 0.0), paymentCount=c.get("capturedCount", 0),
                partiallyRefundedCount=c.get("partiallyRefundedCount", 0),
                fullyRefundedCount=c.get("fullyRefundedCount", 0),
                pendingRefundAmount=pend.get("amount", 0.0), pendingRefundCount=pend.get("count", 0)))
        return rows

    @classmethod
    def _is_test_payment(cls, stripe_pi_id: str) -> bool:
        """Classify if payment was made using Stripe test environment."""
        key = (settings.STRIPE_SECRET_KEY or "").lower()
        if "test" in key or key.startswith("sk_test_"):
            return True
        pi_lower = (stripe_pi_id or "").lower()
        return "test" in pi_lower or "mock" in pi_lower

    # -------------------------------------------------------------------------
    # 1. Platform Overview
    # -------------------------------------------------------------------------

    @classmethod
    async def get_overview(
        cls, db: Database, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> AnalyticsOverviewResponse:
        """Aggregate high-level platform health metrics."""
        parsed_start, parsed_end, s_str, e_str = cls._parse_date_range(start_date, end_date)

        users_coll = get_user_collection(db)
        doc_coll = get_doctor_profile_collection(db)
        appt_coll = get_appointment_collection(db)
        pay_coll = get_payment_collection(db)
        content_coll = get_health_content_collection(db)
        bm_coll = get_content_bookmark_collection(db)

        # Users & Doctors
        total_users = users_coll.count_documents({})
        total_patients = users_coll.count_documents({"role": UserRole.PATIENT.value})
        total_doctors = doc_coll.count_documents({})
        total_verified_doctors = doc_coll.count_documents(
            {"verificationStatus": DoctorVerificationStatus.APPROVED.value}
        )
        pending_doctors = doc_coll.count_documents({"verificationStatus": {"$in": [
            DoctorVerificationStatus.PENDING.value, DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
            DoctorVerificationStatus.PENDING_EMAIL_VERIFICATION.value]}})
        approved_user_ids = [str(d.get("userId")) for d in doc_coll.find(
            {"verificationStatus": DoctorVerificationStatus.APPROVED.value}, {"userId": 1})]
        approved_oids = [ObjectId(u) for u in approved_user_ids if ObjectId.is_valid(u)]
        active_approved = users_coll.count_documents({"_id": {"$in": approved_oids},
                                                      "accountStatus": AccountStatus.ACTIVE.value})
        suspended_doctors = users_coll.count_documents({"role": UserRole.DOCTOR.value,
                                                        "accountStatus": AccountStatus.SUSPENDED.value})
        rejected_doctors = doc_coll.count_documents(
            {"verificationStatus": DoctorVerificationStatus.REJECTED.value}
        )

        # Appointments are placed in a range by their (Asia/Colombo) appointment date only; mixing createdAt and
        # appointmentDate counted the same booking under two different meanings.
        appt_query: Dict[str, Any] = {}
        if s_str or e_str:
            appt_query["appointmentDate"] = {**({"$gte": s_str} if s_str else {}), **({"$lte": e_str} if e_str else {})}

        total_appts = appt_coll.count_documents(appt_query)
        confirmed_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.CONFIRMED.value})
        completed_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.COMPLETED.value})
        cancelled_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.CANCELLED.value})
        pending_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.PENDING.value})

        # Money: one authoritative calculation (P04-N05). Gross collections include refunded payments, refunds
        # include partial refunds, and nothing is presented as platform revenue.
        fin = platform_financials(db, parsed_start, parsed_end)
        currencies_rev = cls._currency_rows(fin)
        pay_query = payment_time_query(parsed_start, parsed_end)
        successful_count = fin["paymentCounts"]["SUCCEEDED"]

        # Every recorded SUCCEEDED payment was verified against the configured Stripe key (a livemode mismatch is
        # rejected), so the key's mode is the payment's mode.
        succeeded_query = {**pay_query, "status": PaymentStatus.SUCCEEDED.value}
        all_succeeded = list(pay_coll.find(succeeded_query, {"stripePaymentIntentId": 1}))
        test_count = sum(1 for p in all_succeeded if cls._is_test_payment(p.get("stripePaymentIntentId", "")))
        live_count = len(all_succeeded) - test_count

        # Content counts
        total_articles = content_coll.count_documents({})
        published_articles = content_coll.count_documents({"status": ContentStatus.PUBLISHED.value})
        draft_articles = content_coll.count_documents({"status": ContentStatus.DRAFT.value})
        total_bookmarks = bm_coll.count_documents({})

        # Structured totals object for Admin Web Dashboard
        totals_obj = OverviewTotalsSchema(
            totalUsers=total_users,
            totalPatients=total_patients,
            totalDoctors=total_doctors,
            verifiedDoctors=total_verified_doctors,
            pendingDoctorApprovals=pending_doctors,
            totalAppointments=total_appts,
            completedAppointments=completed_appts,
            cancelledAppointments=cancelled_appts,
            confirmedAppointments=confirmed_appts,
            pendingAppointments=pending_appts,
            rejectedDoctorApplications=rejected_doctors,
            activeApprovedDoctors=active_approved,
            suspendedDoctors=suspended_doctors,
        )

        # Revenue breakdown map by currency
        rev_map = {r.currency.upper(): r.netAmount for r in currencies_rev}
        payments_obj = PaymentRevenueBreakdownSchema(
            totalRevenueByCurrency=rev_map,
            netCollectedByCurrency=rev_map,
            capturedByCurrency={r.currency.upper(): r.grossAmount for r in currencies_rev},
            refundedByCurrency={r.currency.upper(): r.refundedAmount for r in currencies_rev},
            pendingRefundsByCurrency={c.upper(): v["amount"] for c, v in fin["pendingRefunds"].items()},
            pendingRefundRequests=sum(v["count"] for v in fin["pendingRefunds"].values()),
            succeededTransactions=successful_count,
            refundedTransactions=fin["paymentCounts"]["REFUNDED"],
            failedTransactions=fin["paymentCounts"]["FAILED"],
            pendingTransactions=fin["paymentCounts"]["PENDING"],
            paymentSuccessRate=fin["paymentSuccessRate"],
            platformRevenue=None,
            note=NO_REVENUE_MODEL_NOTE,
        )

        # Build recent activity log from latest events across collections
        recent_activity: List[RecentActivityItemSchema] = []
        recent_docs = doc_coll.find().sort([("createdAt", -1)]).limit(5)
        for d in recent_docs:
            st = d.get("verificationStatus", "PENDING")
            ts = d.get("updatedAt") or d.get("createdAt") or datetime.now(timezone.utc)
            action_type = "DOCTOR_VERIFIED" if st == "APPROVED" else "DOCTOR_APPLICATION"
            recent_activity.append(
                RecentActivityItemSchema(
                    type=action_type,
                    description=f"Doctor profile {st.lower().replace('_', ' ')}"
                                + (f" ({d['medicalRegistrationNumber']})" if d.get("medicalRegistrationNumber") else ""),
                    timestamp=ts if isinstance(ts, datetime) else datetime.now(timezone.utc),
                )
            )
        recent_appts = appt_coll.find().sort([("createdAt", -1)]).limit(5)
        for a in recent_appts:
            ts = a.get("createdAt") or datetime.now(timezone.utc)
            recent_activity.append(
                RecentActivityItemSchema(
                    type="APPOINTMENT_SCHEDULED",
                    description=f"Appointment {str(a.get('status', 'BOOKED')).lower()} for date {a.get('appointmentDate', '')}",
                    timestamp=ts if isinstance(ts, datetime) else datetime.now(timezone.utc),
                )
            )
        recent_users = users_coll.find().sort([("createdAt", -1)]).limit(5)
        for u in recent_users:
            ts = u.get("createdAt") or datetime.now(timezone.utc)
            recent_activity.append(
                RecentActivityItemSchema(
                    type="USER_REGISTERED",
                    description=f"New {str(u.get('role', 'PATIENT')).lower()} account: {u.get('fullName', 'User')}",
                    timestamp=ts if isinstance(ts, datetime) else datetime.now(timezone.utc),
                )
            )
        recent_activity.sort(key=lambda x: x.timestamp, reverse=True)
        recent_activity = recent_activity[:10]

        return AnalyticsOverviewResponse(
            totalUsers=total_users,
            totalPatients=total_patients,
            totalDoctors=total_doctors,
            totalVerifiedDoctors=total_verified_doctors,
            pendingDoctorApprovals=pending_doctors,
            rejectedDoctorApplications=rejected_doctors,
            totalAppointments=total_appts,
            confirmedAppointments=confirmed_appts,
            completedAppointments=completed_appts,
            cancelledAppointments=cancelled_appts,
            pendingAppointments=pending_appts,
            totalRevenueByCurrency=currencies_rev,
            successfulPaymentsCount=successful_count,
            testPaymentsCount=test_count,
            livePaymentsCount=live_count,
            totalArticles=total_articles,
            publishedArticles=published_articles,
            draftArticles=draft_articles,
            totalBookmarks=total_bookmarks,
            startDate=s_str,
            endDate=e_str,
            totals=totals_obj,
            payments=payments_obj,
            recentActivity=recent_activity,
        )

    # -------------------------------------------------------------------------
    # 2. Appointment Analytics
    # -------------------------------------------------------------------------

    @classmethod
    async def get_appointments_analytics(
        cls, db: Database, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> AppointmentAnalyticsResponse:
        """Retrieve appointment volume, completion rates, and daily trend points."""
        parsed_start, parsed_end, s_str, e_str = cls._parse_date_range(start_date, end_date)
        appt_coll = get_appointment_collection(db)

        query: Dict[str, Any] = {}
        if parsed_start and parsed_end:
            query["appointmentDate"] = {"$gte": s_str, "$lte": e_str}
        elif parsed_start:
            query["appointmentDate"] = {"$gte": s_str}
        elif parsed_end:
            query["appointmentDate"] = {"$lte": e_str}

        total = appt_coll.count_documents(query)

        # Status breakdown
        pipeline_status = [
            {"$match": query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        status_map = {r["_id"]: r["count"] for r in appt_coll.aggregate(pipeline_status)}
        for st in [AppointmentStatus.COMPLETED.value, AppointmentStatus.CONFIRMED.value, AppointmentStatus.PENDING.value, AppointmentStatus.CANCELLED.value, AppointmentStatus.HOLD.value]:
            status_map.setdefault(st, 0)

        completed = status_map.get(AppointmentStatus.COMPLETED.value, 0)
        cancelled = status_map.get(AppointmentStatus.CANCELLED.value, 0)
        confirmed = status_map.get(AppointmentStatus.CONFIRMED.value, 0)

        non_cancelled = total - cancelled
        completion_rate = round((completed / non_cancelled * 100.0), 1) if non_cancelled > 0 else 0.0
        cancellation_rate = round((cancelled / total * 100.0), 1) if total > 0 else 0.0

        # Daily trends
        pipeline_trends = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$appointmentDate",
                    "total": {"$sum": 1},
                    "completed": {
                        "$sum": {"$cond": [{"$eq": ["$status", AppointmentStatus.COMPLETED.value]}, 1, 0]}
                    },
                    "confirmed": {
                        "$sum": {"$cond": [{"$eq": ["$status", AppointmentStatus.CONFIRMED.value]}, 1, 0]}
                    },
                    "cancelled": {
                        "$sum": {"$cond": [{"$eq": ["$status", AppointmentStatus.CANCELLED.value]}, 1, 0]}
                    },
                }
            },
            {"$sort": {"_id": 1}},
            {"$limit": 31},
        ]
        trend_docs = list(appt_coll.aggregate(pipeline_trends))
        trends = [
            TrendDataPoint(
                date=str(t["_id"]),
                total=t["total"],
                completed=t["completed"],
                confirmed=t["confirmed"],
                cancelled=t["cancelled"],
            )
            for t in trend_docs
            if t["_id"]
        ]

        daily_trends = [{"date": t.date, "count": t.total} for t in trends]
        return AppointmentAnalyticsResponse(
            totalAppointments=total,
            statusBreakdown=status_map,
            trends=trends,
            completionRate=completion_rate,
            cancellationRate=cancellation_rate,
            startDate=s_str,
            endDate=e_str,
            totalBookings=total,
            completedBookings=completed,
            cancelledBookings=cancelled,
            completionRatePercent=completion_rate,
            dailyTrends=daily_trends,
        )

    # -------------------------------------------------------------------------
    # 3. Payment & Revenue Analytics
    # -------------------------------------------------------------------------

    @classmethod
    async def get_payments_analytics(
        cls, db: Database, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> PaymentAnalyticsResponse:
        """Detailed revenue breakdown by currency, test payments distinction, and refunds."""
        parsed_start, parsed_end, s_str, e_str = cls._parse_date_range(start_date, end_date)
        pay_coll = get_payment_collection(db)

        query: Dict[str, Any] = {}
        if parsed_start and parsed_end:
            query["createdAt"] = {"$gte": parsed_start, "$lte": parsed_end}
        elif parsed_start:
            query["createdAt"] = {"$gte": parsed_start}
        elif parsed_end:
            query["createdAt"] = {"$lte": parsed_end}

        fin = platform_financials(db, parsed_start, parsed_end)
        query = payment_time_query(parsed_start, parsed_end)
        counts = fin["paymentCounts"]
        succeeded_count = counts["SUCCEEDED"]
        failed_count = counts["FAILED"]
        refunded_count = counts["REFUNDED"]
        revenue_by_curr = cls._currency_rows(fin)

        succeeded_docs = list(pay_coll.find({**query, "status": PaymentStatus.SUCCEEDED.value}, {"stripePaymentIntentId": 1}))
        test_count = sum(1 for p in succeeded_docs if cls._is_test_payment(p.get("stripePaymentIntentId", "")))
        live_count = len(succeeded_docs) - test_count

        # Recent transactions safe preview (no card credentials)
        recent_cursor = (
            pay_coll.find(query)
            .sort([("createdAt", -1)])
            .limit(15)
        )
        recent_txs = [
            PaymentTransactionSummary(
                id=str(tx["_id"]),
                appointmentId=str(tx.get("appointmentId", "")),
                amount=float(tx.get("amount", 0.0)),
                currency=(tx.get("currency") or "lkr").lower(),
                status=str(tx.get("status", PaymentStatus.PENDING.value)),
                isTestPayment=cls._is_test_payment(tx.get("stripePaymentIntentId", "")),
                paidAt=tx.get("paidAt"),
                createdAt=tx.get("createdAt", datetime.now(timezone.utc)),
            )
            for tx in recent_cursor
        ]

        is_test_mode = cls._is_test_payment("test")

        return PaymentAnalyticsResponse(
            successfulPaymentsCount=succeeded_count,
            testPaymentsCount=test_count,
            livePaymentsCount=live_count,
            failedPaymentsCount=failed_count,
            refundedPaymentsCount=refunded_count,
            revenueByCurrency=revenue_by_curr,
            isStripeTestMode=is_test_mode,
            recentTransactions=recent_txs,
            startDate=s_str,
            endDate=e_str,
            totalTransactions=succeeded_count + failed_count + refunded_count,
            succeededCount=succeeded_count,
            failedCount=failed_count,
            pendingCount=counts["PENDING"],
            cancelledCount=counts["CANCELLED"],
            paymentSuccessRate=fin["paymentSuccessRate"],
            platformRevenue=None,
            note=NO_REVENUE_MODEL_NOTE,
            dailyTrends=[],
        )

    # -------------------------------------------------------------------------
    # 4. Doctor Analytics
    # -------------------------------------------------------------------------

    @classmethod
    async def get_doctors_analytics(cls, db: Database) -> DoctorAnalyticsResponse:
        """Retrieve doctor verification status and medical specialty distribution."""
        doc_coll = get_doctor_profile_collection(db)

        total_doctors = doc_coll.count_documents({})
        approved = doc_coll.count_documents({"verificationStatus": DoctorVerificationStatus.APPROVED.value})
        pending = doc_coll.count_documents({"verificationStatus": {"$in": [
            DoctorVerificationStatus.PENDING.value, DoctorVerificationStatus.PENDING_ADMIN_APPROVAL.value,
            DoctorVerificationStatus.PENDING_EMAIL_VERIFICATION.value]}})
        rejected = doc_coll.count_documents({"verificationStatus": DoctorVerificationStatus.REJECTED.value})

        # Specialty distribution
        pipeline = [
            {"$match": {"verificationStatus": DoctorVerificationStatus.APPROVED.value}},
            {"$group": {"_id": "$specialty", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        specialty_docs = list(doc_coll.aggregate(pipeline))
        specialties = [
            SpecialtyCountItem(specialty=r["_id"] or "Not specified", count=r["count"])
            for r in specialty_docs
        ]

        # Averages for approved doctors
        avg_pipeline = [
            {"$match": {"verificationStatus": DoctorVerificationStatus.APPROVED.value}},
            {
                "$group": {
                    "_id": None,
                    "avgExp": {"$avg": "$experienceYears"},
                    "avgFee": {"$avg": "$consultationFee"},
                }
            },
        ]
        avg_res = list(doc_coll.aggregate(avg_pipeline))
        avg_exp = round(float(avg_res[0]["avgExp"]), 1) if avg_res and avg_res[0].get("avgExp") is not None else None
        avg_fee = round(float(avg_res[0]["avgFee"]), 2) if avg_res and avg_res[0].get("avgFee") is not None else None

        return DoctorAnalyticsResponse(
            totalDoctors=total_doctors,
            approvedDoctors=approved,
            pendingDoctors=pending,
            rejectedDoctors=rejected,
            specialtyDistribution=specialties,
            averageExperienceYears=avg_exp,
            averageConsultationFee=avg_fee,
        )

    # -------------------------------------------------------------------------
    # 5. Content Analytics
    # -------------------------------------------------------------------------

    @classmethod
    async def get_content_analytics(cls, db: Database) -> ContentAnalyticsResponse:
        """Content publishing metrics and bookmark engagement summaries."""
        content_coll = get_health_content_collection(db)
        bm_coll = get_content_bookmark_collection(db)

        total = content_coll.count_documents({})
        published = content_coll.count_documents({"status": ContentStatus.PUBLISHED.value})
        draft = content_coll.count_documents({"status": ContentStatus.DRAFT.value})
        archived = content_coll.count_documents({"status": ContentStatus.ARCHIVED.value})
        total_bookmarks = bm_coll.count_documents({})

        # Category distribution
        pipeline_cats = [
            {
                "$group": {
                    "_id": "$category",
                    "count": {"$sum": 1},
                    "publishedCount": {
                        "$sum": {"$cond": [{"$eq": ["$status", ContentStatus.PUBLISHED.value]}, 1, 0]}
                    },
                }
            }
        ]
        cat_map = {r["_id"]: r for r in content_coll.aggregate(pipeline_cats)}
        category_distribution = []
        for cat in SUPPORTED_CATEGORIES:
            found = cat_map.get(cat, {})
            category_distribution.append(
                CategoryAnalyticsItem(
                    category=cat,
                    count=found.get("count", 0),
                    publishedCount=found.get("publishedCount", 0),
                )
            )

        # Top bookmarked articles
        top_bm_pipeline = [
            {"$group": {"_id": "$contentId", "bookmarksCount": {"$sum": 1}}},
            {"$sort": {"bookmarksCount": -1}},
            {"$limit": 5},
        ]
        top_bm_docs = list(bm_coll.aggregate(top_bm_pipeline))
        top_items = []
        for b in top_bm_docs:
            cid = b["_id"]
            article = content_coll.find_one({"contentId": cid})
            if article:
                top_items.append(
                    TopContentItem(
                        contentId=article["contentId"],
                        title=article["title"],
                        category=article["category"],
                        bookmarksCount=b["bookmarksCount"],
                    )
                )

        return ContentAnalyticsResponse(
            totalArticles=total,
            publishedArticles=published,
            draftArticles=draft,
            archivedArticles=archived,
            categoryDistribution=category_distribution,
            totalBookmarks=total_bookmarks,
            topBookmarkedArticles=top_items,
        )
