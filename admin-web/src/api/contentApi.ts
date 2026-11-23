import { apiClient } from './client';
import {
  ContentListResponse,
  CreateArticleRequest,
  HealthArticle,
  UpdateArticleRequest,
} from '../types/content';

export const contentApi = {
  listArticles: async (params: {
    status?: string;
    category?: string;
    search?: string;
    page?: number;
    pageSize?: number;
  }): Promise<ContentListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.append('status', params.status);
    if (params.category) searchParams.append('category', params.category);
    if (params.search) searchParams.append('search', params.search);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.pageSize) searchParams.append('pageSize', params.pageSize.toString());

    const response = await apiClient.get<ContentListResponse>(`/admin/content?${searchParams.toString()}`);
    return response.data;
  },

  getArticle: async (identifier: string): Promise<HealthArticle> => {
    const response = await apiClient.get<HealthArticle>(`/admin/content/${identifier}`);
    return response.data;
  },

  createArticle: async (data: CreateArticleRequest): Promise<HealthArticle> => {
    const response = await apiClient.post<HealthArticle>('/admin/content', data);
    return response.data;
  },

  updateArticle: async (identifier: string, data: UpdateArticleRequest): Promise<HealthArticle> => {
    const response = await apiClient.patch<HealthArticle>(`/admin/content/${identifier}`, data);
    return response.data;
  },

  publishArticle: async (identifier: string): Promise<HealthArticle> => {
    const response = await apiClient.post<HealthArticle>(`/admin/content/${identifier}/publish`);
    return response.data;
  },

  archiveArticle: async (identifier: string): Promise<HealthArticle> => {
    const response = await apiClient.post<HealthArticle>(`/admin/content/${identifier}/archive`);
    return response.data;
  },
};
