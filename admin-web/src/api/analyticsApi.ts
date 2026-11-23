import { apiClient } from './client';
import { AnalyticsOverview, AppointmentAnalytics, PaymentAnalytics } from '../types/analytics';

export const analyticsApi = {
  getOverview: async (startDate?: string, endDate?: string): Promise<AnalyticsOverview> => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    const response = await apiClient.get<AnalyticsOverview>(`/admin/analytics/overview?${params.toString()}`);
    return response.data;
  },

  getAppointments: async (startDate?: string, endDate?: string): Promise<AppointmentAnalytics> => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    const response = await apiClient.get<AppointmentAnalytics>(`/admin/analytics/appointments?${params.toString()}`);
    return response.data;
  },

  getPayments: async (startDate?: string, endDate?: string): Promise<PaymentAnalytics> => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    const response = await apiClient.get<PaymentAnalytics>(`/admin/analytics/payments?${params.toString()}`);
    return response.data;
  },
};
