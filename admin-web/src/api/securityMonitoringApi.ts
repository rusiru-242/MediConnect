import { apiClient } from './client';

export interface DependencyHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'unavailable' | 'unconfigured';
  latencyMs?: number;
  message?: string;
}

export interface WorkerHeartbeat {
  workerName: string;
  status: 'active' | 'stale' | 'stopped';
  lastHeartbeat: string;
  lastDurationSeconds: number;
  pendingJobCount: number;
  failedJobCount: number;
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
  investigationNotes: any[];
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

export interface SecurityEvent {
  eventId: string;
  category: string;
  severity: string;
  actorId?: string;
  actorRole?: string;
  ipAddress?: string;
  endpoint?: string;
  description: string;
  metadata: Record<string, any>;
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
    total: number;
  }>;
  totalBacklog: number;
  failureRatePercent: number;
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
  metadata: Record<string, any>;
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

export const securityMonitoringApi = {
  // Platform & Worker Health
  getPlatformHealth: async (): Promise<PlatformHealthResponse> => {
    const res = await apiClient.get<PlatformHealthResponse>('/security/monitoring/platform');
    return res.data;
  },

  // Fraud Management
  getFraudAssessments: async (statusFilter?: string, riskLevel?: string): Promise<{ items: FraudAssessment[]; total: number }> => {
    const params: any = {};
    if (statusFilter) params.status = statusFilter;
    if (riskLevel) params.riskLevel = riskLevel;
    const res = await apiClient.get('/security/fraud/assessments', { params });
    return res.data;
  },

  reviewFraudAssessment: async (assessmentId: string, decision: string, notes: string): Promise<FraudAssessment> => {
    const res = await apiClient.post(`/security/fraud/assessments/${assessmentId}/review`, { decision, notes });
    return res.data;
  },

  // Operational Incidents
  getIncidents: async (statusFilter?: string, category?: string): Promise<{ items: OperationalIncident[]; total: number }> => {
    const params: any = {};
    if (statusFilter) params.status = statusFilter;
    if (category) params.category = category;
    const res = await apiClient.get('/security/incidents', { params });
    return res.data;
  },

  createIncident: async (data: { title: string; category: string; severity: string; description: string; affectedService: string }): Promise<OperationalIncident> => {
    const res = await apiClient.post('/security/incidents', data);
    return res.data;
  },

  acknowledgeIncident: async (incidentId: string): Promise<OperationalIncident> => {
    const res = await apiClient.post(`/security/incidents/${incidentId}/acknowledge`);
    return res.data;
  },

  resolveIncident: async (incidentId: string, notes: string): Promise<OperationalIncident> => {
    const res = await apiClient.post(`/security/incidents/${incidentId}/resolve`, null, { params: { notes } });
    return res.data;
  },

  getIncidentAiSummary: async (incidentId: string): Promise<any> => {
    const res = await apiClient.get(`/security/incidents/${incidentId}/ai-summary`);
    return res.data;
  },

  // Security Events
  getSecurityEvents: async (category?: string, severity?: string): Promise<{ items: SecurityEvent[]; total: number }> => {
    const params: any = {};
    if (category) params.category = category;
    if (severity) params.severity = severity;
    const res = await apiClient.get('/security/events', { params });
    return res.data;
  },

  // Notification Monitoring
  getNotificationMetrics: async (): Promise<NotificationMetrics> => {
    const res = await apiClient.get('/security/monitoring/notifications');
    return res.data;
  },

  getDeadLetters: async (): Promise<DeadLetterItem[]> => {
    const res = await apiClient.get('/security/monitoring/notifications/dead-letters');
    return res.data;
  },

  retryDeadLetter: async (deadLetterId: string): Promise<any> => {
    const res = await apiClient.post(`/security/monitoring/notifications/dead-letters/${deadLetterId}/retry`);
    return res.data;
  },

  // Workflows
  getMonitoredWorkflows: async (statusFilter?: string): Promise<MonitoredWorkflow[]> => {
    const params: any = {};
    if (statusFilter) params.status = statusFilter;
    const res = await apiClient.get('/security/monitoring/workflows', { params });
    return res.data;
  },

  detectStuckWorkflows: async (): Promise<MonitoredWorkflow[]> => {
    const res = await apiClient.post('/security/monitoring/workflows/stuck');
    return res.data;
  },

  recoverWorkflow: async (workflowId: string, recoveryReason: string): Promise<any> => {
    const res = await apiClient.post(`/security/monitoring/workflows/${workflowId}/recover`, {
      workflowId,
      recoveryReason,
      force: true,
    });
    return res.data;
  },

  // AI Providers
  getAiProviderMetrics: async (): Promise<AIProviderMetric[]> => {
    const res = await apiClient.get('/security/monitoring/ai-providers');
    return res.data;
  },

  // Admin AI Chat
  chatMonitoringAssistant: async (message: string): Promise<any> => {
    const res = await apiClient.post('/security/ai-assistant/chat', { message });
    return res.data;
  },
};
