import { apiClient } from './client';
import { ReportedReviewItem, ReviewListResponse } from '../types/review';

export const reviewsApi = {
  listReportedReviews: async (page: number = 1, pageSize: number = 20): Promise<ReportedReviewItem[]> => {
    const response = await apiClient.get<ReportedReviewItem[]>(
      `/admin/reviews/reported?page=${page}&page_size=${pageSize}`
    );
    return response.data;
  },

  listAllReviews: async (params: {
    status?: string;
    page?: number;
    pageSize?: number;
  }): Promise<ReviewListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.append('status', params.status);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.pageSize) searchParams.append('pageSize', params.pageSize.toString());

    const response = await apiClient.get<ReviewListResponse>(`/admin/reviews?${searchParams.toString()}`);
    return response.data;
  },

  moderateReview: async (
    reviewId: string,
    action: 'HIDE' | 'RESTORE',
    moderationNotes?: string
  ): Promise<{ message: string }> => {
    const response = await apiClient.patch<{ message: string }>(`/reviews/${reviewId}/moderate`, {
      action,
      moderationNotes,
    });
    return response.data;
  },

  deleteReview: async (reviewId: string): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/reviews/${reviewId}`);
    return response.data;
  },
};
