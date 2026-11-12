"""Doctor service handling profiles, discovery for patients, and availability management."""

import calendar
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, available_timezones
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from app.models.appointment import AppointmentStatus
from app.models.doctor_availability import (
    DoctorAvailabilityDocument,
    get_doctor_availability_collection,
    utc_now,
)
from app.models.doctor_weekly_schedule import (
    DoctorWeeklyScheduleDocument,
    WeekdaySchedule,
    WorkingSession,
    get_doctor_weekly_schedule_collection,
)
from app.models.doctor_leave import (
    DoctorLeaveDocument,
    LeaveStatus,
    LeaveType,
    get_doctor_leave_collection,
)
from app.models.doctor_blocked_time import (
    DoctorBlockedTimeDocument,
    get_doctor_blocked_time_collection,
)
from app.models.doctor_profile import (
    DoctorVerificationStatus,
    get_doctor_profile_collection,
)
from app.models.user import AccountStatus, UserRole
from app.schemas.doctor import (
    CalendarDayAppointment,
    CalendarDayOverview,
    ConflictingAppointmentSummary,
    CreateAvailabilityRequest,
    CreateBlockedTimeRequest,
    CreateLeaveRequest,
    DayAvailabilitySlots,
    DoctorApplicationStatusResponse,
    DoctorAvailabilityResponse,
    DoctorBlockedTimeResponse,
    DoctorCalendarOverviewResponse,
    DoctorDetailResponse,
    DoctorLeaveResponse,
    DoctorListItem,
    DoctorListResponse,
    DoctorSlotsResponse,
    DoctorWeeklyScheduleResponse,
    LeaveConflictResponse,
    TimeSlot,
    UpdateAvailabilityRequest,
    UpdateWeeklyScheduleRequest,
    WeekdayScheduleSchema,
    WorkingSessionSchema,
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

        # 3. Query all approved profiles matching specialty filter (newest first)
        profiles = list(db["doctor_profiles"].find(profile_query).sort([("_id", -1)]))
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
                    consultationFee=float(p.get("consultationFee", 2500.0)),
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
            consultationFee=float(profile.get("consultationFee", 2500.0)),
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
    # Phase 54: WEEKLY SCHEDULE, LEAVE & BLOCKED TIME MANAGEMENT
    # -------------------------------------------------------------
    @staticmethod
    def _default_weekdays_config() -> List[Dict[str, Any]]:
        return [
            {"day": "monday", "isEnabled": True, "sessions": [{"startTime": "09:00", "endTime": "12:00"}, {"startTime": "14:00", "endTime": "17:00"}]},
            {"day": "tuesday", "isEnabled": True, "sessions": [{"startTime": "09:00", "endTime": "13:00"}]},
            {"day": "wednesday", "isEnabled": False, "sessions": []},
            {"day": "thursday", "isEnabled": True, "sessions": [{"startTime": "09:00", "endTime": "17:00"}]},
            {"day": "friday", "isEnabled": True, "sessions": [{"startTime": "09:00", "endTime": "12:00"}]},
            {"day": "saturday", "isEnabled": False, "sessions": []},
            {"day": "sunday", "isEnabled": False, "sessions": []},
        ]

    @classmethod
    def _get_doctor_profile_or_404(cls, db: Database, user_id: str) -> Dict[str, Any]:
        """Retrieve approved doctor profile by user ID or raise 404/403."""
        profile = db["doctor_profiles"].find_one({"userId": str(user_id)})
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found.",
            )
        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only approved doctors can manage availability.",
            )
        return profile

    @classmethod
    async def get_doctor_weekly_schedule(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
    ) -> DoctorWeeklyScheduleResponse:
        """Fetch weekly recurring schedule for the authenticated doctor."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can access weekly schedule.")

        profile = cls._get_doctor_profile_or_404(db, str(doctor_user.id))
        coll = get_doctor_weekly_schedule_collection(db)
        existing = coll.find_one({"doctorUserId": str(doctor_user.id)})

        if existing:
            return DoctorWeeklyScheduleResponse(
                id=str(existing["_id"]),
                doctorUserId=str(existing["doctorUserId"]),
                doctorProfileId=str(existing["doctorProfileId"]),
                timezone=existing.get("timezone", "Asia/Colombo"),
                slotDurationMinutes=int(existing.get("slotDurationMinutes", 30)),
                weekdays=[
                    WeekdayScheduleSchema(
                        day=w["day"],
                        isEnabled=w.get("isEnabled", True),
                        sessions=[
                            WorkingSessionSchema(startTime=s["startTime"], endTime=s["endTime"])
                            for s in w.get("sessions", [])
                        ],
                    )
                    for w in existing.get("weekdays", [])
                ],
                createdAt=existing.get("createdAt"),
                updatedAt=existing.get("updatedAt"),
            )

        # Return default schedule if not yet saved in DB
        return DoctorWeeklyScheduleResponse(
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            timezone="Asia/Colombo",
            slotDurationMinutes=30,
            weekdays=[
                WeekdayScheduleSchema(
                    day=w["day"],
                    isEnabled=w["isEnabled"],
                    sessions=[
                        WorkingSessionSchema(startTime=s["startTime"], endTime=s["endTime"])
                        for s in w["sessions"]
                    ],
                )
                for w in cls._default_weekdays_config()
            ],
        )

    @classmethod
    async def update_doctor_weekly_schedule(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: UpdateWeeklyScheduleRequest,
    ) -> DoctorWeeklyScheduleResponse:
        """Configure or update weekly recurring working hours for the doctor."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can modify weekly schedule.")

        profile = cls._get_doctor_profile_or_404(db, str(doctor_user.id))
        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only approved doctors can update availability.")

        # Timezone validation
        tz_str = req.timezone or "Asia/Colombo"
        if tz_str not in available_timezones():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid IANA timezone: {tz_str}")

        # Slot duration validation
        slot_dur = req.slotDurationMinutes or 30
        if slot_dur not in ALLOWED_SLOT_DURATIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slot duration must be one of {sorted(ALLOWED_SLOT_DURATIONS)} minutes.",
            )

        # Validate weekdays and sessions
        valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        provided_days = {w.day.lower() for w in req.weekdays}
        if not provided_days.issubset(valid_days):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid weekday name provided.")

        normalized_weekdays = []
        for w in req.weekdays:
            day_name = w.day.lower()
            if not w.isEnabled or not w.sessions:
                normalized_weekdays.append(WeekdayScheduleSchema(day=day_name, isEnabled=w.isEnabled, sessions=[]))
                continue

            # Validate each session
            parsed_sessions = []
            for s in w.sessions:
                cls._validate_time_format(s.startTime)
                cls._validate_time_format(s.endTime)
                sh, sm = int(s.startTime[:2]), int(s.startTime[3:5])
                eh, em = int(s.endTime[:2]), int(s.endTime[3:5])
                start_mins = sh * 60 + sm
                end_mins = eh * 60 + em
                if start_mins >= end_mins:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Session start time ({s.startTime}) must be strictly earlier than end time ({s.endTime}) on {day_name}.",
                    )
                if (end_mins - start_mins) < slot_dur:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Session duration on {day_name} ({end_mins - start_mins} min) must be at least slot duration ({slot_dur} min).",
                    )
                parsed_sessions.append((start_mins, end_mins, s.startTime, s.endTime))

            # Sort sessions by start time and verify non-overlapping
            parsed_sessions.sort(key=lambda x: x[0])
            for i in range(len(parsed_sessions) - 1):
                if parsed_sessions[i][1] > parsed_sessions[i + 1][0]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Overlapping working sessions on {day_name}: {parsed_sessions[i][2]}-{parsed_sessions[i][3]} and {parsed_sessions[i+1][2]}-{parsed_sessions[i+1][3]}.",
                    )

            normalized_weekdays.append(
                WeekdayScheduleSchema(
                    day=day_name,
                    isEnabled=True,
                    sessions=[WorkingSessionSchema(startTime=ps[2], endTime=ps[3]) for ps in parsed_sessions],
                )
            )

        coll = get_doctor_weekly_schedule_collection(db)
        now = utc_now()
        payload = {
            "doctorProfileId": str(profile["_id"]),
            "timezone": tz_str,
            "slotDurationMinutes": slot_dur,
            "weekdays": [w.model_dump() for w in normalized_weekdays],
            "updatedAt": now,
        }
        res = coll.find_one_and_update(
            {"doctorUserId": str(doctor_user.id)},
            {"$set": payload, "$setOnInsert": {"createdAt": now, "doctorUserId": str(doctor_user.id)}},
            upsert=True,
            return_document=True,
        )

        return DoctorWeeklyScheduleResponse(
            id=str(res["_id"]),
            doctorUserId=str(res["doctorUserId"]),
            doctorProfileId=str(res["doctorProfileId"]),
            timezone=res.get("timezone", "Asia/Colombo"),
            slotDurationMinutes=int(res.get("slotDurationMinutes", 30)),
            weekdays=normalized_weekdays,
            createdAt=res.get("createdAt"),
            updatedAt=res.get("updatedAt"),
        )

    @classmethod
    async def create_doctor_leave(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreateLeaveRequest,
    ) -> Any:
        """Create a full-day, multi-day, or partial-day leave entry with conflict resolution."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can manage leave.")

        profile = cls._get_doctor_profile_or_404(db, str(doctor_user.id))
        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only approved doctors can apply for leave.")

        # Date validations
        cls._validate_date_string(req.startDate)
        cls._validate_date_string(req.endDate)
        if req.startDate > req.endDate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave start date cannot be after end date.")

        # Partial day validation
        is_partial = bool(req.startTime or req.endTime)
        if is_partial:
            if not (req.startTime and req.endTime):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Partial-day leave requires both start time and end time.")
            if req.startDate != req.endDate:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Partial-day leave must start and end on the same date.")
            cls._validate_time_format(req.startTime)
            cls._validate_time_format(req.endTime)
            sh, sm = int(req.startTime[:2]), int(req.startTime[3:5])
            eh, em = int(req.endTime[:2]), int(req.endTime[3:5])
            if (sh * 60 + sm) >= (eh * 60 + em):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave start time must be earlier than end time.")

        # Overlapping leave check (avoid duplicate overlapping active records)
        leave_coll = get_doctor_leave_collection(db)
        overlap_query = {
            "doctorUserId": str(doctor_user.id),
            "status": LeaveStatus.ACTIVE.value,
            "startDate": {"$lte": req.endDate},
            "endDate": {"$gte": req.startDate},
        }
        for existing_l in leave_coll.find(overlap_query):
            ex_start_t = existing_l.get("startTime")
            ex_end_t = existing_l.get("endTime")
            # If either is full day, it overlaps
            if not is_partial or not (ex_start_t and ex_end_t):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave overlaps with an existing leave schedule.")
            # Both are partial day on same date
            if req.startTime < ex_end_t and req.endTime > ex_start_t:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Partial leave overlaps with an existing partial leave.")

        # Check existing appointment conflicts
        doctor_profile_id = str(profile["_id"])
        doctor_id_num = profile.get("doctorId")
        appt_query = {
            "$or": [
                {"doctorUserId": str(doctor_user.id)},
                {"doctorProfileId": doctor_profile_id},
                {"doctorId": doctor_id_num},
            ],
            "status": {"$in": ["HOLD", "PENDING", "CONFIRMED"]},
            "appointmentDate": {"$gte": req.startDate, "$lte": req.endDate},
        }
        now = utc_now()
        candidate_appts = list(db["appointments"].find(appt_query))
        conflicts = []
        for a in candidate_appts:
            hold = a.get("holdExpiresAt")
            paid = a.get("paymentStatus") == "PAID"
            st = a.get("status")
            if st in ["HOLD", "PENDING"] and not paid and hold:
                if hold.tzinfo is None:
                    hold = hold.replace(tzinfo=timezone.utc)
                if hold <= now:
                    continue  # Expired hold is not a conflict

            # If partial day, verify time overlap
            if is_partial:
                a_start = a.get("startTime", "00:00")
                a_end = a.get("endTime", "23:59")
                if not (a_start < req.endTime and a_end > req.startTime):
                    continue

            # Fetch patient name for summary
            p_user = db["users"].find_one({"_id": ObjectId(a["patientUserId"])}) if ObjectId.is_valid(str(a.get("patientUserId"))) else None
            p_name = (p_user.get("fullName") if p_user else None) or "Patient"

            conflicts.append(
                ConflictingAppointmentSummary(
                    appointmentId=str(a["_id"]),
                    patientName=p_name,
                    appointmentDate=a.get("appointmentDate", ""),
                    startTime=a.get("startTime", ""),
                    endTime=a.get("endTime", ""),
                    status=a.get("status", ""),
                )
            )

        # Conflict resolution policy
        if conflicts and not req.resolveConflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Leave conflicts with {len(conflicts)} active appointment(s). Explicit resolution required.",
            )

        # If conflicts exist and resolveConflicts is True: explicitly cancel and notify
        if conflicts and req.resolveConflicts:
            from app.models.notification import NotificationType
            from app.services.notification_service import NotificationService

            dr_name = doctor_user.fullName or "Doctor"
            if not dr_name.startswith("Dr.") and not dr_name.startswith("Dr "):
                dr_name = f"Dr. {dr_name}"

            for c in conflicts:
                db["appointments"].update_one(
                    {"_id": ObjectId(c.appointmentId)},
                    {
                        "$set": {
                            "status": AppointmentStatus.CANCELLED.value,
                            "cancelledBy": "DOCTOR",
                            "cancellationReason": f"Doctor on Leave: {req.reason or 'Scheduled leave'}",
                            "updatedAt": now,
                        }
                    },
                )
                # Fetch appt doc to get patientUserId
                appt_doc = db["appointments"].find_one({"_id": ObjectId(c.appointmentId)})
                if appt_doc and appt_doc.get("patientUserId"):
                    try:
                        NotificationService.create_notification(
                            db=db,
                            recipient_user_id=str(appt_doc["patientUserId"]),
                            type=NotificationType.APPOINTMENT_CANCELLED,
                            title="Appointment Cancelled Due to Doctor Leave",
                            body=f"Your appointment with {dr_name} on {c.appointmentDate} at {c.startTime} has been cancelled because the doctor is on leave.",
                            related_appointment_id=c.appointmentId,
                            idempotency_key=f"leave_cancel_{c.appointmentId}",
                        )
                    except Exception as notif_err:
                        pass

        # Save leave
        leave_doc = DoctorLeaveDocument(
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            leaveType=req.leaveType,
            startDate=req.startDate,
            endDate=req.endDate,
            startTime=req.startTime,
            endTime=req.endTime,
            reason=req.reason,
            status=LeaveStatus.ACTIVE,
            createdAt=now,
            updatedAt=now,
        )
        res = leave_coll.insert_one(leave_doc.to_mongo_dict())
        return DoctorLeaveResponse(
            id=str(res.inserted_id),
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            leaveType=req.leaveType,
            startDate=req.startDate,
            endDate=req.endDate,
            startTime=req.startTime,
            endTime=req.endTime,
            reason=req.reason,
            status=LeaveStatus.ACTIVE.value,
            createdAt=now,
            updatedAt=now,
        )

    @classmethod
    async def list_doctor_leaves(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        status_filter: Optional[str] = None,
    ) -> List[DoctorLeaveResponse]:
        """List leave records for the authenticated doctor."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can view leave records.")

        leave_coll = get_doctor_leave_collection(db)
        q: Dict[str, Any] = {"doctorUserId": str(doctor_user.id)}
        if status_filter:
            q["status"] = status_filter.upper()

        records = list(leave_coll.find(q).sort([("startDate", -1)]))
        return [
            DoctorLeaveResponse(
                id=str(r["_id"]),
                doctorUserId=str(r["doctorUserId"]),
                doctorProfileId=str(r["doctorProfileId"]),
                leaveType=r.get("leaveType", "PERSONAL"),
                startDate=r["startDate"],
                endDate=r["endDate"],
                startTime=r.get("startTime"),
                endTime=r.get("endTime"),
                reason=r.get("reason"),
                status=r.get("status", "ACTIVE"),
                createdAt=r.get("createdAt", utc_now()),
                updatedAt=r.get("updatedAt", utc_now()),
            )
            for r in records
        ]

    @classmethod
    async def cancel_doctor_leave(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        leave_id: str,
    ) -> Dict[str, str]:
        """Cancel an existing leave record."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can cancel leave.")

        if not ObjectId.is_valid(leave_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid leave ID format.")

        leave_coll = get_doctor_leave_collection(db)
        existing = leave_coll.find_one({"_id": ObjectId(leave_id)})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave record not found.")

        if str(existing.get("doctorUserId")) != str(doctor_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this leave record.")

        leave_coll.update_one(
            {"_id": ObjectId(leave_id)},
            {"$set": {"status": LeaveStatus.CANCELLED.value, "updatedAt": utc_now()}},
        )
        return {"message": "Leave cancelled successfully."}

    @classmethod
    async def create_doctor_blocked_time(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        req: CreateBlockedTimeRequest,
    ) -> DoctorBlockedTimeResponse:
        """Create a blocked time interval for the authenticated doctor."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can block time.")

        profile = cls._get_doctor_profile_or_404(db, str(doctor_user.id))
        if profile.get("verificationStatus") != DoctorVerificationStatus.APPROVED.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only approved doctors can block time.")

        cls._validate_date_string(req.date)
        cls._validate_time_format(req.startTime)
        cls._validate_time_format(req.endTime)
        sh, sm = int(req.startTime[:2]), int(req.startTime[3:5])
        eh, em = int(req.endTime[:2]), int(req.endTime[3:5])
        if (sh * 60 + sm) >= (eh * 60 + em):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be earlier than end time.")

        coll = get_doctor_blocked_time_collection(db)
        now = utc_now()
        doc = DoctorBlockedTimeDocument(
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            date=req.date,
            startTime=req.startTime,
            endTime=req.endTime,
            reason=req.reason,
            createdAt=now,
        )
        res = coll.insert_one(doc.to_mongo_dict())
        return DoctorBlockedTimeResponse(
            id=str(res.inserted_id),
            doctorUserId=str(doctor_user.id),
            doctorProfileId=str(profile["_id"]),
            date=req.date,
            startTime=req.startTime,
            endTime=req.endTime,
            reason=req.reason,
            createdAt=now,
        )

    @classmethod
    async def list_doctor_blocked_times(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        date_filter: Optional[str] = None,
    ) -> List[DoctorBlockedTimeResponse]:
        """List blocked time intervals for the doctor."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can view blocked times.")

        coll = get_doctor_blocked_time_collection(db)
        q: Dict[str, Any] = {"doctorUserId": str(doctor_user.id)}
        if date_filter:
            q["date"] = date_filter
        records = list(coll.find(q).sort([("date", 1), ("startTime", 1)]))
        return [
            DoctorBlockedTimeResponse(
                id=str(r["_id"]),
                doctorUserId=str(r["doctorUserId"]),
                doctorProfileId=str(r["doctorProfileId"]),
                date=r["date"],
                startTime=r["startTime"],
                endTime=r["endTime"],
                reason=r.get("reason"),
                createdAt=r.get("createdAt", utc_now()),
            )
            for r in records
        ]

    @classmethod
    async def delete_doctor_blocked_time(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        block_id: str,
    ) -> Dict[str, str]:
        """Remove a blocked time interval."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can delete blocked time.")

        if not ObjectId.is_valid(block_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid block ID format.")

        coll = get_doctor_blocked_time_collection(db)
        existing = coll.find_one({"_id": ObjectId(block_id)})
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blocked time record not found.")

        if str(existing.get("doctorUserId")) != str(doctor_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this blocked time record.")

        coll.delete_one({"_id": ObjectId(block_id)})
        return {"message": "Blocked time removed successfully."}

    @classmethod
    async def get_doctor_calendar_overview(
        cls,
        db: Database,
        doctor_user: UserResponseSchema,
        month_str: Optional[str] = None,
    ) -> DoctorCalendarOverviewResponse:
        """Provide detailed monthly calendar overview with day-by-day status, leaves, blocks, and appointments."""
        if doctor_user.role != UserRole.DOCTOR.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can access calendar overview.")

        profile = cls._get_doctor_profile_or_404(db, str(doctor_user.id))
        target_month = month_str.strip() if month_str and month_str.strip() else get_sl_now().strftime("%Y-%m")
        if not re.match(r"^\d{4}-\d{2}$", target_month):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Month must be in YYYY-MM format.")

        year, month_num = int(target_month[:4]), int(target_month[5:7])
        num_days = calendar.monthrange(year, month_num)[1]
        start_date = f"{target_month}-01"
        end_date = f"{target_month}-{num_days:02d}"

        # Fetch active leaves in this month
        leave_coll = get_doctor_leave_collection(db)
        leaves = list(leave_coll.find({
            "doctorUserId": str(doctor_user.id),
            "status": LeaveStatus.ACTIVE.value,
            "startDate": {"$lte": end_date},
            "endDate": {"$gte": start_date},
        }))

        # Fetch blocked times in this month
        block_coll = get_doctor_blocked_time_collection(db)
        blocks = list(block_coll.find({
            "doctorUserId": str(doctor_user.id),
            "date": {"$gte": start_date, "$lte": end_date},
        }))

        # Fetch appointments in this month
        appts = list(db["appointments"].find({
            "doctorUserId": str(doctor_user.id),
            "appointmentDate": {"$gte": start_date, "$lte": end_date},
            "status": {"$in": ["HOLD", "PENDING", "CONFIRMED", "COMPLETED"]},
        }))

        # Fetch generated slots for each day
        days_overview: List[CalendarDayOverview] = []
        for day_i in range(1, num_days + 1):
            curr_date = f"{target_month}-{day_i:02d}"
            curr_weekday = datetime.strptime(curr_date, "%Y-%m-%d").strftime("%A").lower()

            # Check leave for this day
            day_leave_doc = None
            for l in leaves:
                if l["startDate"] <= curr_date <= l["endDate"]:
                    day_leave_doc = l
                    break

            # Check blocked times for this day
            day_blocks = [
                DoctorBlockedTimeResponse(
                    id=str(b["_id"]),
                    doctorUserId=str(b["doctorUserId"]),
                    doctorProfileId=str(b["doctorProfileId"]),
                    date=b["date"],
                    startTime=b["startTime"],
                    endTime=b["endTime"],
                    reason=b.get("reason"),
                    createdAt=b.get("createdAt", utc_now()),
                )
                for b in blocks
                if b["date"] == curr_date
            ]

            # Day appointments
            day_appts = []
            for a in appts:
                if a.get("appointmentDate") == curr_date:
                    p_doc = db["users"].find_one({"_id": ObjectId(a["patientUserId"])}) if ObjectId.is_valid(str(a.get("patientUserId"))) else None
                    p_name = (p_doc.get("fullName") if p_doc else None) or "Patient"
                    day_appts.append(
                        CalendarDayAppointment(
                            appointmentId=str(a["_id"]),
                            patientName=p_name,
                            startTime=a.get("startTime", ""),
                            endTime=a.get("endTime", ""),
                            status=a.get("status", ""),
                        )
                    )

            # Slots calculation for this day
            if curr_date < get_sl_today_str():
                day_slots = []
            else:
                day_slots_res = await cls.get_doctor_patient_slots(db, str(profile["_id"]), date_filter=curr_date)
                day_slots = day_slots_res.slots if hasattr(day_slots_res, "slots") else []

            # Determine Day Status
            if day_leave_doc and not day_leave_doc.get("startTime"):
                day_status = "LEAVE"
            elif day_leave_doc:
                day_status = "LEAVE"  # Partial leave
            elif day_blocks and len(day_slots) == 0:
                day_status = "BLOCKED"
            elif len(day_slots) > 0:
                day_status = "AVAILABLE"
            else:
                day_status = "UNAVAILABLE"

            days_overview.append(
                CalendarDayOverview(
                    date=curr_date,
                    weekday=curr_weekday,
                    status=day_status,
                    availableSlotsCount=len(day_slots),
                    bookedAppointmentsCount=len(day_appts),
                    leave=DoctorLeaveResponse(
                        id=str(day_leave_doc["_id"]),
                        doctorUserId=str(day_leave_doc["doctorUserId"]),
                        doctorProfileId=str(day_leave_doc["doctorProfileId"]),
                        leaveType=day_leave_doc.get("leaveType", "PERSONAL"),
                        startDate=day_leave_doc["startDate"],
                        endDate=day_leave_doc["endDate"],
                        startTime=day_leave_doc.get("startTime"),
                        endTime=day_leave_doc.get("endTime"),
                        reason=day_leave_doc.get("reason"),
                        status=day_leave_doc.get("status", "ACTIVE"),
                        createdAt=day_leave_doc.get("createdAt", utc_now()),
                        updatedAt=day_leave_doc.get("updatedAt", utc_now()),
                    ) if day_leave_doc else None,
                    blockedTimes=day_blocks,
                    appointments=day_appts,
                    slots=day_slots,
                )
            )

        return DoctorCalendarOverviewResponse(month=target_month, days=days_overview)

    # -------------------------------------------------------------
    # GENERATE PATIENT-VISIBLE SLOTS
    # -------------------------------------------------------------
    @staticmethod
    def _generate_slots_for_window(
        date_str: str,
        start_time_str: str,
        end_time_str: str,
        slot_duration_mins: int,
        availability_id: Optional[str] = None,
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
                slots.append(TimeSlot(
                    startTime=slot_start_str,
                    endTime=slot_end_str,
                    availabilityId=availability_id,
                ))

            current_mins += slot_duration_mins

        return slots

    @staticmethod
    async def get_doctor_patient_slots(
        db: Database,
        doctor_id: str,
        date_filter: Optional[str] = None,
    ) -> Any:
        """Generate and return available time slots for an APPROVED doctor, removing booked slots, leaves, and blocks."""
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

        doctor_user_id = str(user["_id"])
        doctor_profile_id = str(profile["_id"])

        # Fetch weekly schedule if exists
        weekly_sched = db["doctor_weekly_schedules"].find_one({"doctorUserId": doctor_user_id})

        # Dates to calculate
        sl_today = get_sl_today_str()
        dates_to_eval = []
        if date_filter and date_filter.strip():
            clean_date = date_filter.strip()
            DoctorService._validate_date_string(clean_date)
            dates_to_eval = [clean_date]
        else:
            # Query all future dates that have legacy records or evaluate next 14 days
            base_date = get_sl_now().date()
            future_days = {(base_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14)}
            legacy_dates = {
                r["date"]
                for r in db["doctor_availabilities"].find(
                    {"doctorProfileId": doctor_profile_id, "isActive": True, "date": {"$gte": sl_today}},
                    {"date": 1},
                )
            }
            dates_to_eval = sorted(future_days.union(legacy_dates))

        # Fetch active leaves covering dates
        min_date = dates_to_eval[0]
        max_date = dates_to_eval[-1]
        leaves = list(db["doctor_leaves"].find({
            "doctorUserId": doctor_user_id,
            "status": LeaveStatus.ACTIVE.value,
            "startDate": {"$lte": max_date},
            "endDate": {"$gte": min_date},
        }))

        # Fetch blocked times covering dates
        blocks = list(db["doctor_blocked_times"].find({
            "doctorUserId": doctor_user_id,
            "date": {"$gte": min_date, "$lte": max_date},
        }))

        # Fetch legacy date-specific availability records
        legacy_coll = get_doctor_availability_collection(db)
        legacy_records = list(legacy_coll.find({
            "doctorProfileId": doctor_profile_id,
            "isActive": True,
            "date": {"$in": dates_to_eval},
        }).sort([("startTime", 1)]))

        # Fetch active appointments
        now = datetime.now(timezone.utc)
        active_appts = list(
            db["appointments"].find(
                {
                    "doctorUserId": doctor_user_id,
                    "appointmentDate": {"$in": dates_to_eval},
                    "status": {"$in": ["HOLD", "PENDING", "CONFIRMED", "COMPLETED"]},
                },
                {"appointmentDate": 1, "startTime": 1, "status": 1, "holdExpiresAt": 1, "paymentStatus": 1},
            )
        )
        booked_slots = set()
        for a in active_appts:
            st = a.get("status")
            hold = a.get("holdExpiresAt")
            paid = a.get("paymentStatus") == "PAID"
            if st in ["HOLD", "PENDING"] and not paid and hold:
                if hold.tzinfo is None:
                    hold = hold.replace(tzinfo=timezone.utc)
                if hold <= now:
                    continue  # Expired hold
            booked_slots.add((a["appointmentDate"], a["startTime"]))

        grouped_slots: Dict[str, List[TimeSlot]] = {}
        for d_str in dates_to_eval:
            # 1. Check full-day leave
            full_day_leave = False
            partial_leaves = []
            for l in leaves:
                if l["startDate"] <= d_str <= l["endDate"]:
                    if not l.get("startTime") or not l.get("endTime"):
                        full_day_leave = True
                        break
                    else:
                        partial_leaves.append((l["startTime"], l["endTime"]))
            if full_day_leave:
                grouped_slots[d_str] = []
                continue

            day_blocks = [(b["startTime"], b["endTime"]) for b in blocks if b["date"] == d_str]

            # 2. Find sessions for this date
            day_sessions = []
            # Check legacy availability for this date first
            date_legacy = [r for r in legacy_records if r["date"] == d_str]
            if date_legacy:
                for rec in date_legacy:
                    day_sessions.append({
                        "startTime": rec["startTime"],
                        "endTime": rec["endTime"],
                        "slotDuration": int(rec.get("slotDurationMinutes", 30)),
                        "availId": str(rec["_id"]),
                    })
            elif weekly_sched:
                weekday_name = datetime.strptime(d_str, "%Y-%m-%d").strftime("%A").lower()
                slot_dur = int(weekly_sched.get("slotDurationMinutes", 30))
                for w in weekly_sched.get("weekdays", []):
                    if w.get("day") == weekday_name and w.get("isEnabled"):
                        for s in w.get("sessions", []):
                            day_sessions.append({
                                "startTime": s["startTime"],
                                "endTime": s["endTime"],
                                "slotDuration": slot_dur,
                                "availId": str(weekly_sched["_id"]),
                            })

            # 3. Generate slots for each session
            day_available_slots: List[TimeSlot] = []
            for s_info in day_sessions:
                raw_slots = DoctorService._generate_slots_for_window(
                    date_str=d_str,
                    start_time_str=s_info["startTime"],
                    end_time_str=s_info["endTime"],
                    slot_duration_mins=s_info["slotDuration"],
                    availability_id=s_info["availId"],
                )
                for slot in raw_slots:
                    # Filter out partial leave overlaps
                    slot_in_leave = any(
                        slot.startTime < pleave[1] and slot.endTime > pleave[0]
                        for pleave in partial_leaves
                    )
                    if slot_in_leave:
                        continue

                    # Filter out blocked time overlaps
                    slot_in_block = any(
                        slot.startTime < pblock[1] and slot.endTime > pblock[0]
                        for pblock in day_blocks
                    )
                    if slot_in_block:
                        continue

                    # Filter out booked slots
                    if (d_str, slot.startTime) in booked_slots:
                        continue

                    day_available_slots.append(slot)

            if day_available_slots or (date_filter and date_filter.strip()):
                grouped_slots[d_str] = day_available_slots

        day_availabilities = [
            DayAvailabilitySlots(date=d, slots=slots)
            for d, slots in sorted(grouped_slots.items(), key=lambda x: x[0])
            if slots or (date_filter and date_filter.strip())
        ]

        if date_filter and date_filter.strip():
            clean_date = date_filter.strip()
            return DayAvailabilitySlots(date=clean_date, slots=grouped_slots.get(clean_date, []))

        if len(day_availabilities) == 1:
            return day_availabilities[0]

        return day_availabilities
