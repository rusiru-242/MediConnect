import { apiClient } from './client';
import { AppointmentListResponse } from '../types/appointment';

export const appointmentsApi = {
  listAppointments: async (params: {
    status?: string;
    paymentStatus?: string;
    search?: string;
    startDate?: string;
    endDate?: string;
    page?: number;
    pageSize?: number;
  }): Promise<AppointmentListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.append('status', params.status);
    if (params.paymentStatus) searchParams.append('paymentStatus', params.paymentStatus);
    if (params.search) searchParams.append('search', params.search);
    if (params.startDate) searchParams.append('startDate', params.startDate);
    if (params.endDate) searchParams.append('endDate', params.endDate);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.pageSize) searchParams.append('pageSize', params.pageSize.toString());

    const response = await apiClient.get<AppointmentListResponse>(`/admin/appointments?${searchParams.toString()}`);
    return response.data;
  },
};
