import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Download,
  Sparkles,
  RefreshCw,
  Table as TableIcon,
} from 'lucide-react';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { Button } from '../components/common/Button';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { useToast } from '../context/ToastContext';

const REPORT_OPTIONS = [
  { value: 'daily_appointment', label: 'Daily Appointment Operations' },
  { value: 'weekly_booking', label: 'Weekly Booking & Conversion' },
  { value: 'monthly_payment', label: 'Monthly Payment & Revenue Breakdown' },
  { value: 'doctor_verification_backlog', label: 'Doctor Verification & Credentialing Backlog' },
  { value: 'support_ticket_resolution', label: 'Customer Support Ticket Resolution' },
  { value: 'refund_status', label: 'Refund Status & Cancellation Settlements' },
];

export const ReportsPage: React.FC = () => {
  const { showToast } = useToast();
  const [reportType, setReportType] = useState<string>('daily_appointment');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const {
    data: report,
    isLoading,
    refetch,
    isRefetching,
  } = useQuery({
    queryKey: ['admin-report', reportType, startDate, endDate],
    queryFn: () => adminWorkflowApi.generateReport(reportType, startDate || undefined, endDate || undefined),
  });

  const exportMutation = useMutation({
    mutationFn: () => adminWorkflowApi.exportReportCsv(reportType, startDate || undefined, endDate || undefined),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `mediconnect_${reportType}_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showToast('CSV report downloaded successfully.', 'success');
    },
    onError: () => {
      showToast('Failed to export CSV report.', 'error');
    },
  });

  const metrics = report?.metrics || {};
  const items = report?.items || [];
  const headers = items.length > 0 ? Object.keys(items[0]) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Operational & Audit Reports
            </h1>
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-700 border border-brand-200">
              CSV Export
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Authoritative platform reports grounded exclusively in verified MongoDB records.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            onClick={() => refetch()}
            isLoading={isRefetching}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Regenerate
          </Button>
          <Button
            variant="primary"
            onClick={() => exportMutation.mutate()}
            isLoading={exportMutation.isPending}
            leftIcon={<Download className="h-4 w-4" />}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {/* Control Filters Bar */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
              Report Subject
            </label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="w-full rounded-lg border border-slate-300 p-2 text-xs font-medium text-slate-800 focus:ring-1 focus:ring-brand-500"
            >
              {REPORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
              From Date (Optional)
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-lg border border-slate-300 p-2 text-xs text-slate-800 focus:ring-1 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
              To Date (Optional)
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg border border-slate-300 p-2 text-xs text-slate-800 focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>
      </div>

      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : report ? (
        <>
          {/* Grounded AI Executive Summary Card */}
          {report.aiSummary && (
            <div className="rounded-xl border border-brand-200 bg-brand-50/60 p-5 shadow-xs">
              <div className="flex items-center gap-2 mb-2 text-xs font-bold text-brand-900">
                <Sparkles className="h-4 w-4 text-brand-600" />
                Grounded Executive Summary
              </div>
              <p className="text-sm text-brand-950 leading-relaxed font-medium">
                {report.aiSummary}
              </p>
              <div className="mt-3 flex items-center gap-4 text-[11px] text-brand-700 font-medium">
                <span>Date Range: {report.dateRange.startDate} to {report.dateRange.endDate}</span>
                <span>Generated: {new Date(report.generatedAt).toLocaleString()}</span>
              </div>
            </div>
          )}

          {/* Metric Summary Grid */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Object.entries(metrics).map(([key, val]) => (
              <div key={key} className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block truncate">
                  {key.replace(/([A-Z])/g, ' $1').trim()}
                </span>
                <span className="mt-1 block text-xl font-bold text-slate-900">
                  {typeof val === 'number'
                    ? key.toLowerCase().includes('lkr') || key.toLowerCase().includes('revenue') || key.toLowerCase().includes('fee')
                      ? `LKR ${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                      : key.toLowerCase().includes('rate')
                      ? `${val}%`
                      : val.toLocaleString()
                    : String(val)}
                </span>
              </div>
            ))}
          </div>

          {/* Data Items Table */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs overflow-hidden">
            <div className="border-b border-slate-100 bg-slate-50/50 px-6 py-4 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <TableIcon className="h-4 w-4 text-slate-500" />
                Underlying Records ({items.length})
              </h2>
            </div>

            {items.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No matching records found for the specified period.
              </div>
            ) : (
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-left text-xs text-slate-600">
                  <thead className="sticky top-0 border-b border-slate-200 bg-slate-100 font-semibold uppercase tracking-wider text-slate-600">
                    <tr>
                      {headers.map((h) => (
                        <th key={h} className="px-5 py-3">
                          {h.replace(/([A-Z])/g, ' $1').trim()}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {items.slice(0, 100).map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        {headers.map((h) => (
                          <td key={h} className="px-5 py-3 font-mono text-[11px] whitespace-nowrap">
                            {String(row[h] ?? '-')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
};
