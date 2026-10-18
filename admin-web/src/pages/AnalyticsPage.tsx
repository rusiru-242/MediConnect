import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { analyticsApi } from '../api/analyticsApi';
import { StatCard } from '../components/common/StatCard';
import { DateRangeFilter } from '../components/common/DateRangeFilter';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorState } from '../components/common/ErrorState';
import {
  CreditCard,
  CheckCircle,
  XCircle,
  Percent,
} from 'lucide-react';
import { getErrorMessage } from '../api/client';

export const AnalyticsPage: React.FC = () => {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const {
    data: overview,
    isLoading: isOverviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useQuery({
    queryKey: ['admin-analytics-overview', startDate, endDate],
    queryFn: () => analyticsApi.getOverview(startDate || undefined, endDate || undefined),
  });

  const {
    data: apptAnalytics,
    isLoading: isApptLoading,
  } = useQuery({
    queryKey: ['admin-analytics-appts', startDate, endDate],
    queryFn: () => analyticsApi.getAppointments(startDate || undefined, endDate || undefined),
  });

  const {
    data: paymentAnalytics,
    isLoading: isPaymentLoading,
  } = useQuery({
    queryKey: ['admin-analytics-payments', startDate, endDate],
    queryFn: () => analyticsApi.getPayments(startDate || undefined, endDate || undefined),
  });

  if (isOverviewLoading) {
    return <LoadingSkeleton rows={6} height="h-32" />;
  }

  if (overviewError) {
    return (
      <ErrorState
        title="Failed to load analytics"
        message={getErrorMessage(overviewError)}
        onRetry={refetchOverview}
      />
    );
  }

  const totals = overview?.totals;
  const statusBreakdown = apptAnalytics?.statusBreakdown || {};
  const statusPieData = Object.entries(statusBreakdown).map(([name, value]) => ({
    name,
    value,
  }));

  const COLORS = ['#0d9488', '#0284c7', '#f59e0b', '#e11d48', '#64748b'];

  const paymentTrends = paymentAnalytics?.dailyTrends?.map((d) => ({
    date: d.date.slice(5),
    transactions: d.count,
  })) || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Platform Analytics & Reporting
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Aggregated metrics for clinical utilization, booking reliability, and financial volume.
          </p>
        </div>

        <DateRangeFilter
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          onClear={() => {
            setStartDate('');
            setEndDate('');
          }}
        />
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Completion Rate"
          value={`${apptAnalytics?.completionRatePercent ?? 100}%`}
          icon={<Percent className="w-5 h-5" />}
          iconBgColor="bg-teal-50 text-teal-600"
          subtitle={`${apptAnalytics?.completedBookings ?? 0} completed of ${apptAnalytics?.totalBookings ?? 0}`}
        />
        <StatCard
          title="Cancelled Consultations"
          value={apptAnalytics?.cancelledBookings ?? 0}
          icon={<XCircle className="w-5 h-5" />}
          iconBgColor="bg-rose-50 text-rose-600"
          subtitle="Patient or doctor cancellations"
        />
        <StatCard
          title="Payment Transactions"
          value={paymentAnalytics?.totalTransactions ?? 0}
          icon={<CreditCard className="w-5 h-5" />}
          iconBgColor="bg-sky-50 text-sky-600"
          subtitle={`${paymentAnalytics?.succeededCount ?? 0} settled, ${paymentAnalytics?.failedCount ?? 0} failed`}
        />
        <StatCard
          title="Verified Doctors Ratio"
          value={`${Math.round(
            ((totals?.verifiedDoctors ?? 0) / Math.max(1, totals?.totalDoctors ?? 1)) * 100
          )}%`}
          icon={<CheckCircle className="w-5 h-5" />}
          iconBgColor="bg-emerald-50 text-emerald-600"
          subtitle={`${totals?.verifiedDoctors ?? 0} verified of ${totals?.totalDoctors ?? 0} doctors`}
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Appointment Status Distribution */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-900 mb-1">Appointment Status Breakdown</h2>
          <p className="text-xs text-slate-500 mb-4">Distribution of booking lifecycle states</p>

          <div className="h-64 w-full flex items-center justify-center">
            {isApptLoading ? (
              <LoadingSkeleton rows={3} height="h-16" />
            ) : statusPieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={4}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {statusPieData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: '0.75rem',
                      border: 'none',
                      color: '#ffffff',
                      fontSize: '0.75rem',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-xs text-slate-400">No appointment records found in selected range.</p>
            )}
          </div>
        </div>

        {/* Daily Payment Volume Trend */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-bold text-slate-900 mb-1">Daily Payment Volume Trends</h2>
          <p className="text-xs text-slate-500 mb-4">Daily transaction counts settled via Stripe</p>

          <div className="h-64 w-full">
            {isPaymentLoading ? (
              <LoadingSkeleton rows={3} height="h-16" />
            ) : paymentTrends.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={paymentTrends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: '0.75rem',
                      border: 'none',
                      color: '#ffffff',
                      fontSize: '0.75rem',
                    }}
                  />
                  <Bar dataKey="transactions" fill="#0284c7" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-slate-400">
                No payment activity recorded in this period.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
