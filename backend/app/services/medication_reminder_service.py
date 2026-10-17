"""Service logic for Smart Medication Reminders and Tracking (Phase 22)."""

from datetime import datetime, time, timedelta, timezone
import logging
import math
import re
from typing import Any, Dict, List, Optional
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import DESCENDING
from pymongo.database import Database

from app.models.medication_reminder import (
    EventStatus,
    MedicationEventDocument,
    MedicationReminderDocument,
    ReminderStatus,
    get_medication_event_collection,
    get_medication_reminder_collection,
    utc_now,
)
from app.models.prescription import (
    PrescriptionStatus,
    get_prescription_collection,
)
from app.models.user import UserRole
from app.schemas.medication_reminder import (
    AdherenceSummaryResponse,
    CreateMedicationReminderRequest,
    MedicationEventListResponse,
    MedicationEventResponse,
    MedicationReminderListResponse,
    MedicationReminderResponse,
    RecordMedicationEventRequest,
    TodayScheduleItem,
    TodayScheduleResponse,
    UpdateMedicationReminderRequest,
)
from app.schemas.user import UserResponseSchema

logger = logging.getLogger(__name__)


def parse_duration_days(duration: str) -> int:
    """Parse medical duration string into number of days. Defaults to 7 days."""
    if not duration:
        return 7
    d_clean = duration.strip().lower()
    match = re.search(r"(\d+)\s*(day|week|month)s?", d_clean)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        if unit == "day":
            return max(1, val)
        elif unit == "week":
            return max(1, val * 7)
        elif unit == "month":
            return max(1, val * 30)
    return 7


def expected_doses_per_day(frequency: str) -> Optional[int]:
    """Derive expected daily reminder count from doctor's prescribed frequency string."""
    if not frequency:
        return None
    f_clean = frequency.strip().lower()
    if any(k in f_clean for k in ["once daily", "once a day", "od", "daily"]):
        if not any(k in f_clean for k in ["twice", "three", "four", "bd", "tds", "qds"]):
            return 1
    if any(k in f_clean for k in ["twice daily", "twice a day", "bd", "bid"]):
        return 2
    if any(k in f_clean for k in ["three times", "thrice", "tds", "tid"]):
        return 3
    if any(k in f_clean for k in ["four times", "qds", "qid"]):
        return 4
    return None


def get_safe_timezone(tz_name: Optional[str]) -> ZoneInfo:
    """Safely return a ZoneInfo instance with fallback to Asia/Colombo."""
    fallback = ZoneInfo("Asia/Colombo")
    if not tz_name or not tz_name.strip():
        return fallback
    try:
        return ZoneInfo(tz_name.strip())
    except (ZoneInfoNotFoundError, Exception):
        logger.warning("Unrecognized timezone '%s', defaulting to Asia/Colombo", tz_name)
        return fallback


