import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  ShieldAlert,
  Server,
  RefreshCw,
  CheckCircle2,
  Clock,
  Send,
  Cpu,
  Mail,
  RotateCcw,
  Bot,
} from 'lucide-react';
import {
  securityMonitoringApi,
  PlatformHealthResponse,
  FraudAssessment,
  OperationalIncident,
  IncidentAiSummaryResponse,
  AIProviderMetric,
  NotificationMetrics,
  DeadLetterItem,
  MonitoredWorkflow,
} from '../api/securityMonitoringApi';
import { useToast } from '../context/ToastContext';

type MonitoringTab = 'health' | 'fraud' | 'incidents' | 'notifications' | 'ai';

export const MonitoringPage: React.FC = () => {
  const { showToast } = useToast();
  const showSuccess = useCallback((msg: string) => showToast(msg, 'success'), [showToast]);
  const showError = useCallback((msg: string) => showToast(msg, 'error'), [showToast]);
  const [activeTab, setActiveTab] = useState<MonitoringTab>('health');
  const [loading, setLoading] = useState<boolean>(true);

  // Telemetry States
  const [health, setHealth] = useState<PlatformHealthResponse | null>(null);
  const [fraudAssessments, setFraudAssessments] = useState<FraudAssessment[]>([]);
  const [incidents, setIncidents] = useState<OperationalIncident[]>([]);
  const [notificationMetrics, setNotificationMetrics] = useState<NotificationMetrics | null>(null);
  const [deadLetters, setDeadLetters] = useState<DeadLetterItem[]>([]);
  const [workflows, setWorkflows] = useState<MonitoredWorkflow[]>([]);
  const [aiMetrics, setAiMetrics] = useState<AIProviderMetric[]>([]);

  // Modals & Chat
  const [selectedIncidentSummary, setSelectedIncidentSummary] = useState<IncidentAiSummaryResponse | null>(null);
  const [reviewingFraud, setReviewingFraud] = useState<FraudAssessment | null>(null);
  const [fraudDecisionNotes, setFraudDecisionNotes] = useState<string>('');
  const [chatOpen, setChatOpen] = useState<boolean>(false);
  const [chatInput, setChatInput] = useState<string>('');
  const [chatMessages, setChatMessages] = useState<Array<{ sender: 'user' | 'bot'; text: string; time: string }>>([
    {
      sender: 'bot',
      text: 'MediConnect Platform Assistant ready. You can ask "system eka healthy da?", "fraud alerts thiyenawada?", or query failed payments in English/Sinhala.',
      time: 'Just now',
    },
  ]);
  const [chatLoading, setChatLoading] = useState<boolean>(false);

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    try {
      const [h, f, inc, n, dl, wf, ai] = await Promise.all([
        securityMonitoringApi.getPlatformHealth(),
        securityMonitoringApi.getFraudAssessments(),
        securityMonitoringApi.getIncidents(),
        securityMonitoringApi.getNotificationMetrics(),
        securityMonitoringApi.getDeadLetters(),
        securityMonitoringApi.getMonitoredWorkflows(),
        securityMonitoringApi.getAiProviderMetrics(),
      ]);
      setHealth(h);
      setFraudAssessments(f.items || []);
      setIncidents(inc.items || []);
      setNotificationMetrics(n);
      setDeadLetters(dl || []);
      setWorkflows(wf || []);
      setAiMetrics(ai || []);
    } catch {
      showError('Failed to refresh monitoring telemetry.');
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  // Handlers
  const handleAcknowledgeIncident = async (id: string) => {
    try {
      await securityMonitoringApi.acknowledgeIncident(id);
      showSuccess(`Incident ${id} acknowledged.`);
      fetchAllData();
    } catch {
      showError('Failed to acknowledge incident.');
    }
  };

  const handleResolveIncident = async (id: string) => {
    const notes = prompt('Enter incident resolution notes:');
    if (!notes) return;
    try {
      await securityMonitoringApi.resolveIncident(id, notes);
      showSuccess(`Incident ${id} resolved.`);
      fetchAllData();
    } catch {
      showError('Failed to resolve incident.');
    }
  };

  const handleShowAiSummary = async (id: string) => {
    try {
      const res = await securityMonitoringApi.getIncidentAiSummary(id);
      setSelectedIncidentSummary(res);
    } catch {
      showError('Could not retrieve AI investigation summary.');
    }
  };

  const handleFraudDecision = async (decision: string) => {
    if (!reviewingFraud || !fraudDecisionNotes.trim()) {
      showError('Please provide investigation notes for this decision.');
      return;
    }
    try {
      await securityMonitoringApi.reviewFraudAssessment(reviewingFraud.assessmentId, decision, fraudDecisionNotes);
      showSuccess(`Fraud assessment ${decision.toUpperCase()}ed.`);
      setReviewingFraud(null);
      setFraudDecisionNotes('');
      fetchAllData();
    } catch {
      showError('Failed to submit fraud review.');
    }
  };

  const handleRetryDeadLetter = async (id: string) => {
    try {
      await securityMonitoringApi.retryDeadLetter(id);
      showSuccess('Notification successfully requeued.');
      fetchAllData();
    } catch {
      showError('Failed to requeue notification.');
    }
  };

  const handleRecoverWorkflow = async (id: string) => {
    try {
      await securityMonitoringApi.recoverWorkflow(id, 'Admin manual recovery from monitoring console');
      showSuccess(`Workflow ${id} recovered.`);
      fetchAllData();
    } catch {
      showError('Failed to recover workflow.');
    }
  };

  const handleSendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { sender: 'user', text: userMsg, time: new Date().toLocaleTimeString() }]);
    setChatLoading(true);

    try {
      const res = await securityMonitoringApi.chatMonitoringAssistant(userMsg);
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: res.response || 'Telemetry query completed.',
          time: new Date().toLocaleTimeString(),
        },
      ]);
    } catch {
      setChatMessages(prev => [
        ...prev,
        { sender: 'bot', text: 'Error contacting Monitoring Assistant.', time: new Date().toLocaleTimeString() },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
            <Activity className="h-7 w-7 text-brand-600" />
            Platform Security & Health Command Center
          </h1>
          <p className="text-sm text-slate-500">
            Infrastructure checks, rule-based fraud signals, notification delivery records and AI provider metrics. Values refresh when this page loads.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchAllData}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-xs hover:bg-slate-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin text-brand-600' : ''}`} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setChatOpen(!chatOpen)}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-xs hover:bg-brand-700"
          >
            <Bot className="h-4 w-4" />
            AI Monitoring Assistant
          </button>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* System Health */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">System Status</span>
            {health?.status === 'healthy' ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                <CheckCircle2 className="h-3.5 w-3.5" /> Healthy
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5" /> {health?.status || 'Unknown'}
              </span>
            )}
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">
            {health ? `${(health.uptimeSeconds / 3600).toFixed(1)} hrs` : '--'}
          </p>
          <p className="mt-1 text-xs text-slate-500">Backend process uptime since last start (not availability %)</p>
        </div>

        {/* Active Incidents */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Active Incidents</span>
            <AlertTriangle className="h-4 w-4 text-rose-500" />
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">{health?.activeIncidentsCount ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Requiring admin attention</p>
        </div>

        {/* Fraud Alerts */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fraud Alerts</span>
            <ShieldAlert className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">{health?.openFraudAssessmentsCount ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">Awaiting human review</p>
        </div>

        {/* Notification Backlog */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Notification Outbox</span>
            <Mail className="h-4 w-4 text-brand-500" />
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-900">{notificationMetrics?.totalBacklog ?? 0}</p>
          <p className="mt-1 text-xs text-slate-500">
            {notificationMetrics
              ? notificationMetrics.failureRatePercent === null || notificationMetrics.failureRatePercent === undefined
                ? 'No deliveries attempted yet'
                : `${notificationMetrics.failureRatePercent}% failure rate`
              : '--'}
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6">
          {(
            [
              { id: 'health', label: 'Dependencies & Workers', icon: Server },
              { id: 'fraud', label: 'Fraud Risk Center', icon: ShieldAlert, count: health?.openFraudAssessmentsCount },
              { id: 'incidents', label: 'Incidents Management', icon: AlertTriangle, count: health?.activeIncidentsCount },
              { id: 'notifications', label: 'Outbox & Workflows', icon: RotateCcw, count: deadLetters.length },
              { id: 'ai', label: 'AI Providers & Safety', icon: Cpu },
            ] as Array<{
              id: MonitoringTab;
              label: string;
              icon: React.ComponentType<{ className?: string }>;
              count?: number;
            }>
          ).map(tab => {
            const Icon = tab.icon;
            const isSel = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 border-b-2 py-3 px-1 text-sm font-medium transition-colors ${
                  isSel
                    ? 'border-brand-600 text-brand-600'
                    : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="ml-1 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-700">
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab 1: Dependencies & Workers */}
      {activeTab === 'health' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Dependencies Card */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
            <h3 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Server className="h-5 w-5 text-slate-500" /> Infrastructure Dependencies
            </h3>
            <div className="divide-y divide-slate-100">
              {health?.dependencies.map((dep, idx) => (
                <div key={idx} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{dep.name}</p>
                    <p className="text-xs text-slate-500">{dep.message || 'No additional details'}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {dep.latencyMs !== null && dep.latencyMs !== undefined && (
                      <span className="text-xs font-mono text-slate-500">{dep.latencyMs}ms</span>
                    )}
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        dep.status === 'healthy'
                          ? 'bg-emerald-50 text-emerald-700'
                          : dep.status === 'degraded' || dep.status === 'configured_not_verified'
                          ? 'bg-amber-50 text-amber-700'
                          : dep.status === 'not_configured' || dep.status === 'disabled' || dep.status === 'unknown'
                          ? 'bg-slate-100 text-slate-600'
                          : 'bg-rose-50 text-rose-700'
                      }`}
                    >
                      {dep.status === 'configured_not_verified' ? 'CONFIGURED, NOT VERIFIED' : dep.status.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Workers Card */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
            <h3 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-slate-500" /> Background Worker Heartbeats
            </h3>
            <div className="divide-y divide-slate-100">
              {health?.workers.map((w, idx) => (
                <div key={idx} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{w.workerName}</p>
                    <p className="text-xs text-slate-500">
                      {w.lastHeartbeat
                        ? `Last heartbeat: ${new Date(w.lastHeartbeat).toLocaleString()} • Run time: ${w.lastDurationSeconds ?? '?'}s`
                        : 'No heartbeat recorded since this database was created'}
                      {w.lastError ? ` • Last error: ${w.lastError}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        w.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                      }`}
                    >
                      {w.status.toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Fraud Risk Center */}
      {activeTab === 'fraud' && (
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs">
          <div className="border-b border-slate-200 p-4">
            <h3 className="text-base font-semibold text-slate-900">Explainable Fraud Risk Assessments</h3>
            <p className="text-xs text-slate-500">Evaluated against deterministic transactional and authorization rules.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="py-3 px-4">Assessment ID</th>
                  <th className="py-3 px-4">Entity / Account</th>
                  <th className="py-3 px-4">Risk Tier</th>
                  <th className="py-3 px-4">Score</th>
                  <th className="py-3 px-4">Triggered Rules</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {fraudAssessments.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-500">
                      No active fraud assessments detected.
                    </td>
                  </tr>
                ) : (
                  fraudAssessments.map(fa => (
                    <tr key={fa.assessmentId} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-mono text-xs font-bold text-slate-800">{fa.assessmentId}</td>
                      <td className="py-3 px-4 text-xs text-slate-600">{fa.relatedEntityReference}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ${
                            fa.riskLevel === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-800'
                              : fa.riskLevel === 'HIGH'
                              ? 'bg-orange-100 text-orange-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {fa.riskLevel}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-900">{fa.riskScore.toFixed(0)} / 100</td>
                      <td className="py-3 px-4 text-xs text-slate-600">
                        {fa.triggeredRules.map((r, i) => (
                          <span key={i} className="mr-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-700">
                            {r}
                          </span>
                        ))}
                      </td>
                      <td className="py-3 px-4 text-xs font-semibold text-slate-700">{fa.reviewStatus}</td>
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setReviewingFraud(fa);
                            setFraudDecisionNotes('');
                          }}
                          className="rounded bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-100"
                        >
                          Review
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Operational Incidents */}
      {activeTab === 'incidents' && (
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs">
          <div className="border-b border-slate-200 p-4 flex justify-between items-center">
            <div>
              <h3 className="text-base font-semibold text-slate-900">Platform Incidents</h3>
              <p className="text-xs text-slate-500">Track and remediate operational outages and security alerts.</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="py-3 px-4">ID</th>
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Service</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {incidents.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500">
                      No open incidents reported.
                    </td>
                  </tr>
                ) : (
                  incidents.map(inc => (
                    <tr key={inc.incidentId} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-mono text-xs font-bold text-slate-800">{inc.incidentId}</td>
                      <td className="py-3 px-4 font-medium text-slate-900">{inc.title}</td>
                      <td className="py-3 px-4 text-xs text-slate-600">{inc.affectedService}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ${
                            inc.severity === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-800'
                              : inc.severity === 'HIGH'
                              ? 'bg-orange-100 text-orange-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {inc.severity}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs font-semibold text-slate-700">{inc.status}</td>
                      <td className="py-3 px-4 text-right space-x-2">
                        <button
                          type="button"
                          onClick={() => handleShowAiSummary(inc.incidentId)}
                          className="rounded bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200"
                        >
                          AI Breakdown
                        </button>
                        {inc.status === 'OPEN' && (
                          <button
                            type="button"
                            onClick={() => handleAcknowledgeIncident(inc.incidentId)}
                            className="rounded bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100"
                          >
                            Acknowledge
                          </button>
                        )}
                        {inc.status !== 'RESOLVED' && (
                          <button
                            type="button"
                            onClick={() => handleResolveIncident(inc.incidentId)}
                            className="rounded bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"
                          >
                            Resolve
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Outbox & Workflows */}
      {activeTab === 'notifications' && (
        <div className="space-y-6">
          {/* Delivery records per channel (P04-N15): from the outbox and reminder events the workers write. */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs" data-testid="notification-channels">
            <h3 className="text-base font-semibold text-slate-900 mb-2">Delivery by channel</h3>
            <p className="text-xs text-slate-500 mb-4">
              Counts come from stored delivery records. &ldquo;Provider accepted&rdquo; is not proof of delivery; a channel
              whose provider is not configured is shown as disabled and sends nothing.
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="py-2 px-3">Channel</th>
                    <th className="py-2 px-3">Provider</th>
                    <th className="py-2 px-3">Delivered / stored</th>
                    <th className="py-2 px-3">Provider accepted</th>
                    <th className="py-2 px-3">Pending</th>
                    <th className="py-2 px-3">Failed</th>
                    <th className="py-2 px-3">Skipped</th>
                    <th className="py-2 px-3">Disabled</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(notificationMetrics?.byChannel || []).map((ch) => (
                    <tr key={ch.channel}>
                      <td className="py-2 px-3 font-medium text-slate-800">{ch.channel.replace('_', '-')}</td>
                      <td className="py-2 px-3 text-xs text-slate-600">{(ch.providerStatus || 'unknown').replace(/_/g, ' ')}</td>
                      <td className="py-2 px-3">{ch.delivered}</td>
                      <td className="py-2 px-3">{ch.accepted ?? 0}</td>
                      <td className="py-2 px-3">{ch.pending}</td>
                      <td className="py-2 px-3">{ch.failed}</td>
                      <td className="py-2 px-3">{ch.skipped ?? 0}</td>
                      <td className="py-2 px-3">{ch.disabled ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(notificationMetrics?.notes || []).map((n) => (
              <p key={n} className="mt-2 text-xs text-amber-700">{n}</p>
            ))}
          </div>

          {/* Dead Letters */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
            <h3 className="text-base font-semibold text-slate-900 mb-2">Notification Dead-Letter Queue</h3>
            <p className="text-xs text-slate-500 mb-4">Notifications that exceeded maximum bounded retries.</p>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="py-2 px-3">DL ID</th>
                    <th className="py-2 px-3">Channel</th>
                    <th className="py-2 px-3">Reason</th>
                    <th className="py-2 px-3">Retries</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {deadLetters.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-4 text-center text-slate-500">
                        Dead-Letter Queue is empty.
                      </td>
                    </tr>
                  ) : (
                    deadLetters.map(dl => (
                      <tr key={dl.deadLetterId}>
                        <td className="py-2 px-3 font-mono text-xs font-bold text-slate-800">{dl.deadLetterId}</td>
                        <td className="py-2 px-3 text-xs uppercase font-semibold text-slate-600">{dl.channel}</td>
                        <td className="py-2 px-3 text-xs text-slate-600">{dl.reason}</td>
                        <td className="py-2 px-3 text-xs text-slate-700">{dl.retryCount}</td>
                        <td className="py-2 px-3 text-xs font-bold text-slate-700">{dl.status}</td>
                        <td className="py-2 px-3 text-right">
                          <button
                            type="button"
                            onClick={() => handleRetryDeadLetter(dl.deadLetterId)}
                            className="rounded bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-100"
                          >
                            Requeue
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Monitored Workflows */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
            <h3 className="text-base font-semibold text-slate-900 mb-2">Automated Healthcare Workflows</h3>
            <p className="text-xs text-slate-500 mb-4">Monitored lifecycle of bookings, payment checks, and notes.</p>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="py-2 px-3">Workflow ID</th>
                    <th className="py-2 px-3">Type</th>
                    <th className="py-2 px-3">Entity Ref</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3 text-right">Recovery</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {workflows.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-slate-500">
                        No active workflows recorded.
                      </td>
                    </tr>
                  ) : (
                    workflows.map(wf => (
                      <tr key={wf.workflowId}>
                        <td className="py-2 px-3 font-mono text-xs font-bold text-slate-800">{wf.workflowId}</td>
                        <td className="py-2 px-3 text-xs text-slate-700">{wf.workflowType}</td>
                        <td className="py-2 px-3 text-xs font-mono text-slate-500">{wf.relatedEntityId}</td>
                        <td className="py-2 px-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                              wf.status === 'COMPLETED' || wf.status === 'RECOVERED'
                                ? 'bg-emerald-50 text-emerald-700'
                                : wf.status === 'STUCK'
                                ? 'bg-rose-100 text-rose-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {wf.status}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right">
                          <button
                            type="button"
                            onClick={() => handleRecoverWorkflow(wf.workflowId)}
                            className="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200"
                          >
                            Recover
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 5: AI Providers & Safety */}
      {activeTab === 'ai' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {aiMetrics.map((prov, i) => (
            <div key={i} className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold capitalize text-slate-900 flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-brand-600" /> {prov.provider} Integration
                </h3>
                <span
                  className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold ${
                    prov.circuitBreakerState === 'CLOSED'
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-rose-100 text-rose-800'
                  }`}
                >
                  Circuit: {prov.circuitBreakerState}
                </span>
              </div>
              <div className="space-y-2 text-sm text-slate-600">
                <div className="flex justify-between">
                  <span>Total Requests:</span>
                  <span className="font-bold text-slate-900">{prov.totalRequests}</span>
                </div>
                <div className="flex justify-between">
                  <span>Successful Requests:</span>
                  <span className="font-bold text-emerald-600">{prov.successfulRequests}</span>
                </div>
                <div className="flex justify-between">
                  <span>Failed Requests:</span>
                  <span className="font-bold text-rose-600">{prov.failedRequests}</span>
                </div>
                <div className="flex justify-between">
                  <span>Average Latency:</span>
                  <span className="font-mono text-slate-900">{prov.averageLatencyMs} ms</span>
                </div>
                <div className="flex justify-between">
                  <span>Fallback Activations:</span>
                  <span className="font-bold text-amber-600">{prov.fallbackActivations}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI Breakdown Modal */}
      {selectedIncidentSummary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-xl rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900 mb-2">AI Incident Investigation Summary</h3>
            <p className="text-sm text-slate-600 mb-4">{selectedIncidentSummary.summary}</p>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Recommended Investigation Steps</h4>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700 mb-6">
              {selectedIncidentSummary.suggestedInvestigationSteps?.map((s: string, idx: number) => (
                <li key={idx}>{s}</li>
              ))}
            </ul>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedIncidentSummary(null)}
                className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fraud Review Modal */}
      {reviewingFraud && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900 mb-2">Review Fraud Assessment: {reviewingFraud.assessmentId}</h3>
            <p className="text-xs text-slate-600 mb-3">{reviewingFraud.explanation}</p>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Investigation Justification / Notes:</label>
            <textarea
              rows={3}
              value={fraudDecisionNotes}
              onChange={e => setFraudDecisionNotes(e.target.value)}
              placeholder="e.g. Verified customer transaction history with bank..."
              className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-brand-500 focus:outline-none mb-4"
            />
            <div className="flex justify-between items-center">
              <button
                type="button"
                onClick={() => setReviewingFraud(null)}
                className="text-sm text-slate-500 hover:text-slate-700"
              >
                Cancel
              </button>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleFraudDecision('dismiss')}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Dismiss (False Positive)
                </button>
                <button
                  type="button"
                  onClick={() => handleFraudDecision('confirm')}
                  className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700"
                >
                  Confirm Fraud
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating AI Monitoring Assistant Chat Drawer */}
      {chatOpen && (
        <div className="fixed bottom-4 right-4 z-50 flex h-96 w-96 flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-100 bg-brand-600 p-3 text-white rounded-t-2xl">
            <span className="flex items-center gap-2 text-sm font-bold">
              <Bot className="h-4 w-4" /> AI Monitoring Assistant
            </span>
            <button type="button" onClick={() => setChatOpen(false)} className="text-white/80 hover:text-white">
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
            {chatMessages.map((m, i) => (
              <div key={i} className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}>
                <div
                  className={`max-w-[85%] rounded-xl px-3 py-2 ${
                    m.sender === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-800'
                  }`}
                >
                  {m.text}
                </div>
                <span className="text-[9px] text-slate-400 mt-0.5">{m.time}</span>
              </div>
            ))}
            {chatLoading && <div className="text-xs text-slate-400 italic">Querying live telemetry...</div>}
          </div>
          <div className="border-t border-slate-100 p-2 flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendChat()}
              placeholder="e.g. system eka healthy da?..."
              className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs focus:outline-none focus:border-brand-500"
            />
            <button
              type="button"
              onClick={handleSendChat}
              disabled={chatLoading}
              className="rounded-lg bg-brand-600 p-2 text-white hover:bg-brand-700"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
export default MonitoringPage;
