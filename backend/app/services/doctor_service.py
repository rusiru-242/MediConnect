"""Doctor service handling profiles, discovery for patients, and availability management."""

from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.doctor_availability import (
    DoctorAvailabilityDocument,
    get_doctor_availability_collection,
    utc_now,
)
from app.models.doctor_profile import (
    DoctorVerificationStatus,
    get_doctor_profile_collection,
)
from app.models.user import AccountStatus, UserRole
from app.schemas.doctor import (
    CreateAvailabilityRequest,
    DayAvailabilitySlots,
    DoctorApplicationStatusResponse,
    DoctorAvailabilityResponse,
    DoctorDetailResponse,
    DoctorListItem,
    DoctorListResponse,
    DoctorSlotsResponse,
    TimeSlot,
    UpdateAvailabilityRequest,
)
from app.schemas.user import UserResponseSchema

# Sri Lanka Standard Time (Asia/Colombo = UTC+05:30)
SL_TIMEZONE = timezone(timedelta(hours=5, minutes=30))
ALLOWED_SLOT_DURATIONS = {15, 20, 30, 45, 60}


def get_sl_now() -> datetime:
    """Return current datetime in Sri Lanka local time (Asia/Colombo)."""
    return datetime.now(SL_TIMEZONE)


def get_sl_today_str() -> str:
    """Return today's date formatted as YYYY-MM-DD in Sri Lanka local time."""
    return get_sl_now().strftime("%Y-%m-%d")


def get_sl_current_time_str() -> str:
    """Return current time formatted as HH:MM in Sri Lanka local time."""
    return get_sl_now().strftime("%H:%M")


