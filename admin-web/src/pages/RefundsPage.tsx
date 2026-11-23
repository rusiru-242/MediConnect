import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldCheck,
} from 'lucide-react';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { RefundRequest } from '../types/adminWorkflow';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../context/ToastContext';

export const RefundsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedRefund, setSelectedRefund] = useState<RefundRequest | null>(null);

  // Modals
  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [isRejectOpen, setIsRejectOpen] = useState(false);
  const [customAmount, setCustomAmount] = useState<number | ''>('');
  const [actionNotes, setActionNotes] = useState('');

  const { data: refundsData, isLoading } = useQuery({
    queryKey: ['refund-requests', statusFilter],
    queryFn: () => adminWorkflowApi.listRefunds({ status: statusFilter, pageSize: 50 }),
  });

  const approveMutation = useMutation({
    mutationFn: ({
      refundId,
      amount,
      notes,
    }: {
      refundId: string;
      amount?: number;
      notes?: string;
    }) => adminWorkflowApi.approveRefund(refundId, amount, notes),
    onSuccess: (data) => {
      showToast(data.message || 'Refund successfully approved and processed.', 'success');
      setIsApproveOpen(false);
      setSelectedRefund(null);
      queryClient.invalidateQueries({ queryKey: ['refund-requests'] });
    },
    onError: (err: any) => {
      showToast(err?.response?.data?.detail || 'Failed to approve refund.', 'error');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ refundId, reason }: { refundId: string; reason: string }) =>
      adminWorkflowApi.rejectRefund(refundId, reason),
    onSuccess: (data) => {
      showToast(data.message || 'Refund request rejected.', 'success');
      setIsRejectOpen(false);
      setSelectedRefund(null);
      queryClient.invalidateQueries({ queryKey: ['refund-requests'] });
    },
    onError: (err: any) => {
      showToast(err?.response?.data?.detail || 'Failed to reject refund.', 'error');
    },
  });

  const refunds = refundsData?.items || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Refund Review & Cancellation Settlements
            </h1>
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-700 border border-brand-200">
              Stripe Safe
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Deterministic cancellation policy evaluation with human-authorized Stripe refund settlement.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-2">
          {['ALL', 'requested', 'succeeded', 'rejected'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors capitalize ${
                statusFilter === st
                  ? 'bg-brand-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Refunds Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} />
          </div>
        ) : refunds.length === 0 ? (
          <div className="py-12">
            <EmptyState
              title="No Refund Requests Found"
              description="No refund inquiries matching the selected filter."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Refund ID</th>
                  <th className="px-6 py-3.5">Patient</th>
                  <th className="px-6 py-3.5">Requested Amount</th>
                  <th className="px-6 py-3.5">Eligibility Rule</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {refunds.map((r) => (
                  <tr key={r.refundId} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap font-mono text-xs font-semibold text-slate-900">
                      {r.refundId}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-slate-900">{r.patientName || 'Patient'}</div>
                      <div className="text-xs font-mono text-slate-400">Appt: {r.appointmentId}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap font-semibold text-slate-900">
                      LKR {r.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4 max-w-sm">
                      <span className="text-xs text-slate-600 line-clamp-1">
                        {r.policyEligibility?.ruleApplied || r.reason}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
                          r.status === 'succeeded'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : r.status === 'rejected'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right whitespace-nowrap">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedRefund(r);
                          setCustomAmount(r.policyEligibility?.eligibleAmount ?? r.amount);
                          setActionNotes('');
                        }}
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

      {/* Review Modal */}
      {selectedRefund && (
        <Modal
          isOpen={!!selectedRefund}
          onClose={() => setSelectedRefund(null)}
          title={`Refund Assessment: ${selectedRefund.refundId}`}
          description={`Patient: ${selectedRefund.patientName} | Status: ${selectedRefund.status}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 py-2">
            {/* Policy & Eligibility Breakdown */}
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-brand-600" />
                Deterministic Policy Evaluation
              </h4>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-slate-500">Original Payment:</span>
                  <div className="font-semibold text-slate-900">
                    LKR {selectedRefund.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500">Calculated Eligible Amount:</span>
                  <div className="font-bold text-emerald-600 text-sm">
                    LKR {(selectedRefund.policyEligibility?.eligibleAmount ?? selectedRefund.amount).toLocaleString(
                      undefined,
                      { minimumFractionDigits: 2 }
                    )}
                  </div>
                </div>
              </div>
              <p className="text-xs text-slate-700 bg-white p-2.5 rounded-lg border border-slate-200">
                <span className="font-semibold">Applied Rule:</span>{' '}
                {selectedRefund.policyEligibility?.ruleApplied || 'Standard Cancellation Schedule'}
              </p>
            </div>

            {/* AI Review Summary */}
            {selectedRefund.aiSummary && (
              <div className="rounded-xl border border-brand-200 bg-brand-50/50 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-brand-900">AI Risk & Narrative Analysis</span>
                  <span className="text-[11px] font-semibold text-brand-700">
                    Recommendation: {selectedRefund.aiSummary.recommendation}
                  </span>
                </div>
                <p className="text-xs text-brand-800 leading-relaxed">{selectedRefund.aiSummary.summary}</p>
              </div>
            )}

            {/* Admin Actions */}
            {selectedRefund.status === 'requested' || selectedRefund.status === 'under_review' ? (
              <div className="pt-3 border-t border-slate-100 flex justify-end gap-3">
                <Button
                  variant="danger"
                  onClick={() => setIsRejectOpen(true)}
                  disabled={approveMutation.isPending || rejectMutation.isPending}
                >
                  Reject Request
                </Button>
                <Button
                  variant="primary"
                  onClick={() => setIsApproveOpen(true)}
                  disabled={approveMutation.isPending || rejectMutation.isPending}
                >
                  Authorize Stripe Refund
                </Button>
              </div>
            ) : (
              <div className="pt-3 border-t border-slate-100 flex justify-end">
                <Button variant="secondary" onClick={() => setSelectedRefund(null)}>
                  Close
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Approve Confirmation Modal */}
      {selectedRefund && isApproveOpen && (
        <Modal
          isOpen={isApproveOpen}
          onClose={() => setIsApproveOpen(false)}
          title="Confirm Refund Approval"
          description={`Execute refund for ${selectedRefund.refundId}`}
          maxWidth="md"
        >
          <div className="space-y-4 py-2 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Approved Amount (LKR)</label>
              <input
                type="number"
                value={customAmount}
                onChange={(e) => setCustomAmount(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-800 font-semibold focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Reviewer Justification Note</label>
              <textarea
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="Audit explanation for executing this refund..."
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-800 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsApproveOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                isLoading={approveMutation.isPending}
                onClick={() =>
                  approveMutation.mutate({
                    refundId: selectedRefund.refundId,
                    amount: typeof customAmount === 'number' ? customAmount : undefined,
                    notes: actionNotes,
                  })
                }
              >
                Execute Refund
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Reject Reason Modal */}
      {selectedRefund && isRejectOpen && (
        <Modal
          isOpen={isRejectOpen}
          onClose={() => setIsRejectOpen(false)}
          title="Reject Refund Request"
          description="A mandatory reason is required for audit history."
          maxWidth="md"
        >
          <div className="space-y-4 py-2 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Rejection Reason</label>
              <textarea
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="Explain why this refund is ineligible under platform policies..."
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-800 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsRejectOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                disabled={!actionNotes.trim()}
                isLoading={rejectMutation.isPending}
                onClick={() =>
                  rejectMutation.mutate({
                    refundId: selectedRefund.refundId,
                    reason: actionNotes.trim(),
                  })
                }
              >
                Confirm Rejection
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
