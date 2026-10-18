import { apiClient } from './client';
import { DoctorListResponse } from '../types/doctor';

export const doctorsApi = {
  listDoctors: async (params: {
    specialty?: string;
    status?: string;
    search?: string;
    page?: number;
    pageSize?: number;
  }): Promise<DoctorListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.specialty) searchParams.append('specialty', params.specialty);
    if (params.status) searchParams.append('status', params.status);
    if (params.search) searchParams.append('search', params.search);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.pageSize) searchParams.append('pageSize', params.pageSize.toString());

    const response = await apiClient.get<DoctorListResponse>(`/admin/doctors?${searchParams.toString()}`);
    return response.data;
  },
};
