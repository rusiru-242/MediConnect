import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldAlert,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Info,
  CreditCard,
} from 'lucide-react';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { ReconciliationDiscrepancy } from '../types/adminWorkflow';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../context/ToastContext';

export const ReconciliationPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [selectedDiscrepancy, setSelectedDiscrepancy] = useState<ReconciliationDiscrepancy | null>(null);

  const {
    data: report,
    isLoading,
    isRefetching,
  } = useQuery({
    queryKey: ['reconciliation-issues'],
    queryFn: () => adminWorkflowApi.getReconciliationIssues(),
  });

  const runReconcileMutation = useMutation({
    mutationFn: () => adminWorkflowApi.runReconciliation(),
    onSuccess: (data) => {
      queryClient.setQueryData(['reconciliation-issues'], data);
      showToast(
        data.discrepanciesCount === 0
          ? 'Reconciliation completed: All transactions match with zero discrepancies.'
          : `Reconciliation completed: Found ${data.discrepanciesCount} discrepancy item(s).`,
        data.discrepanciesCount === 0 ? 'success' : 'warning'
      );
    },
    onError: () => {
      showToast('Failed to run reconciliation checks. Check backend connectivity.', 'error');
    },
  });

  const discrepancies = report?.discrepancies || [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Payment Reconciliation
            </h1>
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-700 border border-brand-200">
              Phase 5
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Deterministic cross-validation between Stripe payment intents and MongoDB appointment booking states.
          </p>
        </div>

        <Button
          variant="primary"
          onClick={() => runReconcileMutation.mutate()}
          isLoading={runReconcileMutation.isPending || isRefetching}
          leftIcon={<RefreshCw className="h-4 w-4" />}
        >
          Run Reconciliation Check
        </Button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Transactions Checked
            </span>
            <CreditCard className="h-4 w-4 text-slate-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {isLoading ? '...' : (report?.totalChecked || 0)}
          </p>
          <span className="mt-1 block text-xs text-slate-500">Authoritative payment & booking records</span>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Discrepancies Flagged
            </span>
            <ShieldAlert className={`h-4 w-4 ${discrepancies.length > 0 ? 'text-rose-500' : 'text-emerald-500'}`} />
          </div>
          <p className={`mt-2 text-2xl font-bold ${discrepancies.length > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
            {isLoading ? '...' : discrepancies.length}
          </p>
          <span className="mt-1 block text-xs text-slate-500">
            {discrepancies.length === 0 ? 'All transactions clean' : 'Requires administrative review'}
          </span>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Last Verified
            </span>
            <CheckCircle2 className="h-4 w-4 text-brand-500" />
          </div>
          <p className="mt-2 text-sm font-semibold text-slate-800">
            {report?.checkedAt ? new Date(report.checkedAt).toLocaleTimeString() : 'Never'}
          </p>
          <span className="mt-1 block text-xs text-slate-500">Idempotent automated scan</span>
        </div>
      </div>

      {/* Discrepancies Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs overflow-hidden">
        <div className="border-b border-slate-100 bg-slate-50/50 px-6 py-4">
          <h2 className="text-sm font-bold text-slate-900">
            Reviewable Discrepancy Queue
          </h2>
        </div>

        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={4} />
          </div>
        ) : discrepancies.length === 0 ? (
          <div className="py-12">
            <EmptyState
              title="Zero Discrepancies Detected"
              description="All Stripe payment settlements align with local MongoDB booking records and cancellation statuses."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Severity</th>
                  <th className="px-6 py-3.5">Type & Reference</th>
                  <th className="px-6 py-3.5">Description</th>
                  <th className="px-6 py-3.5">AI Recommendation</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {discrepancies.map((disc) => (
                  <tr key={disc.discrepancyId} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          disc.severity === 'HIGH'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        <AlertTriangle className="h-3 w-3" />
                        {disc.severity}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-900">{disc.type}</div>
                      <div className="font-mono text-xs text-slate-400 mt-0.5">
                        {disc.stripePaymentIntentId || disc.appointmentId || disc.discrepancyId}
                      </div>
                    </td>
                    <td className="px-6 py-4 max-w-md">
                      <p className="text-xs text-slate-700 leading-relaxed">{disc.description}</p>
                    </td>
                    <td className="px-6 py-4 max-w-sm">
                      <div className="rounded-lg bg-brand-50/60 border border-brand-100 p-2.5 text-xs text-brand-900">
                        {disc.recommendation}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right whitespace-nowrap">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSelectedDiscrepancy(disc)}
                      >
                        Review
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedDiscrepancy && (
        <Modal
          isOpen={!!selectedDiscrepancy}
          onClose={() => setSelectedDiscrepancy(null)}
          title="Discrepancy Investigation"
          description={`Reference: ${selectedDiscrepancy.discrepancyId}`}
          maxWidth="xl"
        >
          <div className="space-y-4 py-2">
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-medium text-slate-500">Anomaly Classification:</span>
                <span className="font-semibold text-slate-800">{selectedDiscrepancy.type}</span>
              </div>
              {selectedDiscrepancy.stripePaymentIntentId && (
                <div className="flex justify-between items-center text-xs">
                  <span className="font-medium text-slate-500">Stripe Payment Intent:</span>
                  <span className="font-mono text-slate-800">{selectedDiscrepancy.stripePaymentIntentId}</span>
                </div>
              )}
              {selectedDiscrepancy.appointmentId && (
                <div className="flex justify-between items-center text-xs">
                  <span className="font-medium text-slate-500">Linked Appointment ID:</span>
                  <span className="font-mono text-slate-800">{selectedDiscrepancy.appointmentId}</span>
                </div>
              )}
            </div>

            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                Observed Root Cause
              </h4>
              <p className="text-sm text-slate-800 leading-relaxed bg-white border border-slate-200 rounded-lg p-3">
                {selectedDiscrepancy.description}
              </p>
            </div>

            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-brand-700 mb-1.5 flex items-center gap-1.5">
                <Info className="h-4 w-4" /> AI Remediation Protocol
              </h4>
              <div className="rounded-lg bg-brand-50 border border-brand-200 p-3 text-xs text-brand-900 leading-relaxed">
                {selectedDiscrepancy.recommendation}
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end gap-2.5">
              <Button variant="secondary" onClick={() => setSelectedDiscrepancy(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
