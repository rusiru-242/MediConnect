"""Pydantic schemas for payment requests and responses."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CreatePaymentIntentRequest(BaseModel):
    """Request payload to initiate a Stripe payment for an appointment hold."""

    appointmentId: str = Field(..., description="ID of the held appointment to pay for")


class CreatePaymentIntentResponse(BaseModel):
    """Response returned when a Stripe PaymentIntent is created."""

    model_config = ConfigDict(populate_by_name=True)

    paymentIntentClientSecret: str = Field(..., description="Stripe client secret for PaymentSheet")
    paymentId: str = Field(..., description="MediConnect payment record _id")
    amount: int = Field(..., description="Amount in smallest currency unit (e.g. cents)")
    currency: str = Field(default="lkr", description="Currency code (e.g. 'lkr')")
    publishableKey: Optional[str] = Field(default=None, description="Stripe publishable key for client initialization")


class PaymentStatusResponse(BaseModel):
    """Authoritative payment and appointment status returned to patient."""

    model_config = ConfigDict(populate_by_name=True)

    paymentId: str
    appointmentId: str
    paymentStatus: str
    appointmentStatus: str
    amount: float
    currency: str


class PaymentHistoryItem(BaseModel):
    """Safe payment summary for patient payment history."""

    model_config = ConfigDict(populate_by_name=True)

    paymentId: str
    appointmentId: str
    doctorName: str
    amount: float
    currency: str
    status: str
    paidAt: Optional[datetime] = None
    createdAt: datetime


class PaymentHistoryResponse(BaseModel):
    """List of patient payments."""

    model_config = ConfigDict(populate_by_name=True)

    items: List[PaymentHistoryItem]
    total: int
