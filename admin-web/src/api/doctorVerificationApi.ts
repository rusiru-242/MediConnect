import { apiClient } from './client';
import { DoctorApplicationSummary, DoctorApplicationDetail } from '../types/doctor';

export const doctorVerificationApi = {
  listApplications: async (status: string = 'PENDING'): Promise<DoctorApplicationSummary[]> => {
    const response = await apiClient.get<DoctorApplicationSummary[]>(`/admin/doctors/applications?status=${status}`);
    return response.data;
  },

  getApplicationDetail: async (doctorProfileId: string): Promise<DoctorApplicationDetail> => {
    const response = await apiClient.get<DoctorApplicationDetail>(`/admin/doctors/applications/${doctorProfileId}`);
    return response.data;
  },

  approveApplication: async (doctorProfileId: string): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(`/admin/doctors/${doctorProfileId}/approve`);
    return response.data;
  },

  rejectApplication: async (doctorProfileId: string, reason: string): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(`/admin/doctors/${doctorProfileId}/reject`, { reason });
    return response.data;
  },

  getDocumentUrl: (doctorProfileId: string, documentKey: string): string => {
    const base = apiClient.defaults.baseURL || 'http://localhost:8000/api';
    return `${base}/admin/doctors/applications/${doctorProfileId}/documents/${documentKey}`;
  },

  downloadDocument: async (doctorProfileId: string, documentKey: string, filename: string): Promise<void> => {
    const response = await apiClient.get(`/admin/doctors/applications/${doctorProfileId}/documents/${documentKey}`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data]);
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },
};
