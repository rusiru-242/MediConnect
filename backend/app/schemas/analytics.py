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
    grossAmount: float = Field(0.0, description="Gross collections: captured payments (SUCCEEDED or REFUNDED)")
    refundedAmount: float = Field(0.0, description="Money returned on those payments (full and partial refunds)")
    netAmount: float = Field(0.0, description="Net collections (gross - refunded). Not platform profit.")
    paymentCount: int = Field(0, description="Count of captured payments")
    partiallyRefundedCount: int = 0
    fullyRefundedCount: int = 0
    pendingRefundAmount: float = Field(0.0, description="Amount set for refund requests that are still open")
    pendingRefundCount: int = 0


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


class OverviewTotalsSchema(BaseModel):
    """Aggregated user, doctor, and appointment count totals."""
    totalUsers: int = 0
    totalPatients: int = 0
    totalDoctors: int = 0
    verifiedDoctors: int = 0
    pendingDoctorApprovals: int = 0
    totalAppointments: int = 0
    completedAppointments: int = 0
    cancelledAppointments: int = 0
    confirmedAppointments: int = 0
    pendingAppointments: int = 0
    rejectedDoctorApplications: int = 0
    activeApprovedDoctors: int = Field(0, description="Approved doctors whose account is ACTIVE (bookable)")
    suspendedDoctors: int = 0


class PaymentRevenueBreakdownSchema(BaseModel):
    """Payment transaction counts and revenue map per currency."""
    totalRevenueByCurrency: Dict[str, float] = Field(
        default_factory=dict, description="Kept for compatibility: net collections per currency (not profit)")
    netCollectedByCurrency: Dict[str, float] = Field(default_factory=dict)
    capturedByCurrency: Dict[str, float] = Field(default_factory=dict)
    refundedByCurrency: Dict[str, float] = Field(default_factory=dict)
    pendingRefundsByCurrency: Dict[str, float] = Field(default_factory=dict)
    pendingRefundRequests: int = 0
    succeededTransactions: int = 0
    refundedTransactions: int = 0
    failedTransactions: int = 0
    pendingTransactions: int = 0
    paymentSuccessRate: Optional[float] = Field(None, description="None when no payment was attempted")
    platformRevenue: Optional[float] = Field(None, description="Not calculated: no platform fee model is configured")
    note: Optional[str] = None


class RecentActivityItemSchema(BaseModel):
    """Platform audit action record."""
    type: str
    description: str
    timestamp: datetime
    actorId: Optional[str] = None


class AnalyticsOverviewResponse(BaseModel):
    """High-level platform overview metrics."""
    # Flat overview properties (for backwards-compatibility & direct access)
    totalUsers: int = 0
    totalPatients: int = 0
    totalDoctors: int = 0
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
    timezone: str = "Asia/Colombo"
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Structured nested fields expected by admin-web
    totals: Optional[OverviewTotalsSchema] = None
    payments: Optional[PaymentRevenueBreakdownSchema] = None
    recentActivity: List[RecentActivityItemSchema] = Field(default_factory=list)


class AppointmentAnalyticsResponse(BaseModel):
    """Appointment detailed analytics and trends."""
    totalAppointments: int = 0
    statusBreakdown: Dict[str, int] = Field(default_factory=dict)
    trends: List[TrendDataPoint] = Field(default_factory=list)
    completionRate: float = Field(0.0, description="Percentage of completed vs non-cancelled")
    cancellationRate: float = Field(0.0, description="Percentage of cancelled vs total")
    startDate: Optional[str] = None
    endDate: Optional[str] = None

    # Admin Web Compatibility fields
    totalBookings: int = 0
    completedBookings: int = 0
    cancelledBookings: int = 0
    completionRatePercent: float = 0.0
    dailyTrends: List[Dict[str, Any]] = Field(default_factory=list)


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

    # Admin Web Compatibility fields
    totalTransactions: int = 0
    succeededCount: int = 0
    failedCount: int = 0
    pendingCount: int = 0
    cancelledCount: int = 0
    paymentSuccessRate: Optional[float] = None
    platformRevenue: Optional[float] = None
    note: Optional[str] = None
    timezone: str = "Asia/Colombo"
    dailyTrends: List[Dict[str, Any]] = Field(default_factory=list)


class DoctorAnalyticsResponse(BaseModel):
    """Doctor verification and specialty distribution analytics."""
    totalDoctors: int = 0
    approvedDoctors: int = 0
    pendingDoctors: int = 0
    rejectedDoctors: int = 0
    specialtyDistribution: List[SpecialtyCountItem] = Field(default_factory=list)
    averageExperienceYears: Optional[float] = None
    averageConsultationFee: Optional[float] = None


class ContentAnalyticsResponse(BaseModel):
    """Content publishing and bookmark engagement statistics."""
    totalArticles: int = 0
    publishedArticles: int = 0
    draftArticles: int = 0
    archivedArticles: int = 0
    categoryDistribution: List[CategoryAnalyticsItem] = Field(default_factory=list)
    totalBookmarks: int = 0
    topBookmarkedArticles: List[TopContentItem] = Field(default_factory=list)
