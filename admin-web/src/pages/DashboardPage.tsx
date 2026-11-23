import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Users,
  Stethoscope,
  UserCheck,
  CalendarCheck,
  CreditCard,
  Clock,
  ArrowRight,
  ShieldAlert,
  Sparkles,
  Send,
  Terminal,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { analyticsApi } from '../api/analyticsApi';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { AdminAssistantChatResponse } from '../types/adminWorkflow';
import { StatCard } from '../components/common/StatCard';
import { Button } from '../components/common/Button';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorState } from '../components/common/ErrorState';

export const DashboardPage: React.FC = () => {
  const {
    data: overview,
    isLoading: isOverviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: () => analyticsApi.getOverview(),
  });

  const {
    data: apptAnalytics,
    isLoading: isApptLoading,
  } = useQuery({
    queryKey: ['admin-appt-analytics'],
    queryFn: () => analyticsApi.getAppointments(),
  });

  const [aiQuery, setAiQuery] = useState('');
  const [aiResponse, setAiResponse] = useState<AdminAssistantChatResponse | null>(null);

  const askAiMutation = useMutation({
    mutationFn: (msg: string) => adminWorkflowApi.askAssistant(msg),
    onSuccess: (data) => {
      setAiResponse(data);
    },
  });

  const handleAsk = (queryText?: string) => {
    const text = (queryText || aiQuery).trim();
    if (!text) return;
    setAiQuery(text);
    askAiMutation.mutate(text);
  };

  if (isOverviewLoading) {
    return <LoadingSkeleton rows={6} height="h-28" />;
  }

  if (overviewError) {
    return (
      <ErrorState
        title="Failed to load dashboard metrics"
        message="Could not retrieve platform analytics from the server."
        onRetry={refetchOverview}
      />
    );
  }

  const totals = overview?.totals;
  const payments = overview?.payments;
  const recentActivities = overview?.recentActivity || [];

  // Chart data from daily appointment trends
  const chartData =
    apptAnalytics?.dailyTrends?.map((t) => ({
      date: t.date.slice(5), // MM-DD
      appointments: t.count,
    })) || [];

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-gradient-to-r from-[#172B4D] via-[#1565C0] to-[#1976D2] rounded-3xl p-6 sm:p-8 text-white shadow-lg">
        <div>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-white/15 text-blue-100 border border-white/20 mb-2">
            Operations & Health Overview
          </span>
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight">
            Platform Command Center
          </h1>
          <p className="mt-1 text-xs text-slate-300 max-w-xl">
            Real-time monitoring of patient engagement, verified medical practitioners, bookings, and financial settlements.
          </p>
        </div>

        {totals && totals.pendingDoctorApprovals > 0 && (
          <Link
            to="/doctor-approvals"
            className="flex items-center gap-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-4 py-2.5 rounded-xl text-xs transition-colors shrink-0 shadow-md"
          >
            <ShieldAlert className="w-4 h-4" />
            <span>{totals.pendingDoctorApprovals} Approvals Pending</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Link>
        )}
      </div>

      {/* Admin AI Operations Assistant Bar */}
      <div className="rounded-2xl border border-brand-200/90 bg-gradient-to-br from-brand-50/60 to-white p-5 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white shadow-xs">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Admin AI Operations Assistant</h2>
              <span className="text-[11px] text-slate-500">
                Natural Language Operations in English & Romanized Sinhala
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-semibold text-brand-700 bg-brand-100/60 rounded-full px-2.5 py-1">
            <Terminal className="h-3 w-3" />
            <span>Bounded Tool Registry</span>
          </div>
        </div>

        {/* Input box */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={aiQuery}
            onChange={(e) => setAiQuery(e.target.value)}
            placeholder="Ask anything: 'pending doctors keeyak innawada?', 'failed payments tika check karanna'..."
            className="flex-1 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 shadow-xs"
          />
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={!aiQuery.trim() || askAiMutation.isPending}
            isLoading={askAiMutation.isPending}
            leftIcon={<Send className="h-3.5 w-3.5" />}
          >
            Ask AI
          </Button>
        </form>

        {/* Quick prompt chips */}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {[
            'pending doctors keeyak innawada?',
            'me month eke bookings keeyak thiyenawada?',
            'failed payments tika check karanna',
            'refund requests monawada?',
            'last 7 days payment success rate eka kiyanna',
          ].map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => handleAsk(prompt)}
              className="rounded-full bg-white border border-slate-200 hover:border-brand-300 hover:bg-brand-50 px-2.5 py-1 text-[11px] text-slate-600 transition-colors shadow-2xs font-medium"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* AI Answer Display */}
        {aiResponse && (
          <div className="mt-3 rounded-xl border border-brand-200 bg-white p-4 text-xs space-y-2 shadow-xs">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-bold text-brand-900 flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-brand-600" /> Grounded Assistant Answer
              </span>
              {aiResponse.toolCalled && (
                <span className="font-mono text-[10px] text-slate-500 bg-slate-100 rounded px-1.5 py-0.5 border border-slate-200">
                  tool: {aiResponse.toolCalled}
                </span>
              )}
            </div>
            <p className="text-slate-800 font-medium leading-relaxed whitespace-pre-wrap">
              {aiResponse.reply}
            </p>
            {aiResponse.actionSuggestions && aiResponse.actionSuggestions.length > 0 && (
              <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
                <span className="text-[10px] uppercase font-bold text-slate-400">Suggestions:</span>
                <div className="flex flex-wrap gap-1.5">
                  {aiResponse.actionSuggestions.map((sug) => (
                    <button
                      key={sug}
                      type="button"
                      onClick={() => handleAsk(sug)}
                      className="text-[10px] font-semibold text-brand-700 hover:text-brand-900 underline"
                    >
                      {sug}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Registered Patients"
          value={totals?.totalPatients?.toLocaleString() ?? 0}
          icon={<Users className="w-5 h-5" />}
          iconBgColor="bg-sky-50 text-sky-600"
          subtitle={`${totals?.totalUsers ?? 0} total platform accounts`}
        />
        <StatCard
          title="Verified Practitioners"
          value={totals?.verifiedDoctors?.toLocaleString() ?? 0}
          icon={<Stethoscope className="w-5 h-5" />}
          iconBgColor="bg-brand-50 text-brand-600"
          subtitle={`${totals?.totalDoctors ?? 0} total registered doctors`}
        />
        <StatCard
          title="Pending Verifications"
          value={totals?.pendingDoctorApprovals ?? 0}
          icon={<UserCheck className="w-5 h-5" />}
          iconBgColor="bg-amber-50 text-amber-600"
          subtitle="Awaiting credentials review"
        />
        <StatCard
          title="Total Appointments"
          value={totals?.totalAppointments?.toLocaleString() ?? 0}
          icon={<CalendarCheck className="w-5 h-5" />}
          iconBgColor="bg-emerald-50 text-emerald-600"
          subtitle={`${totals?.completedAppointments ?? 0} completed successfully`}
        />
      </div>

      {/* Financial & Volume Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Appointments Volume Trend Chart */}
        <div className="lg:col-span-2 rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Appointment Trends (Last 30 Days)</h2>
              <p className="text-xs text-slate-500">Daily appointment booking volume</p>
            </div>
            <Link
              to="/appointments"
              className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="h-64 w-full">
            {isApptLoading ? (
              <LoadingSkeleton rows={4} height="h-12" />
            ) : chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="apptGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1565C0" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#2196F3" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#172b4d',
                      borderRadius: '0.75rem',
                      border: 'none',
                      color: '#ffffff',
                      fontSize: '0.75rem',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="appointments"
                    stroke="#1565C0"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#apptGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-400">
                No appointment trends recorded in this time range.
              </div>
            )}
          </div>
        </div>

        {/* Financial Revenue Summary Card */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-900">Revenue by Currency</h2>
              <div className="p-2 rounded-xl bg-brand-50 text-brand-600">
                <CreditCard className="w-4 h-4" />
              </div>
            </div>

            <div className="space-y-4">
              {payments?.totalRevenueByCurrency &&
              Object.keys(payments.totalRevenueByCurrency).length > 0 ? (
                Object.entries(payments.totalRevenueByCurrency).map(([curr, amt]) => (
                  <div key={curr} className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      {curr} Balance
                    </span>
                    <p className="text-xl font-extrabold text-slate-900 mt-0.5">
                      {curr.toUpperCase()} {amt.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    LKR Balance
                  </span>
                  <p className="text-xl font-extrabold text-slate-900 mt-0.5">LKR 0.00</p>
                </div>
              )}

              <div className="pt-2 text-xs text-slate-500 space-y-1.5 border-t border-slate-100">
                <div className="flex justify-between">
                  <span>Successful Payments:</span>
                  <span className="font-semibold text-emerald-600">
                    {payments?.succeededTransactions ?? 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Failed Payments:</span>
                  <span className="font-semibold text-rose-600">
                    {payments?.failedTransactions ?? 0}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <Link
            to="/payments"
            className="mt-6 block text-center rounded-xl border border-slate-200 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Review Transactions
          </Link>
        </div>
      </div>

      {/* Recent Administrative Activity */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400" />
            <h2 className="text-sm font-bold text-slate-900">Recent Platform Operations</h2>
          </div>
          <span className="text-[11px] text-slate-400">Audit Trail Enabled</span>
        </div>

        {recentActivities.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {recentActivities.map((act, idx) => (
              <div key={idx} className="py-3 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-800">{act.description}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">{act.type}</p>
                </div>
                <span className="text-[11px] text-slate-500">
                  {new Date(act.timestamp).toLocaleDateString()} {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-6 text-center">
            No recent administrative actions recorded.
          </p>
        )}
      </div>
    </div>
  );
};
