import { apiClient } from './client';
import { AdminUser, LoginResponse } from '../types/auth';

export const authApi = {
  login: async (email: string, password: string): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/auth/login', {
      email,
      password,
    });
    return response.data;
  },

  getCurrentUser: async (): Promise<AdminUser> => {
    const response = await apiClient.get<AdminUser>('/auth/me');
    return response.data;
  },

  checkHealth: async (): Promise<{ status: string; service: string }> => {
    // Health check endpoint on backend
    const response = await apiClient.get<{ status: string; service: string }>('/health');
    return response.data;
  },
};
