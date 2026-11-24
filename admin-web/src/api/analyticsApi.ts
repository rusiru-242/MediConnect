import { apiClient } from './client';
import { AnalyticsOverview, AppointmentAnalytics, PaymentAnalytics, CurrencyRevenueItem } from '../types/analytics';

interface RawOverviewTotals {
  totalUsers?: number;
  totalPatients?: number;
  totalDoctors?: number;
  verifiedDoctors?: number;
  pendingDoctorApprovals?: number;
  totalAppointments?: number;
  completedAppointments?: number;
  cancelledAppointments?: number;
}

interface RawOverviewResponse {
  totals?: RawOverviewTotals;
  totalPatients?: number;
  totalVerifiedDoctors?: number;
  pendingDoctorApprovals?: number;
  totalDoctors?: number;
  totalUsers?: number;
  totalAppointments?: number;
  completedAppointments?: number;
  cancelledAppointments?: number;
  payments?: {
    totalRevenueByCurrency?: Record<string, number>;
    succeededTransactions?: number;
    failedTransactions?: number;
    pendingTransactions?: number;
  };
  successfulPaymentsCount?: number;
  failedPaymentsCount?: number;
  totalRevenueByCurrency?: Array<{
    currency?: string;
    netAmount?: number;
    grossAmount?: number;
  }>;
  generatedAt?: string;
  recentActivity?: AnalyticsOverview['recentActivity'];
}

interface RawAppointmentTrend {
  date: string;
  total?: number;
  count?: number;
}

interface RawAppointmentResponse {
  totalBookings?: number;
  totalAppointments?: number;
  completedBookings?: number;
  completedAppointments?: number;
  cancelledBookings?: number;
  cancelledAppointments?: number;
  completionRatePercent?: number;
  completionRate?: number;
  statusBreakdown?: Record<string, number>;
  dailyTrends?: Array<{ date: string; count: number }>;
  trends?: RawAppointmentTrend[];
}

interface RawPaymentCurrencyItem {
  currency?: string;
  netAmount?: number;
  totalAmount?: number;
  grossAmount?: number;
  paymentCount?: number;
  transactionCount?: number;
}

interface RawPaymentResponse {
  totalTransactions?: number;
  succeededCount?: number;
  successfulPaymentsCount?: number;
  failedCount?: number;
  failedPaymentsCount?: number;
  revenueByCurrency?: RawPaymentCurrencyItem[];
  dailyTrends?: PaymentAnalytics['dailyTrends'];
}

export const analyticsApi = {
  getOverview: async (startDate?: string, endDate?: string): Promise<AnalyticsOverview> => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    const response = await apiClient.get<RawOverviewResponse>(`/admin/analytics/overview?${params.toString()}`);
    const data = response.data || {};

    const rawTotals = data.totals || {};
    const totalPatients = rawTotals.totalPatients ?? data.totalPatients ?? 0;
    const verifiedDoctors = rawTotals.verifiedDoctors ?? data.totalVerifiedDoctors ?? 0;
    const pendingDoctorApprovals = rawTotals.pendingDoctorApprovals ?? data.pendingDoctorApprovals ?? 0;
    const totalDoctors = rawTotals.totalDoctors ?? data.totalDoctors ?? (verifiedDoctors + pendingDoctorApprovals);
    const totalUsers = rawTotals.totalUsers ?? data.totalUsers ?? (totalPatients + totalDoctors);
    const totalAppointments = rawTotals.totalAppointments ?? data.totalAppointments ?? 0;
    const completedAppointments = rawTotals.completedAppointments ?? data.completedAppointments ?? 0;
    const cancelledAppointments = rawTotals.cancelledAppointments ?? data.cancelledAppointments ?? 0;

    let revMap: Record<string, number> = {};
    if (
      data.payments?.totalRevenueByCurrency &&
      typeof data.payments.totalRevenueByCurrency === 'object' &&
      !Array.isArray(data.payments.totalRevenueByCurrency)
    ) {
      revMap = data.payments.totalRevenueByCurrency;
    } else if (Array.isArray(data.totalRevenueByCurrency)) {
      for (const item of data.totalRevenueByCurrency) {
        if (item.currency) {
          revMap[item.currency.toUpperCase()] = item.netAmount ?? item.grossAmount ?? 0;
        }
      }
    }

    return {
      generatedAt: data.generatedAt || new Date().toISOString(),
      totals: {
        totalUsers,
        totalPatients,
        totalDoctors,
        verifiedDoctors,
        pendingDoctorApprovals,
        totalAppointments,
        completedAppointments,
        cancelledAppointments,
      },
      payments: {
        totalRevenueByCurrency: revMap,
        succeededTransactions: data.payments?.succeededTransactions ?? data.successfulPaymentsCount ?? 0,
        failedTransactions: data.payments?.failedTransactions ?? data.failedPaymentsCount ?? 0,
        pendingTransactions: data.payments?.pendingTransactions ?? 0,
      },
      recentActivity: data.recentActivity || [],
    };
  },

  getAppointments: async (startDate?: string, endDate?: string): Promise<AppointmentAnalytics> => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    const response = await apiClient.get<RawAppointmentResponse>(`/admin/analytics/appointments?${params.toString()}`);
    const data = response.data || {};

    const dailyTrends = data.dailyTrends ?? (Array.isArray(data.trends) ? data.trends.map((t: RawAppointmentTrend) => ({
      date: t.date,
      count: t.total ?? t.count ?? 0,
    })) : []);

    return {
      totalBookings: data.totalBookings ?? data.totalAppointments ?? 0,
      completedBookings: data.completedBookings ?? data.completedAppointments ?? 0,
      cancelledBookings: data.cancelledBookings ?? data.cancelledAppointments ?? 0,
      completionRatePercent: data.completionRatePercent ?? data.completionRate ?? 0,
      statusBreakdown: data.statusBreakdown || {},
      dailyTrends,
    };
  },

  getPayments: async (startDate?: string, endDate?: string): Promise<PaymentAnalytics> => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    const response = await apiClient.get<RawPaymentResponse>(`/admin/analytics/payments?${params.toString()}`);
    const data = response.data || {};

    let revList: CurrencyRevenueItem[] = [];
    if (Array.isArray(data.revenueByCurrency)) {
      revList = data.revenueByCurrency.map((c: RawPaymentCurrencyItem) => ({
        currency: (c.currency || 'lkr').toUpperCase(),
        totalAmount: c.netAmount ?? c.totalAmount ?? c.grossAmount ?? 0,
        transactionCount: c.paymentCount ?? c.transactionCount ?? 0,
      }));
    }

    return {
      totalTransactions: data.totalTransactions ?? ((data.successfulPaymentsCount ?? 0) + (data.failedPaymentsCount ?? 0)),
      succeededCount: data.succeededCount ?? data.successfulPaymentsCount ?? 0,
      failedCount: data.failedCount ?? data.failedPaymentsCount ?? 0,
      revenueByCurrency: revList,
      dailyTrends: data.dailyTrends || [],
    };
  },
};
