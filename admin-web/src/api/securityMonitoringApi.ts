import { apiClient } from './client';

export interface DependencyHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'unavailable' | 'not_configured' | 'configured_not_verified' | 'disabled' | 'unknown';
  latencyMs?: number;
  message?: string;
}

export interface WorkerHeartbeat {
  workerName: string;
  status: 'active' | 'stale' | 'error' | 'not_reported';
  lastHeartbeat: string | null;
  lastDurationSeconds: number | null;
  pendingJobCount: number | null;
  failedJobCount: number | null;
  lastError?: string | null;
  lastSuccessAt?: string | null;
}

export interface PlatformHealthResponse {
  status: 'healthy' | 'degraded' | 'critical';
  uptimeSeconds: number;
  timestamp: string;
  dependencies: DependencyHealth[];
  workers: WorkerHeartbeat[];
  activeIncidentsCount: number;
  openFraudAssessmentsCount: number;
}

export interface FraudAssessment {
  assessmentId: string;
  relatedAccountId?: string;
  relatedEntityReference: string;
  riskScore: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  triggeredRules: string[];
  supportingEventReferences: string[];
  explanation: string;
  reviewStatus: 'DETECTED' | 'AWAITING_REVIEW' | 'INVESTIGATING' | 'DISMISSED' | 'CONFIRMED' | 'RESOLVED';
  investigationNotes: Array<Record<string, unknown>>;
  assignedAdminId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface OperationalIncident {
  incidentId: string;
  title: string;
  category: string;
  severity: 'INFORMATIONAL' | 'WARNING' | 'HIGH' | 'CRITICAL';
  status: 'OPEN' | 'ACKNOWLEDGED' | 'INVESTIGATING' | 'MITIGATED' | 'RESOLVED';
  description: string;
  affectedService: string;
  supportingEventReferences: string[];
  assignedAdminId?: string;
  resolutionNotes?: string;
  createdAt: string;
  acknowledgedAt?: string;
  resolvedAt?: string;
}

export interface IncidentAiSummaryResponse {
  incidentId: string;
  title: string;
  category?: string;
  severity: string;
  affectedService?: string;
  summary: string;
  recommendedAction?: string;
  suggestedInvestigationSteps?: string[];
  generatedAt?: string;
}

export interface SecurityEvent {
  eventId: string;
  category: string;
  severity: string;
  actorId?: string;
  actorRole?: string;
  ipAddress?: string;
  endpoint?: string;
  description: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface NotificationMetrics {
  timestamp: string;
  byChannel: Array<{
    channel: string;
    pending: number;
    delivered: number;
    failed: number;
    retryScheduled: number;
    deadLettered: number;
    skipped?: number;
    uncertain?: number;
    total: number;
    providerStatus?: string | null;
    statusCounts?: Record<string, number>;
  }>;
  totalBacklog: number;
  /** null when nothing was attempted. */
  failureRatePercent: number | null;
  notes?: string[];
  inAppStored?: number;
  inAppUnread?: number;
  deadLetterQueueCount: number;
}

export interface DeadLetterItem {
  deadLetterId: string;
  appointmentId?: string;
  recipientUserId: string;
  channel: string;
  reason: string;
  retryCount: number;
  status: string;
  createdAt: string;
}

export interface MonitoredWorkflow {
  workflowId: string;
  workflowType: string;
  status: string;
  relatedEntityId: string;
  retryCount: number;
  maxRetries: number;
  errorCategory?: string;
  errorMessage?: string;
  startedAt: string;
  lastUpdatedAt: string;
  completedAt?: string;
  metadata: Record<string, unknown>;
}

export interface AIProviderMetric {
  provider: string;
  status: string;
  circuitBreakerState: string;
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageLatencyMs: number;
  fallbackActivations: number;
  lastError?: string;
  lastErrorTimestamp?: string;
}

export interface DeadLetterRetryResponse {
  success: boolean;
  message: string;
  deadLetterId: string;
}

export interface WorkflowRecoveryResponse {
  workflowId: string;
  recovered: boolean;
  message: string;
  currentStatus?: string;
}

export interface MonitoringAssistantChatResponse {
  intent: string;
  response: string;
  confidence: number;
  actionRecommended?: string;
}

export const securityMonitoringApi = {
  // Platform & Worker Health
  getPlatformHealth: async (): Promise<PlatformHealthResponse> => {
    const res = await apiClient.get<PlatformHealthResponse>('/security/monitoring/platform');
    return res.data;
  },

  // Fraud Management
  getFraudAssessments: async (statusFilter?: string, riskLevel?: string): Promise<{ items: FraudAssessment[]; total: number }> => {
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (riskLevel) params.riskLevel = riskLevel;
    const res = await apiClient.get<{ items: FraudAssessment[]; total: number }>('/security/fraud/assessments', { params });
    return res.data;
  },

  reviewFraudAssessment: async (assessmentId: string, decision: string, notes: string): Promise<FraudAssessment> => {
    const res = await apiClient.post<FraudAssessment>(`/security/fraud/assessments/${assessmentId}/review`, { decision, notes });
    return res.data;
  },

  // Operational Incidents
  getIncidents: async (statusFilter?: string, category?: string): Promise<{ items: OperationalIncident[]; total: number }> => {
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (category) params.category = category;
    const res = await apiClient.get<{ items: OperationalIncident[]; total: number }>('/security/incidents', { params });
    return res.data;
  },

  createIncident: async (data: { title: string; category: string; severity: string; description: string; affectedService: string }): Promise<OperationalIncident> => {
    const res = await apiClient.post<OperationalIncident>('/security/incidents', data);
    return res.data;
  },

  acknowledgeIncident: async (incidentId: string): Promise<OperationalIncident> => {
    const res = await apiClient.post<OperationalIncident>(`/security/incidents/${incidentId}/acknowledge`);
    return res.data;
  },

  resolveIncident: async (incidentId: string, notes: string): Promise<OperationalIncident> => {
    const res = await apiClient.post<OperationalIncident>(`/security/incidents/${incidentId}/resolve`, null, { params: { notes } });
    return res.data;
  },

  getIncidentAiSummary: async (incidentId: string): Promise<IncidentAiSummaryResponse> => {
    const res = await apiClient.get<IncidentAiSummaryResponse>(`/security/incidents/${incidentId}/ai-summary`);
    return res.data;
  },

  // Security Events
  getSecurityEvents: async (category?: string, severity?: string): Promise<{ items: SecurityEvent[]; total: number }> => {
    const params: Record<string, string> = {};
    if (category) params.category = category;
    if (severity) params.severity = severity;
    const res = await apiClient.get<{ items: SecurityEvent[]; total: number }>('/security/events', { params });
    return res.data;
  },

  // Notification Monitoring
  getNotificationMetrics: async (): Promise<NotificationMetrics> => {
    const res = await apiClient.get<NotificationMetrics>('/security/monitoring/notifications');
    return res.data;
  },

  getDeadLetters: async (): Promise<DeadLetterItem[]> => {
    const res = await apiClient.get<DeadLetterItem[]>('/security/monitoring/notifications/dead-letters');
    return res.data;
  },

  retryDeadLetter: async (deadLetterId: string): Promise<DeadLetterRetryResponse> => {
    const res = await apiClient.post<DeadLetterRetryResponse>(`/security/monitoring/notifications/dead-letters/${deadLetterId}/retry`);
    return res.data;
  },

  // Workflows
  getMonitoredWorkflows: async (statusFilter?: string): Promise<MonitoredWorkflow[]> => {
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    const res = await apiClient.get<MonitoredWorkflow[]>('/security/monitoring/workflows', { params });
    return res.data;
  },

  detectStuckWorkflows: async (): Promise<MonitoredWorkflow[]> => {
    const res = await apiClient.post<MonitoredWorkflow[]>('/security/monitoring/workflows/stuck');
    return res.data;
  },

  recoverWorkflow: async (workflowId: string, recoveryReason: string): Promise<WorkflowRecoveryResponse> => {
    const res = await apiClient.post<WorkflowRecoveryResponse>(`/security/monitoring/workflows/${workflowId}/recover`, {
      workflowId,
      recoveryReason,
      force: true,
    });
    return res.data;
  },

  // AI Providers
  getAiProviderMetrics: async (): Promise<AIProviderMetric[]> => {
    const res = await apiClient.get<AIProviderMetric[]>('/security/monitoring/ai-providers');
    return res.data;
  },

  // Admin AI Chat
  chatMonitoringAssistant: async (message: string): Promise<MonitoringAssistantChatResponse> => {
    const res = await apiClient.post<MonitoringAssistantChatResponse>('/security/ai-assistant/chat', { message });
    return res.data;
  },
};
