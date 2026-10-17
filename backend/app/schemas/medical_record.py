"""Pydantic schemas for Medical Consultation Records API (Phase 21)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.prescription import PrescriptionResponseSchema


class CreateMedicalRecordRequest(BaseModel):
    """Doctor request to create a medical consultation record for a completed appointment."""

    appointmentId: str = Field(..., description="ID of completed appointment")
    clinicalNotes: str = Field(..., min_length=1, max_length=5000, description="Symptoms, clinical observations")
    assessment: str = Field(..., min_length=1, max_length=2000, description="Diagnostic impression / clinical assessment")
    treatmentPlan: str = Field(..., min_length=1, max_length=5000, description="Care plan and recommendations")
    followUpInstructions: Optional[str] = Field(default=None, max_length=2000)


class AmendMedicalRecordRequest(BaseModel):
    """Doctor request to amend an existing medical record with required reason and audit trail."""

    amendmentReason: str = Field(..., min_length=3, max_length=500, description="Clinical reason for record correction")
    clinicalNotes: str = Field(..., min_length=1, max_length=5000)
    assessment: str = Field(..., min_length=1, max_length=2000)
    treatmentPlan: str = Field(..., min_length=1, max_length=5000)
    followUpInstructions: Optional[str] = Field(default=None, max_length=2000)


class MedicalRecordResponseSchema(BaseModel):
    """Response schema for a consultation medical record with doctor, patient, and prescription details."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    recordId: str
    patientUserId: str
    patientName: Optional[str] = None
    doctorUserId: str
    doctorName: Optional[str] = None
    doctorSpecialty: Optional[str] = None
    slmcRegistrationNumber: Optional[str] = None
    hospitalOrClinic: Optional[str] = None
    appointmentId: str
    consultationDate: str
    clinicalNotes: str
    assessment: str
    treatmentPlan: str
    followUpInstructions: Optional[str] = None
    status: str
    prescription: Optional[PrescriptionResponseSchema] = None
    amendmentHistory: List[Dict[str, Any]] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime


class MedicalRecordListResponse(BaseModel):
    """Paginated list response for medical records."""

    items: List[MedicalRecordResponseSchema]
    total: int
    page: int
    pageSize: int
