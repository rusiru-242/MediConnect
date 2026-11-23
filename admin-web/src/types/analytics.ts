export interface OverviewTotals {
  totalUsers: number;
  totalPatients: number;
  totalDoctors: number;
  verifiedDoctors: number;
  pendingDoctorApprovals: number;
  totalAppointments: number;
  completedAppointments: number;
  cancelledAppointments: number;
}

export interface PaymentRevenueBreakdown {
  totalRevenueByCurrency: Record<string, number>;
  succeededTransactions: number;
  failedTransactions: number;
  pendingTransactions: number;
}

export interface RecentActivityItem {
  type: string;
  description: string;
  timestamp: string;
  actorId?: string;
}

export interface AnalyticsOverview {
  generatedAt: string;
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
  totalAmount: number;
  transactionCount: number;
}

export interface PaymentAnalytics {
  totalTransactions: number;
  succeededCount: number;
  failedCount: number;
  revenueByCurrency: CurrencyRevenueItem[];
  dailyTrends: DailyTrendItem[];
}
