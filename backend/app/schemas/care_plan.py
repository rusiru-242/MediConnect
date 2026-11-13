"""Pydantic schemas for Smart Follow-up Care Plans (Phase 56)."""

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CareTaskSchema(BaseModel):
    """Non-medication task representation."""

    model_config = ConfigDict(populate_by_name=True)

    taskId: str
    title: str
    description: Optional[str] = None
    isCompleted: bool = False
    completedAt: Optional[datetime] = None


class CreateCareTaskRequest(BaseModel):
    """Payload to add a task to a care plan."""

    title: str = Field(..., min_length=2, max_length=200, description="Task title")
    description: Optional[str] = Field(None, max_length=500, description="Optional task details")


class CarePlanAuditEntrySchema(BaseModel):
    """Audit entry representation."""

    model_config = ConfigDict(populate_by_name=True)

    action: str
    performedBy: str
    performedByRole: str
    timestamp: datetime
    note: Optional[str] = None


class CreateCarePlanRequest(BaseModel):
    """Payload for doctor creating a new follow-up care plan for a consultation."""

    appointmentId: str = Field(..., description="ID of the consultation appointment")
    followUpDate: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Follow-up date YYYY-MM-DD")
    followUpDateEnd: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Optional range end YYYY-MM-DD")
    reason: str = Field(..., min_length=3, max_length=300, description="Follow-up clinical reason")
    instructions: str = Field(..., min_length=5, max_length=2000, description="Specific care instructions")
    recommendedConsultationType: Optional[str] = Field(default="IN_PERSON", description="IN_PERSON, VIDEO, AUDIO")
    tasks: List[CreateCareTaskRequest] = Field(default_factory=list, description="Non-medication actionable tasks")
    linkedPrescriptionIds: List[str] = Field(default_factory=list, description="Related prescription IDs")
    linkedMedicalRecordIds: List[str] = Field(default_factory=list, description="Related medical record IDs")


class UpdateCarePlanRequest(BaseModel):
    """Payload for doctor modifying an active follow-up care plan."""

    followUpDate: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    followUpDateEnd: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: Optional[str] = Field(None, min_length=3, max_length=300)
    instructions: Optional[str] = Field(None, min_length=5, max_length=2000)
    recommendedConsultationType: Optional[str] = None
    tasks: Optional[List[CreateCareTaskRequest]] = None
    linkedPrescriptionIds: Optional[List[str]] = None
    linkedMedicalRecordIds: Optional[List[str]] = None


class CancelCarePlanRequest(BaseModel):
    """Payload for cancelling a care plan."""

    reason: str = Field(..., min_length=3, max_length=300, description="Reason for cancellation")


class UpdateTaskStatusRequest(BaseModel):
    """Payload for patient toggling completion status of a task."""

    isCompleted: bool = Field(..., description="True if completed, False if pending")


class LinkAppointmentRequest(BaseModel):
    """Payload for patient linking a booked follow-up appointment to care plan."""

    appointmentId: str = Field(..., description="ID of the newly booked appointment")


class CarePlanResponse(BaseModel):
    """Public representation of a follow-up care plan."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    patientUserId: str
    patientName: Optional[str] = None
    doctorUserId: str
    doctorProfileId: str
    doctorName: Optional[str] = None
    doctorSpecialty: Optional[str] = None
    doctorHospital: Optional[str] = None
    appointmentId: str
    consultationDate: Optional[str] = None
    followUpDate: str
    followUpDateEnd: Optional[str] = None
    reason: str
    instructions: str
    recommendedConsultationType: str = "IN_PERSON"
    tasks: List[CareTaskSchema] = []
    linkedPrescriptionIds: List[str] = []
    linkedMedicalRecordIds: List[str] = []
    bookedAppointmentId: Optional[str] = None
    status: str
    version: int = 1
    createdBy: str
    updatedBy: str
    auditLog: List[CarePlanAuditEntrySchema] = []
    remindersSent: List[str] = []
    createdAt: datetime
    updatedAt: datetime


class CarePlanListResponse(BaseModel):
    """List response wrapper for care plans."""

    total: int
    plans: List[CarePlanResponse]
