"""Service implementing aggregation queries and statistics for the Admin Analytics Dashboard (Phase 24)."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from pymongo.database import Database

from app.config.settings import Settings
from app.models.appointment import AppointmentStatus, get_appointment_collection
from app.models.doctor_profile import DoctorVerificationStatus, get_doctor_profile_collection
from app.models.health_content import ContentStatus, SUPPORTED_CATEGORIES, get_content_bookmark_collection, get_health_content_collection
from app.models.payment import PaymentStatus, get_payment_collection
from app.models.user import UserRole, get_user_collection
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AppointmentAnalyticsResponse,
    CategoryAnalyticsItem,
    ContentAnalyticsResponse,
    CurrencyRevenue,
    DoctorAnalyticsResponse,
    PaymentAnalyticsResponse,
    PaymentTransactionSummary,
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
        """Validate and parse ISO/YYYY-MM-DD date strings into UTC datetimes."""
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        parsed_start = None
        parsed_end = None

        if start_date:
            s = start_date.strip()
            if not date_pattern.match(s):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid startDate format. Expected YYYY-MM-DD.",
                )
            try:
                parsed_start = datetime.strptime(s, "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid startDate value. Expected valid YYYY-MM-DD calendar date.",
                )

        if end_date:
            e = end_date.strip()
            if not date_pattern.match(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid endDate format. Expected YYYY-MM-DD.",
                )
            try:
                parsed_end = datetime.strptime(e, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid endDate value. Expected valid YYYY-MM-DD calendar date.",
                )

        if parsed_start and parsed_end and parsed_start > parsed_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="startDate cannot be after endDate.",
            )

        return parsed_start, parsed_end, start_date, end_date

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
        total_patients = users_coll.count_documents({"role": UserRole.PATIENT.value})
        total_verified_doctors = doc_coll.count_documents(
            {"verificationStatus": DoctorVerificationStatus.APPROVED.value}
        )
        pending_doctors = doc_coll.count_documents(
            {"verificationStatus": DoctorVerificationStatus.PENDING.value}
        )
        rejected_doctors = doc_coll.count_documents(
            {"verificationStatus": DoctorVerificationStatus.REJECTED.value}
        )

        # Appointments filter
        appt_query: Dict[str, Any] = {}
        if parsed_start and parsed_end:
            appt_query["$or"] = [
                {"createdAt": {"$gte": parsed_start, "$lte": parsed_end}},
                {"appointmentDate": {"$gte": s_str, "$lte": e_str}},
            ]
        elif parsed_start:
            appt_query["$or"] = [
                {"createdAt": {"$gte": parsed_start}},
                {"appointmentDate": {"$gte": s_str}},
            ]
        elif parsed_end:
            appt_query["$or"] = [
                {"createdAt": {"$lte": parsed_end}},
                {"appointmentDate": {"$lte": e_str}},
            ]

        total_appts = appt_coll.count_documents(appt_query)
        confirmed_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.CONFIRMED.value})
        completed_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.COMPLETED.value})
        cancelled_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.CANCELLED.value})
        pending_appts = appt_coll.count_documents({**appt_query, "status": AppointmentStatus.PENDING.value})

        # Payments & Revenue accounting
        pay_query: Dict[str, Any] = {}
        if parsed_start and parsed_end:
            pay_query["createdAt"] = {"$gte": parsed_start, "$lte": parsed_end}
        elif parsed_start:
            pay_query["createdAt"] = {"$gte": parsed_start}
        elif parsed_end:
            pay_query["createdAt"] = {"$lte": parsed_end}

        # Revenue grouping by currency (SUCCEEDED vs REFUNDED)
        pipeline = [
            {"$match": {**pay_query, "status": {"$in": [PaymentStatus.SUCCEEDED.value, PaymentStatus.REFUNDED.value]}}},
            {
                "$group": {
                    "_id": "$currency",
                    "grossAmount": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", PaymentStatus.SUCCEEDED.value]}, "$amount", 0.0]
                        }
                    },
                    "refundedAmount": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", PaymentStatus.REFUNDED.value]}, "$amount", 0.0]
                        }
                    },
                    "paymentCount": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", PaymentStatus.SUCCEEDED.value]}, 1, 0]
                        }
                    },
                }
            },
        ]
        rev_results = list(pay_coll.aggregate(pipeline))
        currencies_rev = []
        for r in rev_results:
            cur = (r["_id"] or "lkr").lower()
            gross = float(r.get("grossAmount", 0.0))
            refunded = float(r.get("refundedAmount", 0.0))
            net = max(0.0, round(gross - refunded, 2))
            currencies_rev.append(
                CurrencyRevenue(
                    currency=cur,
                    grossAmount=round(gross, 2),
                    refundedAmount=round(refunded, 2),
                    netAmount=net,
                    paymentCount=int(r.get("paymentCount", 0)),
                )
            )

        if not currencies_rev:
            currencies_rev.append(CurrencyRevenue(currency="lkr", grossAmount=0.0, refundedAmount=0.0, netAmount=0.0, paymentCount=0))

        # Payments count
        succeeded_query = {**pay_query, "status": PaymentStatus.SUCCEEDED.value}
        successful_count = pay_coll.count_documents(succeeded_query)

        # Test vs live breakdown
        all_succeeded = list(pay_coll.find(succeeded_query, {"stripePaymentIntentId": 1}))
        test_count = sum(1 for p in all_succeeded if cls._is_test_payment(p.get("stripePaymentIntentId", "")))
        live_count = len(all_succeeded) - test_count

        # Content counts
        total_articles = content_coll.count_documents({})
        published_articles = content_coll.count_documents({"status": ContentStatus.PUBLISHED.value})
        draft_articles = content_coll.count_documents({"status": ContentStatus.DRAFT.value})
        total_bookmarks = bm_coll.count_documents({})

        return AnalyticsOverviewResponse(
            totalPatients=total_patients,
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

        return AppointmentAnalyticsResponse(
            totalAppointments=total,
            statusBreakdown=status_map,
            trends=trends,
            completionRate=completion_rate,
            cancellationRate=cancellation_rate,
            startDate=s_str,
            endDate=e_str,
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

        # Status counts
        status_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        s_counts = {r["_id"]: r["count"] for r in pay_coll.aggregate(status_pipeline)}

        succeeded_count = s_counts.get(PaymentStatus.SUCCEEDED.value, 0)
        failed_count = s_counts.get(PaymentStatus.FAILED.value, 0)
        refunded_count = s_counts.get(PaymentStatus.REFUNDED.value, 0)

        # Revenue per currency
        rev_pipeline = [
            {"$match": {**query, "status": {"$in": [PaymentStatus.SUCCEEDED.value, PaymentStatus.REFUNDED.value]}}},
            {
                "$group": {
                    "_id": "$currency",
                    "grossAmount": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", PaymentStatus.SUCCEEDED.value]}, "$amount", 0.0]
                        }
                    },
                    "refundedAmount": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", PaymentStatus.REFUNDED.value]}, "$amount", 0.0]
                        }
                    },
                    "paymentCount": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", PaymentStatus.SUCCEEDED.value]}, 1, 0]
                        }
                    },
                }
            },
        ]
        rev_records = list(pay_coll.aggregate(rev_pipeline))
        revenue_by_curr = []
        for r in rev_records:
            gross = float(r.get("grossAmount", 0.0))
            refunded = float(r.get("refundedAmount", 0.0))
            revenue_by_curr.append(
                CurrencyRevenue(
                    currency=(r["_id"] or "lkr").lower(),
                    grossAmount=round(gross, 2),
                    refundedAmount=round(refunded, 2),
                    netAmount=max(0.0, round(gross - refunded, 2)),
                    paymentCount=int(r.get("paymentCount", 0)),
                )
            )

        if not revenue_by_curr:
            revenue_by_curr.append(CurrencyRevenue(currency="lkr", grossAmount=0.0, refundedAmount=0.0, netAmount=0.0, paymentCount=0))

        # Test vs live payments check
        succeeded_docs = list(pay_coll.find({**query, "status": PaymentStatus.SUCCEEDED.value}))
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
        pending = doc_coll.count_documents({"verificationStatus": DoctorVerificationStatus.PENDING.value})
        rejected = doc_coll.count_documents({"verificationStatus": DoctorVerificationStatus.REJECTED.value})

        # Specialty distribution
        pipeline = [
            {"$match": {"verificationStatus": DoctorVerificationStatus.APPROVED.value}},
            {"$group": {"_id": "$specialty", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        specialty_docs = list(doc_coll.aggregate(pipeline))
        specialties = [
            SpecialtyCountItem(specialty=r["_id"] or "General Practice", count=r["count"])
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
        avg_exp = round(float(avg_res[0]["avgExp"]), 1) if avg_res and avg_res[0].get("avgExp") is not None else 0.0
        avg_fee = round(float(avg_res[0]["avgFee"]), 2) if avg_res and avg_res[0].get("avgFee") is not None else 0.0

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
