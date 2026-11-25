/**
 * Type definitions for Admin AI Automation, Verification, Analytics & Payment Operations (Phase 5).
 */

export interface DoctorVerificationAIDecision {
  doctorProfileId: string;
  doctorName: string;
  completenessScore: number;
  fieldCompleteness: Record<string, boolean>;
  documentChecklist: Record<string, boolean>;
  missingDocuments: string[];
  inconsistencies: string[];
  riskFlags: string[];
  needsManualExternalCheck: boolean;
  summary: string;
  recommendedAction: 'APPROVE' | 'REJECT' | 'REQUEST_INFO' | 'MANUAL_VERIFY';
}

export interface ReconciliationDiscrepancy {
  discrepancyId: string;
  type: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  paymentId?: string;
  appointmentId?: string;
  stripePaymentIntentId?: string;
  description: string;
  recommendation: string;
  detectedAt: string;
}

export interface ReconciliationReport {
  discrepancies: ReconciliationDiscrepancy[];
  totalChecked: number;
  discrepanciesCount: number;
  checkedAt: string;
}

export interface SupportMessage {
  messageId: string;
  senderId: string;
  senderRole: string;
  senderName?: string;
  message: string;
  sentAt: string;
}

export interface AIDraftSupportResponse {
  ticketId: string;
  suggestedCategory: string;
  suggestedPriority: string;
  issueSummary: string;
  suggestedResolution: string;
  draftResponse: string;
  flags: string[];
}

export interface SupportTicket {
  id: string;
  ticketId: string;
  requesterId: string;
  requesterRole: string;
  requesterEmail: string;
  requesterName: string;
  category: string;
  subject: string;
  description: string;
  status: 'open' | 'in_progress' | 'waiting_for_user' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  assignedAdminId?: string;
  relatedEntityId?: string;
  messages: SupportMessage[];
  aiDraft?: AIDraftSupportResponse;
  createdAt: string;
  updatedAt: string;
  resolvedAt?: string;
}

export interface SupportTicketListResponse {
  items: SupportTicket[];
  total: number;
  page: number;
  pageSize: number;
}

export interface RefundPolicyResult {
  eligible: boolean;
  eligibleAmount: number;
  penaltyAmount: number;
  ruleApplied: string;
  isDisputed: boolean;
  alreadyRefunded: boolean;
}

export interface RefundRequest {
  id: string;
  refundId: string;
  paymentId: string;
  appointmentId: string;
  patientUserId: string;
  patientName: string;
  amount: number;
  currency: string;
  reason: string;
  status: 'requested' | 'under_review' | 'approved' | 'rejected' | 'processing' | 'succeeded' | 'failed';
  policyEligibility?: RefundPolicyResult;
  aiSummary?: {
    summary: string;
    recommendation: string;
    riskFlags: string[];
  };
  stripeRefundId?: string;
  idempotencyKey: string;
  adminReviewerId?: string;
  reviewNotes?: string;
  failureReason?: string;
  /** Why the request exists: patient cancellation, doctor cancellation or doctor leave (null for legacy rows). */
  source?: 'patient' | 'doctor' | 'leave' | 'admin' | null;
  cancelledBy?: string | null;
  cancellationReason?: string | null;
  approvedAmount?: number | null;
  refundedAmount?: number | null;
  stripeRefundStatus?: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

export interface RefundRequestListResponse {
  items: RefundRequest[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AdminReportResponse {
  reportId: string;
  reportType: string;
  title: string;
  dateRange: { startDate: string; endDate: string };
  generatedAt: string;
  dataDefinitions: Record<string, string>;
  metrics: Record<string, unknown>;
  items: Array<Record<string, unknown>>;
  aiSummary?: string;
}

export interface AdminAssistantChatResponse {
  reply: string;
  toolCalled?: string;
  data?: Record<string, unknown>;
  dateRange?: { startDate: string; endDate: string };
  actionSuggestions: string[];
}

export interface AdminAuditLogItem {
  id: string;
  auditId: string;
  actorId: string;
  actorEmail?: string;
  actorRole: string;
  actionType: string;
  targetId: string;
  targetType: string;
  previousState?: string;
  newState?: string;
  reason?: string;
  correlationId?: string;
  status: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface AdminAuditLogListResponse {
  items: AdminAuditLogItem[];
  total: number;
  page: number;
  pageSize: number;
}
