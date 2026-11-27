"""Pydantic schemas for Digital Prescriptions API (Phase 21)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MedicationItemSchema(BaseModel):
    """Schema for individual medication item."""

    # Whitespace-only values ("   ") are not a medicine name, strength or frequency (P03-N13).
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    medicationName: str = Field(..., min_length=1, max_length=200)
    strength: str = Field(..., min_length=1, max_length=100)
    dose: str = Field(..., min_length=1, max_length=100)
    route: str = Field(default="Oral", max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    duration: str = Field(..., min_length=1, max_length=100)
    quantity: str = Field(..., min_length=1, max_length=100)
    additionalInstructions: Optional[str] = Field(default=None, max_length=500)


class CreatePrescriptionRequest(BaseModel):
    """Doctor request to create a structured digital prescription."""

    medicalRecordId: str = Field(..., description="ID of associated consultation medical record")
    appointmentId: str = Field(..., description="ID of completed appointment")
    medicationItems: List[MedicationItemSchema] = Field(..., min_length=1)
    instructions: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("medicationItems")
    @classmethod
    def _no_repeats(cls, value):
        from app.schemas.clinical_workflow import reject_repeated_medicines  # A04-BUG-002
        return reject_repeated_medicines(value)


class AmendPrescriptionRequest(BaseModel):
    """Doctor request to safely amend an issued prescription with audit trail."""

    amendmentReason: str = Field(..., min_length=3, max_length=500, description="Mandatory clinical reason for amendment")
    medicationItems: List[MedicationItemSchema] = Field(..., min_length=1)
    instructions: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("medicationItems")
    @classmethod
    def _no_repeats(cls, value):
        from app.schemas.clinical_workflow import reject_repeated_medicines  # A04-BUG-002
        return reject_repeated_medicines(value)


class PrescriptionResponseSchema(BaseModel):
    """Response schema for digital prescription with doctor and patient metadata."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    prescriptionId: str
    medicalRecordId: Optional[str] = None
    appointmentId: Optional[str] = None
    patientUserId: str
    patientName: Optional[str] = None
    doctorUserId: str
    doctorName: Optional[str] = None
    doctorSpecialty: Optional[str] = None
    slmcRegistrationNumber: Optional[str] = None
    hospitalOrClinic: Optional[str] = None
    issuedAt: datetime
    status: str
    medicationItems: List[MedicationItemSchema]
    instructions: Optional[str] = None
    amendmentHistory: List[Dict[str, Any]] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime


class PrescriptionListResponse(BaseModel):
    """Paginated list response for digital prescriptions."""

    items: List[PrescriptionResponseSchema]
    total: int
    page: int
    pageSize: int
