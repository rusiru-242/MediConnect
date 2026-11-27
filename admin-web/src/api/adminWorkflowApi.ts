/**
 * API client for Admin AI Automation, Verification, Analytics & Payment Operations (Phase 5).
 */

import { apiClient } from './client';
import {
  AdminAssistantChatResponse,
  AdminAuditLogListResponse,
  AdminReportResponse,
  AIDraftSupportResponse,
  DoctorVerificationAIDecision,
  ReconciliationReport,
  RefundRequest,
  RefundRequestListResponse,
  SupportTicket,
  SupportTicketListResponse,
} from '../types/adminWorkflow';

export const adminWorkflowApi = {
  // 1. Doctor Verification Assistant
  getDoctorAIReview: async (profileId: string): Promise<DoctorVerificationAIDecision> => {
    const { data } = await apiClient.get<DoctorVerificationAIDecision>(
      `/admin/workflow/doctor-verification/${profileId}/ai-review`
    );
    return data;
  },

  // 2. Payment Reconciliation
  runReconciliation: async (): Promise<ReconciliationReport> => {
    const { data } = await apiClient.post<ReconciliationReport>('/admin/workflow/reconciliation/run');
    return data;
  },

  getReconciliationIssues: async (): Promise<ReconciliationReport> => {
    const { data } = await apiClient.get<ReconciliationReport>('/admin/workflow/reconciliation/issues');
    return data;
  },

  // 3. Customer Support Ticketing
  listTickets: async (params?: {
    status?: string;
    category?: string;
    priority?: string;
    page?: number;
    pageSize?: number;
  }): Promise<SupportTicketListResponse> => {
    const { data } = await apiClient.get<SupportTicketListResponse>('/admin/workflow/tickets', { params });
    return data;
  },

  getTicket: async (ticketId: string): Promise<SupportTicket> => {
    const { data } = await apiClient.get<SupportTicket>(`/admin/workflow/tickets/${ticketId}`);
    return data;
  },

  generateTicketDraft: async (ticketId: string): Promise<AIDraftSupportResponse> => {
    const { data } = await apiClient.post<AIDraftSupportResponse>(
      `/admin/workflow/tickets/${ticketId}/ai-draft`
    );
    return data;
  },

  replyTicket: async (
    ticketId: string,
    message: string,
    status?: string,
    resolve?: boolean
  ): Promise<{ message: string; ticketId: string; status: string; duplicate?: boolean }> => {
    const { data } = await apiClient.post(`/admin/workflow/tickets/${ticketId}/reply`, {
      message,
      status,
      resolve,
    });
    return data;
  },

  // 4. Refund Review & Execution
  listRefunds: async (params?: {
    status?: string;
    source?: string;
    page?: number;
    pageSize?: number;
  }): Promise<RefundRequestListResponse> => {
    const { data } = await apiClient.get<RefundRequestListResponse>('/admin/workflow/refunds', { params });
    return data;
  },

  getRefund: async (refundId: string): Promise<RefundRequest> => {
    const { data } = await apiClient.get<RefundRequest>(`/admin/workflow/refunds/${refundId}`);
    return data;
  },

  approveRefund: async (
    refundId: string,
    approvedAmount?: number,
    notes?: string
  ): Promise<{ message: string; refundId: string; status: string; stripeRefundId?: string }> => {
    const { data } = await apiClient.post(`/admin/workflow/refunds/${refundId}/approve`, {
      approvedAmount,
      notes,
    });
    return data;
  },

  rejectRefund: async (
    refundId: string,
    reason: string
  ): Promise<{ message: string; refundId: string; status: string }> => {
    const { data } = await apiClient.post(`/admin/workflow/refunds/${refundId}/reject`, {
      reason,
    });
    return data;
  },

  // 5. Operational Reports & CSV
  generateReport: async (
    reportType: string,
    startDate?: string,
    endDate?: string
  ): Promise<AdminReportResponse> => {
    const { data } = await apiClient.post<AdminReportResponse>('/admin/workflow/reports/generate', {
      reportType,
      startDate,
      endDate,
    });
    return data;
  },

  exportReportCsv: async (reportType: string, startDate?: string, endDate?: string): Promise<Blob> => {
    const response = await apiClient.post(
      '/admin/workflow/reports/export-csv',
      { reportType, startDate, endDate },
      { responseType: 'blob' }
    );
    return response.data;
  },

  // 6. Admin Conversational AI Assistant
  askAssistant: async (message: string, contextFilter?: Record<string, unknown>): Promise<AdminAssistantChatResponse> => {
    const { data } = await apiClient.post<AdminAssistantChatResponse>('/admin/workflow/assistant', {
      message,
      contextFilter,
    });
    return data;
  },

  // 7. Audit Logs
  listAuditLogs: async (params?: {
    actionType?: string;
    targetType?: string;
    actorId?: string;
    startDate?: string;
    endDate?: string;
    page?: number;
    pageSize?: number;
  }): Promise<AdminAuditLogListResponse> => {
    const { data } = await apiClient.get<AdminAuditLogListResponse>('/admin/workflow/audit-logs', { params });
    return data;
  },
};
