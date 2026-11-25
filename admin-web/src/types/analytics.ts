export interface OverviewTotals {
  totalUsers: number;
  totalPatients: number;
  totalDoctors: number;
  verifiedDoctors: number;
  pendingDoctorApprovals: number;
  totalAppointments: number;
  completedAppointments: number;
  cancelledAppointments: number;
  confirmedAppointments?: number;
  pendingAppointments?: number;
  rejectedDoctorApplications?: number;
  /** Approved doctors whose account is ACTIVE (bookable). */
  activeApprovedDoctors?: number;
  suspendedDoctors?: number;
}

export interface PaymentRevenueBreakdown {
  /** Kept for compatibility: net collections per currency (captured minus refunded). Not profit. */
  totalRevenueByCurrency: Record<string, number>;
  netCollectedByCurrency?: Record<string, number>;
  capturedByCurrency?: Record<string, number>;
  refundedByCurrency?: Record<string, number>;
  pendingRefundsByCurrency?: Record<string, number>;
  pendingRefundRequests?: number;
  succeededTransactions: number;
  refundedTransactions?: number;
  failedTransactions: number;
  pendingTransactions: number;
  paymentSuccessRate?: number | null;
  /** Always null: no platform fee model is configured. */
  platformRevenue?: number | null;
  note?: string | null;
}

export interface RecentActivityItem {
  type: string;
  description: string;
  timestamp: string;
  actorId?: string;
}

export interface AnalyticsOverview {
  generatedAt: string;
  timezone?: string;
  totals: OverviewTotals;
  payments: PaymentRevenueBreakdown;
  recentActivity: RecentActivityItem[];
}

export interface DailyTrendItem {
  date: string;
  count: number;
}

export interface AppointmentAnalytics {
  totalBookings: number;
  completedBookings: number;
  cancelledBookings: number;
  completionRatePercent: number;
  statusBreakdown: Record<string, number>;
  dailyTrends: DailyTrendItem[];
}

export interface CurrencyRevenueItem {
  currency: string;
  /** Gross collections (captured payments, including later refunded ones). */
  grossAmount: number;
  refundedAmount: number;
  /** Net collections (gross - refunded). Not platform profit. */
  netAmount: number;
  paymentCount: number;
  pendingRefundAmount?: number;
  pendingRefundCount?: number;
}

export interface PaymentAnalytics {
  totalTransactions: number;
  succeededCount: number;
  failedCount: number;
  revenueByCurrency: CurrencyRevenueItem[];
  dailyTrends: DailyTrendItem[];
  paymentSuccessRate?: number | null;
  platformRevenue?: number | null;
  note?: string | null;
}