class DoctorService:
    """Business logic for Doctor application, public discovery, and availability management."""

    # -------------------------------------------------------------
    # DOCTOR APPLICATION STATUS
    # -------------------------------------------------------------
    @staticmethod
    def get_application_status(user_id: str, db: Database) -> DoctorApplicationStatusResponse:
        """Fetch application status for an authenticated doctor."""
        collection = get_doctor_profile_collection(db)

        profile = collection.find_one({"userId": str(user_id)})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found for this account.",
            )

        return DoctorApplicationStatusResponse(
            doctorId=str(profile.get("doctorId", "")),
            specialty=str(profile.get("specialty", "")),
            verificationStatus=str(profile.get("verificationStatus", "PENDING")),
            submittedAt=profile.get("submittedAt"),
            rejectionReason=profile.get("rejectionReason"),
        )

    # -------------------------------------------------------------
    # PATIENT DOCTOR DISCOVERY & SEARCH
    # -------------------------------------------------------------
    @staticmethod
    async def list_approved_doctors(
        db: Database,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        specialty: Optional[str] = None,
    ) -> DoctorListResponse:
        """List and search ONLY verified, approved, and active doctors for patients.

        Enforces backend security: PENDING and REJECTED doctors are strictly excluded.
        """
        # 1. Clamp pagination limits
        page = max(1, page)
        limit = max(1, min(100, limit))
        skip = (page - 1) * limit

        # 2. Build profile query: ONLY APPROVED doctors
        profile_query: Dict[str, Any] = {
            "verificationStatus": DoctorVerificationStatus.APPROVED.value,
        }

        if specialty and specialty.strip() and specialty.strip().lower() != "all":
            clean_spec = specialty.strip()
            profile_query["specialty"] = {"$regex": f"^{re.escape(clean_spec)}$", "$options": "i"}

        # 3. Query all approved profiles matching specialty filter
        profiles = list(db["doctor_profiles"].find(profile_query))
        if not profiles:
            return DoctorListResponse(items=[], page=page, limit=limit, total=0, totalPages=0)

        # 4. Map user IDs to fetch corresponding active users
        user_ids = []
        for p in profiles:
            uid = p.get("userId")
            if uid:
                user_ids.append(ObjectId(uid) if ObjectId.is_valid(uid) else uid)

        # User security check: MUST be DOCTOR role AND ACTIVE accountStatus
        users_cursor = db["users"].find({
            "_id": {"$in": user_ids},
            "role": UserRole.DOCTOR.value,
            "accountStatus": AccountStatus.ACTIVE.value,
        })
        active_users = {str(u["_id"]): u for u in users_cursor}

        # 5. Combine and filter profiles that have a valid active doctor user
        matching_doctors: List[DoctorListItem] = []
        clean_search = search.strip().lower() if search and search.strip() else None

        for p in profiles:
            uid_str = str(p.get("userId", ""))
            user = active_users.get(uid_str)
            if not user:
                # Exclude if user is not active or not DOCTOR role
                continue

            full_name = user.get("fullName", "")
            spec = p.get("specialty", "")
            hospital = p.get("hospitalOrClinic", "")

            # Apply search across full name, specialty, and hospital/clinic
            if clean_search:
                if (
                    clean_search not in full_name.lower()
                    and clean_search not in spec.lower()
                    and clean_search not in hospital.lower()
                ):
                    continue

            matching_doctors.append(
                DoctorListItem(
                    doctorId=str(p.get("doctorId", "")),
                    fullName=full_name,
                    specialty=spec,
                    hospitalOrClinic=hospital,
                    experienceYears=int(p.get("experienceYears", 0)),
                    bio=p.get("bio"),
                    profileImage=user.get("profileImage"),
                    verificationStatus=DoctorVerificationStatus.APPROVED.value,
                )
            )

        total = len(matching_doctors)
        total_pages = math.ceil(total / limit) if total > 0 else 0
        paginated_items = matching_doctors[skip : skip + limit]

        return DoctorListResponse(
            items=paginated_items,
            page=page,
            limit=limit,
            total=total,
            totalPages=total_pages,
        )

    @staticmethod
    async def get_approved_doctor_detail(db: Database, doctor_id: str) -> DoctorDetailResponse:
        """Fetch public profile details for an APPROVED + ACTIVE doctor.

        Returns 404 if the doctor is not found, pending, rejected, or inactive.
        """
        clean_id = doctor_id.strip()

        # Query profile by doctorId or _id
        query = {}
        if ObjectId.is_valid(clean_id):
            query = {"$or": [{"doctorId": clean_id}, {"_id": ObjectId(clean_id)}]}
        else:
            query = {"doctorId": clean_id}

        profile = db["doctor_profiles"].find_one(query)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found.",
            )

        # Core Security Rule: MUST be APPROVED
        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found.",
            )

        # Validate associated user account is ACTIVE and DOCTOR role
        user_id_val = profile.get("userId")
        user_query = {}
        if ObjectId.is_valid(user_id_val):
            user_query = {"$or": [{"_id": ObjectId(user_id_val)}, {"_id": user_id_val}]}
        else:
            user_query = {"_id": user_id_val}

        user = db["users"].find_one(user_query)
        if (
            not user
            or user.get("role") != UserRole.DOCTOR.value
            or user.get("accountStatus") != AccountStatus.ACTIVE.value
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found.",
            )

        return DoctorDetailResponse(
            doctorId=str(profile.get("doctorId", "")),
            fullName=user.get("fullName", ""),
            specialty=profile.get("specialty", ""),
            qualifications=profile.get("qualifications", ""),
            hospitalOrClinic=profile.get("hospitalOrClinic", ""),
            experienceYears=int(profile.get("experienceYears", 0)),
            bio=profile.get("bio"),
            profileImage=user.get("profileImage"),
            verificationStatus=DoctorVerificationStatus.APPROVED.value,
        )

    # -------------------------------------------------------------
    # DOCTOR AVAILABILITY MANAGEMENT
    # -------------------------------------------------------------
    @staticmethod
    def _validate_time_format(time_str: str) -> tuple[int, int]:
        """Validate HH:MM format and return (hours, minutes)."""
        parts = time_str.split(":")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Time must be in HH:MM format.")
        try:
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError()
            return h, m
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time values in HH:MM.")

    @staticmethod
    def _validate_date_string(date_str: str) -> None:
        """Validate YYYY-MM-DD date and ensure it is not in the past (Sri Lanka local time)."""
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Date must be a valid date in YYYY-MM-DD format.")

        sl_today = get_sl_now().date()
        if target_date < sl_today:
            raise HTTPException(status_code=400, detail="Cannot schedule availability for a past date.")

    @staticmethod
    def _check_time_overlap(
        start_a: str,
        end_a: str,
        start_b: str,
        end_b: str,
    ) -> bool:
        """Check if two time intervals [start, end) overlap."""
        return max(start_a, start_b) < min(end_a, end_b)

    @staticmethod
    async def create_availability(
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreateAvailabilityRequest,
    ) -> DoctorAvailabilityResponse:
        """Create a new availability schedule for an approved active doctor."""
        # 1. Authorization & Status Check
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can manage availability.")

        profile = db["doctor_profiles"].find_one({"userId": str(doctor_user.id)})
        if not profile or profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only approved doctors with active accounts can create availability.",
            )

        if doctor_user.accountStatus != AccountStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your doctor account is pending administrative verification.",
            )

        # 2. Date and Time Validation
        DoctorService._validate_date_string(req.date)
        start_h, start_m = DoctorService._validate_time_format(req.startTime)
        end_h, end_m = DoctorService._validate_time_format(req.endTime)

        start_total_mins = start_h * 60 + start_m
        end_total_mins = end_h * 60 + end_m

        if start_total_mins >= end_total_mins:
            raise HTTPException(status_code=400, detail="startTime must be earlier than endTime.")

        if req.slotDurationMinutes not in ALLOWED_SLOT_DURATIONS:
            raise HTTPException(
                status_code=400,
                detail=f"slotDurationMinutes must be one of {sorted(ALLOWED_SLOT_DURATIONS)}.",
            )

        window_duration = end_total_mins - start_total_mins
        if window_duration < req.slotDurationMinutes:
            raise HTTPException(
                status_code=400,
                detail=f"Availability window ({window_duration} min) must be at least one slot duration ({req.slotDurationMinutes} min).",
            )

        # 3. If date is today in Sri Lanka, endTime must not be in the past
        sl_today = get_sl_today_str()
        if req.date == sl_today:
            sl_current_time = get_sl_current_time_str()
            if req.endTime <= sl_current_time:
                raise HTTPException(status_code=400, detail="Cannot schedule availability window that has already passed today.")

        # 4. Check for overlapping active availability for this doctor on the same date
        existing_availabilities = list(
            db["doctor_availabilities"].find({
                "doctorUserId": str(doctor_user.id),
                "date": req.date,
                "isActive": True,
            })
        )

        for exist in existing_availabilities:
            if DoctorService._check_time_overlap(
                req.startTime, req.endTime, exist["startTime"], exist["endTime"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Availability overlaps with existing schedule ({exist['startTime']} - {exist['endTime']}) on {req.date}.",
                )

        now = utc_now()
        avail_doc = DoctorAvailabilityDocument(
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            date=req.date,
            startTime=req.startTime,
            endTime=req.endTime,
            slotDurationMinutes=req.slotDurationMinutes,
            isActive=True,
            createdAt=now,
            updatedAt=now,
        )

        collection = get_doctor_availability_collection(db)
        res = collection.insert_one(avail_doc.to_mongo_dict())

        return DoctorAvailabilityResponse(
            id=str(res.inserted_id),
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            date=req.date,
            startTime=req.startTime,
            endTime=req.endTime,
            slotDurationMinutes=req.slotDurationMinutes,
            isActive=True,
            createdAt=now,
            updatedAt=now,
        )

    @staticmethod
    async def get_doctor_availabilities(
        db: Database,
        doctor_user: UserResponseSchema,
    ) -> List[DoctorAvailabilityResponse]:
        """Fetch all upcoming and active availability records for the authenticated doctor."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can view availability.")

        collection = get_doctor_availability_collection(db)
        cursor = collection.find({
            "doctorUserId": str(doctor_user.id),
        }).sort([("date", 1), ("startTime", 1)])

        results = []
        for doc in cursor:
            results.append(
                DoctorAvailabilityResponse(
                    id=str(doc["_id"]),
                    doctorUserId=str(doc["doctorUserId"]),
                    doctorProfileId=str(doc["doctorProfileId"]),
                    date=doc["date"],
                    startTime=doc["startTime"],
                    endTime=doc["endTime"],
                    slotDurationMinutes=doc.get("slotDurationMinutes", 30),
                    isActive=doc.get("isActive", True),
                    createdAt=doc.get("createdAt", utc_now()),
                    updatedAt=doc.get("updatedAt", utc_now()),
                )
            )
        return results

    @staticmethod
    async def update_availability(
        db: Database,
        doctor_user: UserResponseSchema,
        availability_id: str,
        req: UpdateAvailabilityRequest,
    ) -> DoctorAvailabilityResponse:
        """Update an availability window, ensuring ownership and overlap safety."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can update availability.")

        if not ObjectId.is_valid(availability_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid availability ID format.")

        collection = get_doctor_availability_collection(db)
        existing = collection.find_one({"_id": ObjectId(availability_id)})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability record not found.")

        # Strict Ownership Check: Must belong to authenticated doctor
        if str(existing["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this availability record.",
            )

        new_date = req.date if req.date is not None else existing["date"]
        new_start = req.startTime if req.startTime is not None else existing["startTime"]
        new_end = req.endTime if req.endTime is not None else existing["endTime"]
        new_duration = req.slotDurationMinutes if req.slotDurationMinutes is not None else existing.get("slotDurationMinutes", 30)
        new_active = req.isActive if req.isActive is not None else existing.get("isActive", True)

        DoctorService._validate_date_string(new_date)
        start_h, start_m = DoctorService._validate_time_format(new_start)
        end_h, end_m = DoctorService._validate_time_format(new_end)

        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m
        if start_total >= end_total:
            raise HTTPException(status_code=400, detail="startTime must be earlier than endTime.")

        if new_duration not in ALLOWED_SLOT_DURATIONS:
            raise HTTPException(status_code=400, detail=f"slotDurationMinutes must be one of {sorted(ALLOWED_SLOT_DURATIONS)}.")

        # Overlap check against other active schedules on that date
        if new_active:
            other_schedules = list(
                collection.find({
                    "doctorUserId": str(doctor_user.id),
                    "date": new_date,
                    "isActive": True,
                    "_id": {"$ne": ObjectId(availability_id)},
                })
            )
            for other in other_schedules:
                if DoctorService._check_time_overlap(new_start, new_end, other["startTime"], other["endTime"]):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Updated availability overlaps with existing schedule ({other['startTime']} - {other['endTime']}) on {new_date}.",
                    )

        now = utc_now()
        collection.update_one(
            {"_id": ObjectId(availability_id)},
            {
                "$set": {
                    "date": new_date,
                    "startTime": new_start,
                    "endTime": new_end,
                    "slotDurationMinutes": new_duration,
                    "isActive": new_active,
                    "updatedAt": now,
                }
            },
        )

        return DoctorAvailabilityResponse(
            id=availability_id,
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(existing["doctorProfileId"]),
            date=new_date,
            startTime=new_start,
            endTime=new_end,
            slotDurationMinutes=new_duration,
            isActive=new_active,
            createdAt=existing.get("createdAt", now),
            updatedAt=now,
        )

    @staticmethod
    async def delete_availability(
        db: Database,
        doctor_user: UserResponseSchema,
        availability_id: str,
    ) -> Dict[str, str]:
        """Soft-disable or remove doctor availability, enforcing ownership."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can remove availability.")

        if not ObjectId.is_valid(availability_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid availability ID format.")

        collection = get_doctor_availability_collection(db)
        existing = collection.find_one({"_id": ObjectId(availability_id)})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability record not found.")

        # Strict Ownership Check
        if str(existing["doctorUserId"]) != str(doctor_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this availability record.",
            )

        # Soft disable using isActive = False to maintain compatibility with future appointment records
        collection.update_one(
            {"_id": ObjectId(availability_id)},
            {"$set": {"isActive": False, "updatedAt": utc_now()}},
        )

        return {"message": "Doctor availability removed successfully."}

    # -------------------------------------------------------------
    # GENERATE PATIENT-VISIBLE SLOTS
    # -------------------------------------------------------------
    @staticmethod
    def _generate_slots_for_window(
        date_str: str,
        start_time_str: str,
        end_time_str: str,
        slot_duration_mins: int,
    ) -> List[TimeSlot]:
        """Generate discrete TimeSlots between start_time and end_time, filtering out past slots."""
        start_h, start_m = int(start_time_str[:2]), int(start_time_str[3:5])
        end_h, end_m = int(end_time_str[:2]), int(end_time_str[3:5])

        current_mins = start_h * 60 + start_m
        end_mins = end_h * 60 + end_m

        is_today = (date_str == get_sl_today_str())
        sl_now_mins = None
        if is_today:
            sl_now_h, sl_now_m = int(get_sl_current_time_str()[:2]), int(get_sl_current_time_str()[3:5])
            sl_now_mins = sl_now_h * 60 + sl_now_m

        slots: List[TimeSlot] = []
        while current_mins + slot_duration_mins <= end_mins:
            slot_start_h = current_mins // 60
            slot_start_m = current_mins % 60
            next_mins = current_mins + slot_duration_mins
            slot_end_h = next_mins // 60
            slot_end_m = next_mins % 60

            slot_start_str = f"{slot_start_h:02d}:{slot_start_m:02d}"
            slot_end_str = f"{slot_end_h:02d}:{slot_end_m:02d}"

            # Filter out past slots if date is today
            if not is_today or (sl_now_mins is not None and current_mins > sl_now_mins):
                slots.append(TimeSlot(startTime=slot_start_str, endTime=slot_end_str))

            current_mins += slot_duration_mins

        return slots

    @staticmethod
    async def get_doctor_patient_slots(
        db: Database,
        doctor_id: str,
        date_filter: Optional[str] = None,
    ) -> Any:
        """Generate and return available time slots for an APPROVED doctor."""
        clean_id = doctor_id.strip()

        # 1. Verify doctor is APPROVED + ACTIVE
        query = {}
        if ObjectId.is_valid(clean_id):
            query = {"$or": [{"doctorId": clean_id}, {"_id": ObjectId(clean_id)}]}
        else:
            query = {"doctorId": clean_id}

        profile = db["doctor_profiles"].find_one(query)
        if not profile or profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found or not currently active.")

        user_id_val = profile.get("userId")
        user_query = {"$or": [{"_id": ObjectId(user_id_val)}, {"_id": user_id_val}]} if ObjectId.is_valid(user_id_val) else {"_id": user_id_val}
        user = db["users"].find_one(user_query)
        if not user or user.get("role") != UserRole.DOCTOR.value or user.get("accountStatus") != AccountStatus.ACTIVE.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found or not currently active.")

        # 2. Query active availabilities
        sl_today = get_sl_today_str()
        avail_query: Dict[str, Any] = {
            "doctorProfileId": str(profile["_id"]),
            "isActive": True,
        }

        if date_filter and date_filter.strip():
            clean_date = date_filter.strip()
            DoctorService._validate_date_string(clean_date)
            avail_query["date"] = clean_date
        else:
            avail_query["date"] = {"$gte": sl_today}

        collection = get_doctor_availability_collection(db)
        avail_records = list(collection.find(avail_query).sort([("date", 1), ("startTime", 1)]))

        # 3. Group and generate slots by date
        grouped_slots: Dict[str, List[TimeSlot]] = {}
        for rec in avail_records:
            date_key = rec["date"]
            start_t = rec["startTime"]
            end_t = rec["endTime"]
            duration = int(rec.get("slotDurationMinutes", 30))

            generated = DoctorService._generate_slots_for_window(date_key, start_t, end_t, duration)
            if generated:
                if date_key not in grouped_slots:
                    grouped_slots[date_key] = []
                grouped_slots[date_key].extend(generated)

        day_availabilities = [
            DayAvailabilitySlots(date=d, slots=slots)
            for d, slots in sorted(grouped_slots.items(), key=lambda x: x[0])
        ]

        if date_filter and date_filter.strip():
            clean_date = date_filter.strip()
            return DayAvailabilitySlots(date=clean_date, slots=grouped_slots.get(clean_date, []))

        if len(day_availabilities) == 1:
            return day_availabilities[0]

        return day_availabilities
