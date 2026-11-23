import { apiClient } from './client';
import { PaymentListResponse } from '../types/payment';

export const paymentsApi = {
  listPayments: async (params: {
    status?: string;
    currency?: string;
    startDate?: string;
    endDate?: string;
    page?: number;
    pageSize?: number;
  }): Promise<PaymentListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.append('status', params.status);
    if (params.currency) searchParams.append('currency', params.currency);
    if (params.startDate) searchParams.append('startDate', params.startDate);
    if (params.endDate) searchParams.append('endDate', params.endDate);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.pageSize) searchParams.append('pageSize', params.pageSize.toString());

    const response = await apiClient.get<PaymentListResponse>(`/admin/payments?${searchParams.toString()}`);
    return response.data;
  },
};
