import { apiClient } from './client';
import { UserListResponse } from '../types/user';

export const usersApi = {
  listUsers: async (params: {
    role?: string;
    status?: string;
    search?: string;
    page?: number;
    pageSize?: number;
  }): Promise<UserListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.role) searchParams.append('role', params.role);
    if (params.status) searchParams.append('status', params.status);
    if (params.search) searchParams.append('search', params.search);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.pageSize) searchParams.append('pageSize', params.pageSize.toString());

    const response = await apiClient.get<UserListResponse>(`/admin/users?${searchParams.toString()}`);
    return response.data;
  },

  updateUserStatus: async (userId: string, accountStatus: string): Promise<{ message: string }> => {
    const response = await apiClient.patch<{ message: string }>(`/admin/users/${userId}/status`, {
      accountStatus,
    });
    return response.data;
  },
};
