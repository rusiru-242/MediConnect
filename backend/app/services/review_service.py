"""Service implementing business logic for doctor reviews and ratings (Phase 23)."""

from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import uuid
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.appointment import AppointmentStatus, get_appointment_collection
from app.models.doctor_profile import get_doctor_profile_collection
from app.models.review import (
    ReviewDocument,
    ReviewStatus,
    get_review_collection,
    mask_patient_name,
    utc_now,
)
from app.models.user import UserRole, get_user_collection
from app.schemas.review import (
    AdminReportedReviewItem,
    CreateReviewRequest,
    DoctorRatingSummaryResponse,
    ModerateReviewRequest,
    PatientReviewItem,
    PatientReviewListResponse,
    PublicReviewItem,
    PublicReviewListResponse,
    ReportReviewRequest,
    ReviewResponse,
    UpdateReviewRequest,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)


class ReviewService:
    """Manages verified patient reviews, ratings, aggregation, and moderation."""

    @classmethod
    def _resolve_doctor(cls, db: Database, doctor_identifier: str) -> Tuple[str, str]:
        """Resolve doctorUserId and doctorProfileId from any doctor identifier.

        doctor_identifier can be user._id, doctor_profiles._id, or doctorId.
        """
        prof_coll = get_doctor_profile_collection(db)
        doctor_doc = None

        if ObjectId.is_valid(doctor_identifier):
            obj_id = ObjectId(doctor_identifier)
            doctor_doc = prof_coll.find_one({"$or": [{"_id": obj_id}, {"userId": doctor_identifier}]})

        if not doctor_doc:
            doctor_doc = prof_coll.find_one({
                "$or": [
                    {"userId": doctor_identifier},
                    {"doctorId": doctor_identifier},
                ]
            })

        if doctor_doc:
            return str(doctor_doc.get("userId", "")), str(doctor_doc.get("_id", ""))

        # If only user ID is present in users collection
        user_coll = get_user_collection(db)
        if ObjectId.is_valid(doctor_identifier):
            u_doc = user_coll.find_one({"_id": ObjectId(doctor_identifier), "role": UserRole.DOCTOR.value})
            if u_doc:
                return str(u_doc["_id"]), doctor_identifier

        return doctor_identifier, doctor_identifier

    @classmethod
    async def create_review(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        req: CreateReviewRequest,
    ) -> ReviewResponse:
        """Create a new verified review for a completed appointment."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only registered patients may submit reviews.",
            )

        appt_coll = get_appointment_collection(db)
        appt_query: Dict[str, Any] = {}
        if ObjectId.is_valid(req.appointmentId):
            appt_query = {"$or": [{"_id": ObjectId(req.appointmentId)}, {"_id": req.appointmentId}]}
        else:
            appt_query = {"_id": req.appointmentId}

        appt = appt_coll.find_one(appt_query)
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        # Enforce patient ownership
        appt_patient_id = str(appt.get("patientUserId", ""))
        current_patient_id = str(patient_user.id)
        if appt_patient_id != current_patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review your own appointments.",
            )

        # Enforce completed status
        appt_status = str(appt.get("status", "")).upper()
        if appt_status != AppointmentStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reviews can only be submitted for completed appointments (current status: {appt_status}).",
            )

        # Check for existing review
        norm_appt_id = str(appt["_id"])
        review_coll = get_review_collection(db)
        existing = review_coll.find_one({"appointmentId": norm_appt_id})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This appointment has already been reviewed.",
            )

        doctor_user_id = str(appt.get("doctorUserId", ""))
        doctor_profile_id = str(appt.get("doctorProfileId", ""))

        review_ref_id = f"REV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        masked_name = mask_patient_name(patient_user.fullName)

        doc_data = {
            "reviewId": review_ref_id,
            "doctorUserId": doctor_user_id,
            "doctorProfileId": doctor_profile_id,
            "patientUserId": current_patient_id,
            "patientDisplayName": masked_name,
            "appointmentId": norm_appt_id,
            "rating": req.rating,
            "reviewText": req.reviewText,
            "status": ReviewStatus.PUBLISHED.value,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        }

        try:
            insert_result = review_coll.insert_one(doc_data)
            doc_data["_id"] = str(insert_result.inserted_id)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A review for this appointment already exists.",
            )

        return ReviewResponse(
            id=str(doc_data["_id"]),
            reviewId=doc_data["reviewId"],
            doctorUserId=doc_data["doctorUserId"],
            doctorProfileId=doc_data["doctorProfileId"],
            patientUserId=doc_data["patientUserId"],
            patientDisplayName=doc_data["patientDisplayName"],
            appointmentId=doc_data["appointmentId"],
            rating=doc_data["rating"],
            reviewText=doc_data.get("reviewText"),
            status=ReviewStatus(doc_data["status"]),
            verifiedAppointment=True,
            createdAt=doc_data["createdAt"],
            updatedAt=doc_data["updatedAt"],
        )

    @classmethod
    async def get_doctor_rating_summary(
        cls,
        db: Database,
        doctor_identifier: str,
    ) -> DoctorRatingSummaryResponse:
        """Aggregate ratings for a verified doctor based solely on published reviews."""
        doc_user_id, doc_profile_id = cls._resolve_doctor(db, doctor_identifier)

        review_coll = get_review_collection(db)
        match_criteria: Dict[str, Any] = {
            "$and": [
                {
                    "$or": [
                        {"doctorUserId": doc_user_id},
                        {"doctorProfileId": doc_profile_id},
                        {"doctorUserId": doctor_identifier},
                        {"doctorProfileId": doctor_identifier},
                    ]
                },
                {"status": ReviewStatus.PUBLISHED.value},
            ]
        }

        pipeline = [
            {"$match": match_criteria},
            {
                "$group": {
                    "_id": None,
                    "totalReviews": {"$sum": 1},
                    "averageRating": {"$avg": "$rating"},
                    "star1": {"$sum": {"$cond": [{"$eq": ["$rating", 1]}, 1, 0]}},
                    "star2": {"$sum": {"$cond": [{"$eq": ["$rating", 2]}, 1, 0]}},
                    "star3": {"$sum": {"$cond": [{"$eq": ["$rating", 3]}, 1, 0]}},
                    "star4": {"$sum": {"$cond": [{"$eq": ["$rating", 4]}, 1, 0]}},
                    "star5": {"$sum": {"$cond": [{"$eq": ["$rating", 5]}, 1, 0]}},
                }
            },
        ]

        results = list(review_coll.aggregate(pipeline))
        if not results:
            return DoctorRatingSummaryResponse(
                doctorId=doctor_identifier,
                doctorUserId=doc_user_id,
                doctorProfileId=doc_profile_id,
                averageRating=None,
                totalReviews=0,
                ratingDistribution={"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                hasReviews=False,
            )

        res = results[0]
        total = int(res.get("totalReviews", 0))
        avg = round(float(res.get("averageRating", 0.0)), 1) if total > 0 else None

        return DoctorRatingSummaryResponse(
            doctorId=doctor_identifier,
            doctorUserId=doc_user_id,
            doctorProfileId=doc_profile_id,
            averageRating=avg,
            totalReviews=total,
            ratingDistribution={
                "1": int(res.get("star1", 0)),
                "2": int(res.get("star2", 0)),
                "3": int(res.get("star3", 0)),
                "4": int(res.get("star4", 0)),
                "5": int(res.get("star5", 0)),
            },
            hasReviews=total > 0,
        )

    @classmethod
    async def list_doctor_public_reviews(
        cls,
        db: Database,
        doctor_identifier: str,
        page: int = 1,
        page_size: int = 10,
    ) -> PublicReviewListResponse:
        """List verified public reviews for a doctor with privacy-preserving display."""
        doc_user_id, doc_profile_id = cls._resolve_doctor(db, doctor_identifier)

        review_coll = get_review_collection(db)
        query: Dict[str, Any] = {
            "$and": [
                {
                    "$or": [
                        {"doctorUserId": doc_user_id},
                        {"doctorProfileId": doc_profile_id},
                        {"doctorUserId": doctor_identifier},
                        {"doctorProfileId": doctor_identifier},
                    ]
                },
                {"status": ReviewStatus.PUBLISHED.value},
            ]
        }

        total = review_coll.count_documents(query)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        skip = (page - 1) * page_size

        cursor = review_coll.find(query).sort("createdAt", DESCENDING).skip(skip).limit(page_size)

        items: List[PublicReviewItem] = []
        for r in cursor:
            items.append(
                PublicReviewItem(
                    reviewId=r["reviewId"],
                    rating=int(r["rating"]),
                    reviewText=r.get("reviewText"),
                    patientDisplayName=r.get("patientDisplayName") or "Verified Patient",
                    verifiedAppointment=True,
                    createdAt=r["createdAt"],
                    updatedAt=r.get("updatedAt"),
                )
            )

        summary = await cls.get_doctor_rating_summary(db, doctor_identifier)

        return PublicReviewListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
            summary=summary,
        )

    @classmethod
    async def list_patient_reviews(
        cls,
        db: Database,
        patient_user: UserResponseSchema,
        page: int = 1,
        page_size: int = 20,
    ) -> PatientReviewListResponse:
        """List all reviews created by the authenticated patient."""
        review_coll = get_review_collection(db)
        query = {"patientUserId": str(patient_user.id)}

        total = review_coll.count_documents(query)
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        skip = (page - 1) * page_size

        cursor = review_coll.find(query).sort("createdAt", DESCENDING).skip(skip).limit(page_size)

        # Batch lookup doctor info
        reviews_raw = list(cursor)
        doc_user_ids = list({r["doctorUserId"] for r in reviews_raw if r.get("doctorUserId")})

        user_coll = get_user_collection(db)
        prof_coll = get_doctor_profile_collection(db)

        users_map = {}
        if doc_user_ids:
            doc_user_objs = [ObjectId(uid) for uid in doc_user_ids if ObjectId.is_valid(uid)]
            user_docs = user_coll.find({"_id": {"$in": doc_user_objs}})
            for u in user_docs:
                users_map[str(u["_id"])] = u.get("fullName", "Doctor")

        profiles_map = {}
        if doc_user_ids:
            prof_docs = prof_coll.find({"userId": {"$in": doc_user_ids}})
            for p in prof_docs:
                profiles_map[str(p["userId"])] = {
                    "specialty": p.get("specialty", "General"),
                    "hospital": p.get("hospitalOrClinic", ""),
                }

        items: List[PatientReviewItem] = []
        for r in reviews_raw:
            d_uid = r.get("doctorUserId", "")
            d_prof = profiles_map.get(d_uid, {})
            items.append(
                PatientReviewItem(
                    reviewId=r["reviewId"],
                    appointmentId=r["appointmentId"],
                    doctorUserId=d_uid,
                    doctorProfileId=r.get("doctorProfileId", ""),
                    doctorName=users_map.get(d_uid, "Doctor"),
                    doctorSpecialty=d_prof.get("specialty", "General"),
                    doctorHospital=d_prof.get("hospital", ""),
                    rating=int(r["rating"]),
                    reviewText=r.get("reviewText"),
                    status=ReviewStatus(r.get("status", ReviewStatus.PUBLISHED.value)),
                    createdAt=r["createdAt"],
                    updatedAt=r.get("updatedAt", r["createdAt"]),
                )
            )

        return PatientReviewListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )

    @classmethod
    async def update_review(
        cls,
        db: Database,
        review_id: str,
        patient_user: UserResponseSchema,
        req: UpdateReviewRequest,
    ) -> ReviewResponse:
        """Update an existing review's rating or text by its author."""
        review_coll = get_review_collection(db)
        query = {"$or": [{"reviewId": review_id}]}
        if ObjectId.is_valid(review_id):
            query["$or"].append({"_id": ObjectId(review_id)})

        review = review_coll.find_one(query)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )

        if str(review.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot edit another patient's review.",
            )

        update_fields: Dict[str, Any] = {"updatedAt": utc_now()}
        if req.rating is not None:
            update_fields["rating"] = req.rating
        if req.reviewText is not None:
            update_fields["reviewText"] = req.reviewText

        review_coll.update_one({"_id": review["_id"]}, {"$set": update_fields})
        updated = review_coll.find_one({"_id": review["_id"]})

        return ReviewResponse(
            id=str(updated["_id"]),
            reviewId=updated["reviewId"],
            doctorUserId=updated["doctorUserId"],
            doctorProfileId=updated["doctorProfileId"],
            patientUserId=updated["patientUserId"],
            patientDisplayName=updated.get("patientDisplayName", "Verified Patient"),
            appointmentId=updated["appointmentId"],
            rating=int(updated["rating"]),
            reviewText=updated.get("reviewText"),
            status=ReviewStatus(updated.get("status", ReviewStatus.PUBLISHED.value)),
            verifiedAppointment=True,
            createdAt=updated["createdAt"],
            updatedAt=updated["updatedAt"],
        )

    @classmethod
    async def delete_review(
        cls,
        db: Database,
        review_id: str,
        current_user: UserResponseSchema,
    ) -> Dict[str, Any]:
        """Delete a review by its author or by an administrator."""
        review_coll = get_review_collection(db)
        query = {"$or": [{"reviewId": review_id}]}
        if ObjectId.is_valid(review_id):
            query["$or"].append({"_id": ObjectId(review_id)})

        review = review_coll.find_one(query)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )

        is_author = str(review.get("patientUserId")) == str(current_user.id)
        is_admin = current_user.role == UserRole.ADMIN.value

        if not (is_author or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to delete this review.",
            )

        review_coll.delete_one({"_id": review["_id"]})
        return {"success": True, "message": "Review deleted successfully"}

    @classmethod
    async def report_review(
        cls,
        db: Database,
        review_id: str,
        current_user: UserResponseSchema,
        req: ReportReviewRequest,
    ) -> Dict[str, Any]:
        """Flag an inappropriate review for admin moderation."""
        review_coll = get_review_collection(db)
        query = {"$or": [{"reviewId": review_id}]}
        if ObjectId.is_valid(review_id):
            query["$or"].append({"_id": ObjectId(review_id)})

        review = review_coll.find_one(query)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )

        review_coll.update_one(
            {"_id": review["_id"]},
            {
                "$set": {
                    "status": ReviewStatus.REPORTED.value,
                    "reportReason": req.reason,
                    "reportedBy": str(current_user.id),
                    "reportedAt": utc_now(),
                    "updatedAt": utc_now(),
                }
            },
        )
        return {"success": True, "message": "Review reported for moderation"}

    @classmethod
    async def list_reported_reviews(
        cls,
        db: Database,
        admin_user: UserResponseSchema,
        page: int = 1,
        page_size: int = 20,
    ) -> List[AdminReportedReviewItem]:
        """List reported reviews awaiting admin action."""
        if admin_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin authorization required.",
            )

        review_coll = get_review_collection(db)
        query = {"status": ReviewStatus.REPORTED.value}
        skip = (page - 1) * page_size

        cursor = review_coll.find(query).sort("reportedAt", DESCENDING).skip(skip).limit(page_size)
        raw_list = list(cursor)

        user_coll = get_user_collection(db)
        doc_user_ids = [r["doctorUserId"] for r in raw_list if r.get("doctorUserId")]
        doc_user_objs = [ObjectId(uid) for uid in doc_user_ids if ObjectId.is_valid(uid)]
        users_map = {}
        if doc_user_objs:
            for u in user_coll.find({"_id": {"$in": doc_user_objs}}):
                users_map[str(u["_id"])] = u.get("fullName", "Doctor")

        items: List[AdminReportedReviewItem] = []
        for r in raw_list:
            items.append(
                AdminReportedReviewItem(
                    reviewId=r["reviewId"],
                    appointmentId=r["appointmentId"],
                    doctorUserId=r["doctorUserId"],
                    doctorName=users_map.get(r["doctorUserId"], "Doctor"),
                    patientUserId=r["patientUserId"],
                    patientDisplayName=r.get("patientDisplayName", "Patient"),
                    rating=int(r["rating"]),
                    reviewText=r.get("reviewText"),
                    status=ReviewStatus(r["status"]),
                    reportReason=r.get("reportReason"),
                    reportedBy=r.get("reportedBy"),
                    reportedAt=r.get("reportedAt"),
                    createdAt=r["createdAt"],
                )
            )
        return items

    @classmethod
    async def moderate_review(
        cls,
        db: Database,
        review_id: str,
        admin_user: UserResponseSchema,
        req: ModerateReviewRequest,
    ) -> Dict[str, Any]:
        """Admin action to hide or restore a reported review without altering rating value."""
        if admin_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin authorization required.",
            )

        review_coll = get_review_collection(db)
        query = {"$or": [{"reviewId": review_id}]}
        if ObjectId.is_valid(review_id):
            query["$or"].append({"_id": ObjectId(review_id)})

        review = review_coll.find_one(query)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )

        new_status = ReviewStatus.HIDDEN.value if req.action == "HIDE" else ReviewStatus.PUBLISHED.value

        review_coll.update_one(
            {"_id": review["_id"]},
            {
                "$set": {
                    "status": new_status,
                    "moderationNotes": req.moderationNotes,
                    "moderatedBy": str(admin_user.id),
                    "moderatedAt": utc_now(),
                    "updatedAt": utc_now(),
                }
            },
        )
        return {
            "success": True,
            "reviewId": review["reviewId"],
            "status": new_status,
            "message": f"Review has been {new_status.lower()}.",
        }
