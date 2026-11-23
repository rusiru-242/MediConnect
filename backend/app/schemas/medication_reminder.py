"""Pydantic schemas for Medication Reminder System request validation and responses (Phase 22)."""

from datetime import datetime
import re
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.medication_reminder import EventStatus, ReminderStatus

# Regex for 24-hour time "HH:MM" (00:00 to 23:59)
TIME_24H_REGEX = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class CreateMedicationReminderRequest(BaseModel):
    """Payload to create a medication reminder linked to an existing prescription."""

    prescriptionId: str = Field(
        ...,
        min_length=1,
        description="Prescription reference number e.g. RX-20261018-XXXX or MongoDB _id",
    )
    prescriptionMedicationIndex: int = Field(
        default=0,
        ge=0,
        description="Zero-based index of medication within prescription medicationItems",
    )
    scheduledTimes: List[str] = Field(
        ...,
        min_length=1,
        description="Daily reminder times in HH:MM format e.g. ['08:00', '20:00']",
    )
    patientTimezone: str = Field(
        default="Asia/Colombo",
        min_length=1,
        max_length=100,
        description="Timezone of the patient e.g. Asia/Colombo",
    )
    startDate: Optional[datetime] = Field(
        default=None,
        description="Optional start date; defaults to prescription issuance date or today",
    )
    endDate: Optional[datetime] = Field(
        default=None,
        description="Optional end date; calculated from prescribed duration if omitted",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Patient notes for this reminder",
    )

    @field_validator("scheduledTimes")
    @classmethod
    def validate_scheduled_times(cls, times: List[str]) -> List[str]:
        cleaned = []
        for t in times:
            t_str = t.strip()
            if not TIME_24H_REGEX.match(t_str):
                raise ValueError(f"Invalid time format '{t}'. Must be HH:MM in 24-hour format (00:00 - 23:59).")
            cleaned.append(t_str)
        # Return sorted unique times
        return sorted(list(set(cleaned)))


class UpdateMedicationReminderRequest(BaseModel):
    """Payload to update an existing medication reminder."""

    scheduledTimes: Optional[List[str]] = Field(
        default=None,
        description="Updated reminder times e.g. ['09:00', '21:00']",
    )
    patientTimezone: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    enabled: Optional[bool] = Field(
        default=None,
        description="Toggle notification delivery",
    )
    status: Optional[ReminderStatus] = Field(
        default=None,
        description="Update status: ACTIVE, PAUSED, COMPLETED, CANCELLED",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    @field_validator("scheduledTimes")
    @classmethod
    def validate_scheduled_times(cls, times: Optional[List[str]]) -> Optional[List[str]]:
        if times is None:
            return None
        if len(times) == 0:
            raise ValueError("scheduledTimes cannot be empty.")
        cleaned = []
        for t in times:
            t_str = t.strip()
            if not TIME_24H_REGEX.match(t_str):
                raise ValueError(f"Invalid time format '{t}'. Must be HH:MM in 24-hour format (00:00 - 23:59).")
            cleaned.append(t_str)
        return sorted(list(set(cleaned)))


class RecordMedicationEventRequest(BaseModel):
    """Payload to log a medication event: TAKEN, SKIPPED, or SNOOZED."""

    scheduledOccurrenceTime: datetime = Field(
        ...,
        description="The scheduled time (UTC) of this dose occurrence",
    )
    status: EventStatus = Field(
        ...,
        description="Event status: TAKEN, SKIPPED, or SNOOZED",
    )
    snoozeMinutes: Optional[int] = Field(
        default=15,
        ge=5,
        le=120,
        description="Duration in minutes if snoozing (5 to 120 minutes)",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Optional patient note for this event",
    )


class MedicationReminderResponse(BaseModel):
    """Response schema for a single medication reminder schedule."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str = Field(..., alias="_id")
    reminderId: str
    patientUserId: str
    prescriptionId: str
    prescriptionDbId: str
    prescriptionMedicationIndex: int

    medicationName: str
    strength: str
    dose: str
    route: str
    frequency: str
    duration: str

    scheduledTimes: List[str]
    patientTimezone: str
    startDate: datetime
    endDate: datetime
    enabled: bool
    status: str

    additionalInstructions: Optional[str] = None
    notes: Optional[str] = None

    createdAt: datetime
    updatedAt: datetime


class MedicationReminderListResponse(BaseModel):
    """Paginated list of medication reminders."""

    items: List[MedicationReminderResponse]
    total: int
    page: int
    pageSize: int
    totalPages: int


class MedicationEventResponse(BaseModel):
    """Response schema for a recorded medication intake event."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str = Field(..., alias="_id")
    eventId: str
    reminderId: str
    reminderDbId: str
    patientUserId: str
    scheduledOccurrenceTime: datetime
    status: str
    recordedAt: datetime
    snoozeMinutes: Optional[int] = None
    notes: Optional[str] = None
    medicationName: Optional[str] = None
    dose: Optional[str] = None


class MedicationEventListResponse(BaseModel):
    """Paginated list of medication intake history events."""

    items: List[MedicationEventResponse]
    total: int
    page: int
    pageSize: int
    totalPages: int


class TodayScheduleItem(BaseModel):
    """Single scheduled dose item for today's medication schedule."""

    reminderId: str
    reminderDbId: str
    medicationName: str
    strength: str
    dose: str
    route: str
    timeStr: str
    scheduledOccurrenceTime: datetime
    status: str  # "PENDING", "TAKEN", "SKIPPED", "SNOOZED"
    recordedAt: Optional[datetime] = None
    snoozeMinutes: Optional[int] = None
    additionalInstructions: Optional[str] = None


class TodayScheduleResponse(BaseModel):
    """Daily schedule view for the patient."""

    date: str
    patientTimezone: str
    totalScheduled: int
    takenCount: int
    skippedCount: int
    pendingCount: int
    items: List[TodayScheduleItem]


class AdherenceSummaryResponse(BaseModel):
    """Summary of medication adherence over past 30 days."""

    totalTrackedDays: int
    totalScheduledDoses: int
    takenDoses: int
    skippedDoses: int
    adherenceRatePercent: float
    activeRemindersCount: int
