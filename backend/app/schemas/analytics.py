"""Pydantic schemas for Admin Analytics Dashboard (Phase 24)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DateRangeFilter(BaseModel):
    """Optional date filter for analytics queries."""
    startDate: Optional[str] = Field(default=None, description="Start date YYYY-MM-DD")
    endDate: Optional[str] = Field(default=None, description="End date YYYY-MM-DD")


class TrendDataPoint(BaseModel):
    """Daily or periodic trend data point."""
    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    total: int = 0
    completed: int = 0
    confirmed: int = 0
    cancelled: int = 0


class CurrencyRevenue(BaseModel):
    """Revenue totals per currency."""
    currency: str = Field(..., description="ISO currency code (e.g. 'lkr', 'usd')")
    grossAmount: float = Field(0.0, description="Gross succeeded payment amount")
    refundedAmount: float = Field(0.0, description="Total refunded amount")
    netAmount: float = Field(0.0, description="Net earned revenue (gross - refunded)")
    paymentCount: int = Field(0, description="Count of succeeded transactions")


class SpecialtyCountItem(BaseModel):
    """Count of doctors per medical specialty."""
    specialty: str
    count: int


class CategoryAnalyticsItem(BaseModel):
    """Count of articles per health topic category."""
    category: str
    count: int
    publishedCount: int = 0


class TopContentItem(BaseModel):
    """Most bookmarked health articles."""
    contentId: str
    title: str
    category: str
    bookmarksCount: int


class AnalyticsOverviewResponse(BaseModel):
    """High-level platform overview metrics."""
    totalPatients: int = 0
    totalVerifiedDoctors: int = 0
    pendingDoctorApprovals: int = 0
    rejectedDoctorApplications: int = 0

    totalAppointments: int = 0
    confirmedAppointments: int = 0
    completedAppointments: int = 0
    cancelledAppointments: int = 0
    pendingAppointments: int = 0

    totalRevenueByCurrency: List[CurrencyRevenue] = Field(default_factory=list)
    successfulPaymentsCount: int = 0
    testPaymentsCount: int = 0
    livePaymentsCount: int = 0

    totalArticles: int = 0
    publishedArticles: int = 0
    draftArticles: int = 0
    totalBookmarks: int = 0

    startDate: Optional[str] = None
    endDate: Optional[str] = None
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AppointmentAnalyticsResponse(BaseModel):
    """Appointment detailed analytics and trends."""
    totalAppointments: int = 0
    statusBreakdown: Dict[str, int] = Field(default_factory=dict)
    trends: List[TrendDataPoint] = Field(default_factory=list)
    completionRate: float = Field(0.0, description="Percentage of completed vs non-cancelled")
    cancellationRate: float = Field(0.0, description="Percentage of cancelled vs total")
    startDate: Optional[str] = None
    endDate: Optional[str] = None


class PaymentTransactionSummary(BaseModel):
    """Safe payment transaction summary without sensitive card data."""
    id: str
    appointmentId: str
    amount: float
    currency: str
    status: str
    isTestPayment: bool
    paidAt: Optional[datetime] = None
    createdAt: datetime


class PaymentAnalyticsResponse(BaseModel):
    """Payment & revenue analytics with Stripe test/live distinction."""
    successfulPaymentsCount: int = 0
    testPaymentsCount: int = 0
    livePaymentsCount: int = 0
    failedPaymentsCount: int = 0
    refundedPaymentsCount: int = 0
    revenueByCurrency: List[CurrencyRevenue] = Field(default_factory=list)
    isStripeTestMode: bool = True
    recentTransactions: List[PaymentTransactionSummary] = Field(default_factory=list)
    startDate: Optional[str] = None
    endDate: Optional[str] = None


class DoctorAnalyticsResponse(BaseModel):
    """Doctor verification and specialty distribution analytics."""
    totalDoctors: int = 0
    approvedDoctors: int = 0
    pendingDoctors: int = 0
    rejectedDoctors: int = 0
    specialtyDistribution: List[SpecialtyCountItem] = Field(default_factory=list)
    averageExperienceYears: float = 0.0
    averageConsultationFee: float = 0.0


class ContentAnalyticsResponse(BaseModel):
    """Content publishing and bookmark engagement statistics."""
    totalArticles: int = 0
    publishedArticles: int = 0
    draftArticles: int = 0
    archivedArticles: int = 0
    categoryDistribution: List[CategoryAnalyticsItem] = Field(default_factory=list)
    totalBookmarks: int = 0
    topBookmarkedArticles: List[TopContentItem] = Field(default_factory=list)