class MedicationReminderService:
    """Core domain logic for creating and tracking prescription medication reminders."""

    @staticmethod
    async def create_reminder(
        db: Database,
        patient_user: UserResponseSchema,
        req: CreateMedicationReminderRequest,
    ) -> MedicationReminderResponse:
        """Create a structured medication reminder schedule from a doctor's prescription."""
        if patient_user.role != UserRole.PATIENT.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can create medication reminders for their prescriptions.",
            )

        # 1. Fetch prescription
        rx_coll = get_prescription_collection(db)
        prescription = None
        if ObjectId.is_valid(req.prescriptionId):
            prescription = rx_coll.find_one({"_id": ObjectId(req.prescriptionId)})
        if not prescription:
            prescription = rx_coll.find_one({"prescriptionId": req.prescriptionId})

        if not prescription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prescription '{req.prescriptionId}' was not found.",
            )

        # 2. Verify patient ownership
        if str(prescription.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot create reminders for another patient's prescription.",
            )

        # 3. Check prescription status
        rx_status = prescription.get("status")
        if rx_status == PrescriptionStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create reminders for a cancelled prescription.",
            )

        # 4. Check medication item index
        items = prescription.get("medicationItems", [])
        if req.prescriptionMedicationIndex < 0 or req.prescriptionMedicationIndex >= len(items):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prescription does not contain medication index {req.prescriptionMedicationIndex}.",
            )

        med_item = items[req.prescriptionMedicationIndex]

        # 5. Prevent duplicate active reminder for the same prescription medication
        reminder_coll = get_medication_reminder_collection(db)
        existing_active = reminder_coll.find_one(
            {
                "patientUserId": str(patient_user.id),
                "prescriptionDbId": str(prescription["_id"]),
                "prescriptionMedicationIndex": req.prescriptionMedicationIndex,
                "status": ReminderStatus.ACTIVE.value,
            }
        )
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active reminder already exists for {med_item.get('medicationName')} from this prescription.",
            )

        # 6. Validate schedule times count against prescribed frequency
        freq = med_item.get("frequency", "")
        expected_doses = expected_doses_per_day(freq)
        if expected_doses is not None and len(req.scheduledTimes) != expected_doses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Prescribed frequency is '{freq}' ({expected_doses} dose{'s' if expected_doses > 1 else ''}/day), "
                    f"but {len(req.scheduledTimes)} reminder time{'s were' if len(req.scheduledTimes) > 1 else ' was'} provided. "
                    f"Please choose exactly {expected_doses} reminder times."
                ),
            )

        # 7. Calculate start and end dates
        start_dt = req.startDate or utc_now()
        duration_days = parse_duration_days(med_item.get("duration", "7 days"))
        end_dt = req.endDate or (start_dt + timedelta(days=duration_days))

        # 8. Generate reference ID
        now = utc_now()
        ref_id = f"REM-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        doc = MedicationReminderDocument(
            reminderId=ref_id,
            patientUserId=str(patient_user.id),
            prescriptionId=prescription.get("prescriptionId", req.prescriptionId),
            prescriptionDbId=str(prescription["_id"]),
            prescriptionMedicationIndex=req.prescriptionMedicationIndex,
            medicationName=med_item.get("medicationName", ""),
            strength=med_item.get("strength", ""),
            dose=med_item.get("dose", ""),
            route=med_item.get("route", "Oral"),
            frequency=freq,
            duration=med_item.get("duration", ""),
            scheduledTimes=req.scheduledTimes,
            patientTimezone=req.patientTimezone,
            startDate=start_dt,
            endDate=end_dt,
            enabled=True,
            status=ReminderStatus.ACTIVE,
            additionalInstructions=med_item.get("additionalInstructions"),
            notes=req.notes,
            createdAt=now,
            updatedAt=now,
        )

        doc_dict = doc.model_dump(by_alias=True, exclude={"id"})
        res = reminder_coll.insert_one(doc_dict)
        doc_dict["_id"] = str(res.inserted_id)

        return MedicationReminderResponse(**doc_dict)

    @staticmethod
    async def list_patient_reminders(
        db: Database,
        patient_user: UserResponseSchema,
        active_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> MedicationReminderListResponse:
        """List reminders owned by the authenticated patient."""
        reminder_coll = get_medication_reminder_collection(db)
        query: Dict[str, Any] = {"patientUserId": str(patient_user.id)}
        if active_only:
            query["status"] = ReminderStatus.ACTIVE.value
            query["enabled"] = True

        total = reminder_coll.count_documents(query)
        cursor = (
            reminder_coll.find(query)
            .sort("createdAt", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        items = []
        for raw in cursor:
            raw["_id"] = str(raw["_id"])
            items.append(MedicationReminderResponse(**raw))

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return MedicationReminderListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )

    @staticmethod
    async def get_reminder(
        db: Database,
        current_user: UserResponseSchema,
        reminder_id: str,
    ) -> MedicationReminderResponse:
        """Retrieve single reminder by ID with patient ownership check."""
        reminder_coll = get_medication_reminder_collection(db)
        query: Dict[str, Any] = {"$or": [{"reminderId": reminder_id}]}
        if ObjectId.is_valid(reminder_id):
            query["$or"].append({"_id": ObjectId(reminder_id)})

        raw = reminder_coll.find_one(query)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medication reminder '{reminder_id}' was not found.",
            )

        if str(raw.get("patientUserId")) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this medication reminder.",
            )

        raw["_id"] = str(raw["_id"])
        return MedicationReminderResponse(**raw)

    @staticmethod
    async def update_reminder(
        db: Database,
        current_user: UserResponseSchema,
        reminder_id: str,
        req: UpdateMedicationReminderRequest,
    ) -> MedicationReminderResponse:
        """Update an existing medication reminder schedule."""
        reminder_coll = get_medication_reminder_collection(db)
        query: Dict[str, Any] = {"$or": [{"reminderId": reminder_id}]}
        if ObjectId.is_valid(reminder_id):
            query["$or"].append({"_id": ObjectId(reminder_id)})

        raw = reminder_coll.find_one(query)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medication reminder '{reminder_id}' was not found.",
            )

        if str(raw.get("patientUserId")) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to modify this medication reminder.",
            )

        update_fields: Dict[str, Any] = {"updatedAt": utc_now()}

        if req.scheduledTimes is not None:
            freq = raw.get("frequency", "")
            expected_doses = expected_doses_per_day(freq)
            if expected_doses is not None and len(req.scheduledTimes) != expected_doses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Prescribed frequency is '{freq}' ({expected_doses} dose{'s' if expected_doses > 1 else ''}/day). "
                        f"Cannot schedule {len(req.scheduledTimes)} reminder times."
                    ),
                )
            update_fields["scheduledTimes"] = req.scheduledTimes

        if req.patientTimezone is not None:
            update_fields["patientTimezone"] = req.patientTimezone

        if req.enabled is not None:
            update_fields["enabled"] = req.enabled

        if req.status is not None:
            update_fields["status"] = req.status.value

        if req.notes is not None:
            update_fields["notes"] = req.notes

        reminder_coll.update_one({"_id": raw["_id"]}, {"$set": update_fields})
        updated = reminder_coll.find_one({"_id": raw["_id"]})
        updated["_id"] = str(updated["_id"])
        return MedicationReminderResponse(**updated)

    @staticmethod
    async def delete_reminder(
        db: Database,
        current_user: UserResponseSchema,
        reminder_id: str,
    ) -> Dict[str, Any]:
        """Delete or cancel a medication reminder."""
        reminder_coll = get_medication_reminder_collection(db)
        query: Dict[str, Any] = {"$or": [{"reminderId": reminder_id}]}
        if ObjectId.is_valid(reminder_id):
            query["$or"].append({"_id": ObjectId(reminder_id)})

        raw = reminder_coll.find_one(query)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medication reminder '{reminder_id}' was not found.",
            )

        if str(raw.get("patientUserId")) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to delete this medication reminder.",
            )

        # Mark cancelled and disabled to maintain historical event linkages
        reminder_coll.update_one(
            {"_id": raw["_id"]},
            {
                "$set": {
                    "status": ReminderStatus.CANCELLED.value,
                    "enabled": False,
                    "updatedAt": utc_now(),
                }
            },
        )

        return {
            "success": True,
            "message": "Medication reminder cancelled successfully.",
            "reminderId": raw.get("reminderId"),
        }

    @staticmethod
    async def get_today_schedule(
        db: Database,
        patient_user: UserResponseSchema,
        timezone_str: Optional[str] = None,
    ) -> TodayScheduleResponse:
        """Generate today's scheduled occurrences and recorded statuses in patient local time."""
        tz = get_safe_timezone(timezone_str or "Asia/Colombo")
        local_now = datetime.now(tz)
        today_date_str = local_now.strftime("%Y-%m-%d")

        # Today's boundaries in UTC
        start_of_today_local = datetime(local_now.year, local_now.month, local_now.day, 0, 0, 0, tzinfo=tz)
        end_of_today_local = datetime(local_now.year, local_now.month, local_now.day, 23, 59, 59, tzinfo=tz)
        start_of_today_utc = start_of_today_local.astimezone(timezone.utc)
        end_of_today_utc = end_of_today_local.astimezone(timezone.utc)

        reminder_coll = get_medication_reminder_collection(db)
        event_coll = get_medication_event_collection(db)

        # Active, enabled reminders covering today
        reminders = list(
            reminder_coll.find(
                {
                    "patientUserId": str(patient_user.id),
                    "status": ReminderStatus.ACTIVE.value,
                    "enabled": True,
                    "startDate": {"$lte": end_of_today_utc},
                    "endDate": {"$gte": start_of_today_utc},
                }
            )
        )

        items: List[TodayScheduleItem] = []
        taken_count = 0
        skipped_count = 0
        pending_count = 0

        for r in reminders:
            r_db_id = str(r["_id"])
            times = r.get("scheduledTimes", [])

            for t_str in times:
                try:
                    parts = t_str.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1])
                except Exception:
                    continue

                slot_local = datetime(local_now.year, local_now.month, local_now.day, hour, minute, 0, tzinfo=tz)
                slot_utc = slot_local.astimezone(timezone.utc)

                # Look up recorded event
                event = event_coll.find_one(
                    {
                        "reminderDbId": r_db_id,
                        "scheduledOccurrenceTime": slot_utc,
                    }
                )

                item_status = "PENDING"
                recorded_at = None
                snooze_min = None

                if event:
                    item_status = event.get("status", "PENDING")
                    recorded_at = event.get("recordedAt")
                    snooze_min = event.get("snoozeMinutes")

                if item_status == EventStatus.TAKEN.value:
                    taken_count += 1
                elif item_status == EventStatus.SKIPPED.value:
                    skipped_count += 1
                else:
                    pending_count += 1

                items.append(
                    TodayScheduleItem(
                        reminderId=r.get("reminderId", ""),
                        reminderDbId=r_db_id,
                        medicationName=r.get("medicationName", ""),
                        strength=r.get("strength", ""),
                        dose=r.get("dose", ""),
                        route=r.get("route", "Oral"),
                        timeStr=t_str,
                        scheduledOccurrenceTime=slot_utc,
                        status=item_status,
                        recordedAt=recorded_at,
                        snoozeMinutes=snooze_min,
                        additionalInstructions=r.get("additionalInstructions"),
                    )
                )

        # Sort chronological by scheduledOccurrenceTime
        items.sort(key=lambda x: x.scheduledOccurrenceTime)

        return TodayScheduleResponse(
            date=today_date_str,
            patientTimezone=str(tz),
            totalScheduled=len(items),
            takenCount=taken_count,
            skippedCount=skipped_count,
            pendingCount=pending_count,
            items=items,
        )

    @staticmethod
    async def record_event(
        db: Database,
        patient_user: UserResponseSchema,
        reminder_id: str,
        req: RecordMedicationEventRequest,
    ) -> MedicationEventResponse:
        """Idempotently record or update a medication intake event (taken, skipped, snoozed)."""
        reminder_coll = get_medication_reminder_collection(db)
        event_coll = get_medication_event_collection(db)

        query: Dict[str, Any] = {"$or": [{"reminderId": reminder_id}]}
        if ObjectId.is_valid(reminder_id):
            query["$or"].append({"_id": ObjectId(reminder_id)})

        reminder = reminder_coll.find_one(query)
        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medication reminder '{reminder_id}' was not found.",
            )

        if str(reminder.get("patientUserId")) != str(patient_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot record medication events for another patient.",
            )

        # Ensure scheduled occurrence time is UTC
        occurrence_time = req.scheduledOccurrenceTime
        if occurrence_time.tzinfo is None:
            occurrence_time = occurrence_time.replace(tzinfo=timezone.utc)
        else:
            occurrence_time = occurrence_time.astimezone(timezone.utc)

        r_db_id = str(reminder["_id"])
        now = utc_now()

        # Idempotent upsert based on (reminderDbId, scheduledOccurrenceTime)
        filter_doc = {
            "reminderDbId": r_db_id,
            "scheduledOccurrenceTime": occurrence_time,
        }

        existing_event = event_coll.find_one(filter_doc)

        if existing_event:
            # Update existing event record
            update_data = {
                "status": req.status.value,
                "recordedAt": now,
                "notes": req.notes,
            }
            if req.status == EventStatus.SNOOZED:
                update_data["snoozeMinutes"] = req.snoozeMinutes or 15
            else:
                update_data["snoozeMinutes"] = None

            event_coll.update_one({"_id": existing_event["_id"]}, {"$set": update_data})
            saved = event_coll.find_one({"_id": existing_event["_id"]})
        else:
            # Insert new event record
            event_ref_id = f"EVT-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            new_event = MedicationEventDocument(
                eventId=event_ref_id,
                reminderId=reminder.get("reminderId", reminder_id),
                reminderDbId=r_db_id,
                patientUserId=str(patient_user.id),
                scheduledOccurrenceTime=occurrence_time,
                status=req.status,
                recordedAt=now,
                snoozeMinutes=req.snoozeMinutes if req.status == EventStatus.SNOOZED else None,
                notes=req.notes,
            )
            insert_dict = new_event.model_dump(by_alias=True, exclude={"id"})
            res = event_coll.insert_one(insert_dict)
            insert_dict["_id"] = str(res.inserted_id)
            saved = insert_dict

        saved["_id"] = str(saved["_id"])
        saved["medicationName"] = reminder.get("medicationName")
        saved["dose"] = reminder.get("dose")

        return MedicationEventResponse(**saved)

    @staticmethod
    async def get_history(
        db: Database,
        patient_user: UserResponseSchema,
        page: int = 1,
        page_size: int = 20,
    ) -> MedicationEventListResponse:
        """Retrieve paginated chronological medication intake event history for the patient."""
        event_coll = get_medication_event_collection(db)
        reminder_coll = get_medication_reminder_collection(db)

        query = {"patientUserId": str(patient_user.id)}
        total = event_coll.count_documents(query)
        cursor = (
            event_coll.find(query)
            .sort("scheduledOccurrenceTime", DESCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        # Pre-cache reminders for fast lookup
        reminder_ids = set()
        events_raw = list(cursor)
        for e in events_raw:
            reminder_ids.add(e.get("reminderDbId"))

        reminders_map = {}
        if reminder_ids:
            obj_ids = [ObjectId(rid) for rid in reminder_ids if ObjectId.is_valid(rid)]
            for r in reminder_coll.find({"_id": {"$in": obj_ids}}):
                reminders_map[str(r["_id"])] = r

        items: List[MedicationEventResponse] = []
        for e in events_raw:
            e["_id"] = str(e["_id"])
            r_info = reminders_map.get(e.get("reminderDbId"), {})
            e["medicationName"] = r_info.get("medicationName", "Medication")
            e["dose"] = r_info.get("dose", "")
            items.append(MedicationEventResponse(**e))

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return MedicationEventListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
            totalPages=total_pages,
        )

    @staticmethod
    async def get_adherence_summary(
        db: Database,
        patient_user: UserResponseSchema,
    ) -> AdherenceSummaryResponse:
        """Compute non-judgmental adherence summary statistics over the past 30 days."""
        now = utc_now()
        thirty_days_ago = now - timedelta(days=30)

        event_coll = get_medication_event_collection(db)
        reminder_coll = get_medication_reminder_collection(db)

        active_count = reminder_coll.count_documents(
            {
                "patientUserId": str(patient_user.id),
                "status": ReminderStatus.ACTIVE.value,
                "enabled": True,
            }
        )

        events_30d = list(
            event_coll.find(
                {
                    "patientUserId": str(patient_user.id),
                    "scheduledOccurrenceTime": {"$gte": thirty_days_ago},
                }
            )
        )

        taken_doses = sum(1 for e in events_30d if e.get("status") == EventStatus.TAKEN.value)
        skipped_doses = sum(1 for e in events_30d if e.get("status") == EventStatus.SKIPPED.value)
        total_doses = taken_doses + skipped_doses

        adherence_rate = (
            round((taken_doses / total_doses) * 100, 1) if total_doses > 0 else 100.0
        )

        return AdherenceSummaryResponse(
            totalTrackedDays=30,
            totalScheduledDoses=total_doses,
            takenDoses=taken_doses,
            skippedDoses=skipped_doses,
            adherenceRatePercent=adherence_rate,
            activeRemindersCount=active_count,
        )
