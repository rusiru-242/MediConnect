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


# -----------------------------------------------------------------------------
# Admin User Management Schemas
# -----------------------------------------------------------------------------

class AdminUserItem(BaseModel):
    """Privacy-safe user item for admin management (least-privilege)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: str
    fullName: str
    phone: Optional[str] = None
    role: str
    accountStatus: str
    emailVerified: bool = False
    createdAt: datetime
    updatedAt: Optional[datetime] = None
    lastLoginAt: Optional[datetime] = None


class AdminUserListResponse(BaseModel):
    """Paginated list of users for administration."""

    items: List[AdminUserItem]
    total: int
    page: int
    pageSize: int
    totalPages: int


class UpdateUserStatusRequest(BaseModel):
    """Request payload to change a user's account status."""

    accountStatus: str = Field(..., description="ACTIVE, SUSPENDED, PENDING, or DEACTIVATED")


# -----------------------------------------------------------------------------
# Admin Doctor Directory Schemas
# -----------------------------------------------------------------------------

class AdminDoctorListItem(BaseModel):
    """Detailed doctor item for administrative directory."""

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
    accountStatus: str
    submittedAt: datetime
    verifiedAt: Optional[datetime] = None
    averageRating: Optional[float] = None
    totalReviews: int = 0


class AdminDoctorListResponse(BaseModel):
    """Paginated list of doctors for administration."""

    items: List[AdminDoctorListItem]
    total: int
    page: int
    pageSize: int
    totalPages: int


# -----------------------------------------------------------------------------
# Admin Appointment Management Schemas
# -----------------------------------------------------------------------------

class AdminAppointmentItem(BaseModel):
    """Appointment item for administrative monitoring."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    patientUserId: str
    patientName: str
    patientEmail: str
    doctorUserId: str
    doctorName: str
    doctorSpecialty: str
    appointmentDate: str
    startTime: str
    endTime: str
    status: str
    paymentStatus: str
    consultationFee: Optional[float] = 0.0
    patientNote: Optional[str] = None
    cancellationReason: Optional[str] = None
    cancelledBy: Optional[str] = None
    createdAt: datetime


class AdminAppointmentListResponse(BaseModel):
    """Paginated list of appointments for administration."""

    items: List[AdminAppointmentItem]
    total: int
    page: int
    pageSize: int
    totalPages: int


# -----------------------------------------------------------------------------
# Admin Payment Monitoring Schemas
# -----------------------------------------------------------------------------

class AdminPaymentItem(BaseModel):
    """Payment record representation for administrative financial oversight."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    appointmentId: str
    patientUserId: str
    patientName: str
    doctorUserId: str
    doctorName: str
    stripePaymentIntentId: str
    amount: float
    currency: str
    status: str
    isTestMode: bool = False
    failureReason: Optional[str] = None
    paidAt: Optional[datetime] = None
    createdAt: datetime


class AdminPaymentListResponse(BaseModel):
    """Paginated list of payment transactions."""

    items: List[AdminPaymentItem]
    total: int
    page: int
    pageSize: int
    totalPages: int


# -----------------------------------------------------------------------------
# Admin Review Management Schemas
# -----------------------------------------------------------------------------

class AdminReviewItem(BaseModel):
    """Review item for administrative moderation overview."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    appointmentId: str
    doctorId: str
    doctorName: str
    patientId: str
    patientName: str
    rating: int
    reviewText: Optional[str] = None
    status: str
    isReported: bool = False
    reportReason: Optional[str] = None
    moderationNotes: Optional[str] = None
    createdAt: datetime


class AdminReviewListResponse(BaseModel):
    """Paginated list of reviews for administration."""

    items: List[AdminReviewItem]
    total: int
    page: int
    pageSize: int
    totalPages: int
