"""Schemas for Admin Doctor Verification Workflow."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AdminDoctorApplicationSummary(BaseModel):
    """Summary representation of a doctor application for admin list view."""

    model_config = ConfigDict(populate_by_name=True)

    doctorProfileId: str
    userId: str
    fullName: str
    email: str
    phone: Optional[str] = None
    specialty: str
    medicalRegistrationNumber: str
    hospitalOrClinic: str
    experienceYears: int
    verificationStatus: str
    submittedAt: datetime


class AdminDoctorDocumentMetadata(BaseModel):
    """Safe metadata representation of an uploaded verification document (no server paths)."""

    model_config = ConfigDict(populate_by_name=True)

    documentKey: str = Field(..., description="Document identifier/key, e.g. identityDocument")
    title: str = Field(..., description="Human-readable title for the document")
    filename: str = Field(..., description="Original safe filename")
    mimeType: str
    sizeBytes: int
    uploadedAt: Optional[datetime] = None


class AdminDoctorApplicationDetail(BaseModel):
    """Detailed doctor application information for admin review."""

    model_config = ConfigDict(populate_by_name=True)

    doctorProfileId: str
    userId: str
    fullName: str
    email: str
    phone: Optional[str] = None
    specialty: str
    medicalRegistrationNumber: str
    qualifications: str
    hospitalOrClinic: str
    experienceYears: int
    bio: Optional[str] = None
    verificationStatus: str
    rejectionReason: Optional[str] = None
    submittedAt: datetime
    verifiedAt: Optional[datetime] = None
    verifiedBy: Optional[str] = None
    documents: List[AdminDoctorDocumentMetadata] = Field(default_factory=list)


class RejectDoctorRequest(BaseModel):
    """Request payload to reject a doctor application."""

    reason: str = Field(..., min_length=3, max_length=1000, description="Reason for rejection")


class AdminActionResponse(BaseModel):
    """Generic response for admin doctor actions."""

    message: str
