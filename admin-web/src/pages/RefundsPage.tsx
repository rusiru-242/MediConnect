import React, { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { getErrorMessage } from '../api/client';
import { RefundRequest } from '../types/adminWorkflow';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { useToast } from '../context/ToastContext';
import { formatMoney, formatDateTime, isKnownNumber } from '../utils/format';
import { validateRefundAmount } from '../utils/refunds';

/**
 * Refund review (Phase 04: B15 and P3-B3).
 *
 * - Shows why each request exists (patient cancellation, doctor cancellation, doctor leave), including the
 *   doctor-created requests added in Phase 03.
 * - Amounts are in the request's own currency; the approved amount is validated against the policy amount and the
 *   captured payment before the request is sent (the backend validates again).
 * - Failed requests (for example a Stripe timeout) can be retried; the backend reuses the same idempotency key, so
 *   a retry never creates a second refund.
 * - Nothing is shown as refunded until the backend reports Stripe's result.
 */
const STATUS_FILTERS = ['ALL', 'requested', 'processing', 'failed', 'succeeded', 'rejected'] as const;
const SOURCE_FILTERS = [
  { value: 'ALL', label: 'All sources' },
  { value: 'doctor', label: 'Doctor cancellation' },
  { value: 'leave', label: 'Doctor leave' },
  { value: 'patient', label: 'Patient cancellation' },
] as const;

const SOURCE_LABEL: Record<string, string> = {
  doctor: 'Doctor cancelled',
  leave: 'Doctor leave',
  patient: 'Patient cancelled',
  admin: 'Admin',
};

const REVIEWABLE = new Set(['requested', 'under_review']);

function sourceLabel(r: RefundRequest): string {
  return (r.source && SOURCE_LABEL[r.source]) || 'Not recorded';
}

function statusClass(status: string): string {
  if (status === 'succeeded') return 'bg-emerald-50 text-emerald-700 border border-emerald-200';
  if (status === 'rejected') return 'bg-rose-50 text-rose-700 border border-rose-200';
  if (status === 'failed') return 'bg-orange-50 text-orange-700 border border-orange-200';
  if (status === 'processing' || status === 'approved') return 'bg-sky-50 text-sky-700 border border-sky-200';
  return 'bg-amber-50 text-amber-700 border border-amber-200';
}

export const RefundsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sourceFilter, setSourceFilter] = useState<string>('ALL');
  const [selectedRefund, setSelectedRefund] = useState<RefundRequest | null>(null);
  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [isRejectOpen, setIsRejectOpen] = useState(false);
  const [customAmount, setCustomAmount] = useState<number | ''>('');
  const [actionNotes, setActionNotes] = useState('');

  const { data: refundsData, isLoading, error, refetch } = useQuery({
    queryKey: ['refund-requests', statusFilter, sourceFilter],
    queryFn: () => adminWorkflowApi.listRefunds({ status: statusFilter, source: sourceFilter, pageSize: 50 }),
  });

  const closeAll = () => {
    setIsApproveOpen(false);
    setIsRejectOpen(false);
    setSelectedRefund(null);
    queryClient.invalidateQueries({ queryKey: ['refund-requests'] });
  };

  const approveMutation = useMutation({
    mutationFn: ({ refundId, amount, notes }: { refundId: string; amount?: number; notes?: string }) =>
      adminWorkflowApi.approveRefund(refundId, amount, notes),
    onSuccess: (data) => {
      // The message comes from the backend and states Stripe's actual result (succeeded or pending).
      showToast(data.message || `Refund ${data.status}.`, data.status === 'succeeded' ? 'success' : 'info');
      closeAll();
    },
    onError: (err: unknown) => {
      showToast(getErrorMessage(err) || 'Failed to approve refund.', 'error');
      queryClient.invalidateQueries({ queryKey: ['refund-requests'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ refundId, reason }: { refundId: string; reason: string }) =>
      adminWorkflowApi.rejectRefund(refundId, reason),
    onSuccess: (data) => {
      showToast(data.message || 'Refund request rejected.', 'success');
      closeAll();
    },
    onError: (err: unknown) => {
      showToast(getErrorMessage(err) || 'Failed to reject refund.', 'error');
      queryClient.invalidateQueries({ queryKey: ['refund-requests'] });
    },
  });

  const refunds = refundsData?.items || [];
  const busy = approveMutation.isPending || rejectMutation.isPending;
  // Synchronous guard: a double click sends two clicks before the button re-renders as disabled (P04-N23). The
  // backend also allows only one approval to claim a request; this keeps the UI from sending the second one.
  const inFlight = useRef(false);
  const once = (fire: (done: () => void) => void) => {
    if (inFlight.current) return;
    inFlight.current = true;
    fire(() => {
      inFlight.current = false;
    });
  };
  const amountError = selectedRefund ? validateRefundAmount(customAmount, selectedRefund) : null;

  const openReview = (r: RefundRequest) => {
    setSelectedRefund(r);
    setCustomAmount(r.approvedAmount ?? r.policyEligibility?.eligibleAmount ?? r.amount);
    setActionNotes('');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Refund Review</h1>
          <p className="mt-1 text-sm text-slate-500">
            Refund requests from patient cancellations, doctor cancellations and doctor leave. Amounts follow the
            existing cancellation policy; money moves only after an administrator approves and Stripe confirms.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((st) => (
            <button
              key={st}
              type="button"
              aria-pressed={statusFilter === st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors capitalize ${
                statusFilter === st
                  ? 'bg-brand-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {st === 'ALL' ? 'All' : st}
            </button>
          ))}
          <select
            aria-label="Refund source"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700"
          >
            {SOURCE_FILTERS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} />
          </div>
        ) : error ? (
          <ErrorState title="Failed to load refund requests" message={getErrorMessage(error)} onRetry={refetch} />
        ) : refunds.length === 0 ? (
          <div className="py-12">
            <EmptyState title="No refund requests" description="No refund requests match the selected filters." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3.5">Refund ID</th>
                  <th className="px-4 py-3.5">Source</th>
                  <th className="px-4 py-3.5">Patient</th>
                  <th className="px-4 py-3.5">Paid</th>
                  <th className="px-4 py-3.5">Policy amount</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {refunds.map((r) => (
                  <tr key={r.refundId} className="hover:bg-slate-50/70 transition-colors" data-testid={`refund-row-${r.refundId}`}>
                    <td className="px-4 py-4 whitespace-nowrap font-mono text-xs font-semibold text-slate-900">
                      {r.refundId}
                      <div className="text-[10px] font-normal text-slate-400">{formatDateTime(r.createdAt)}</div>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                          r.source === 'doctor' || r.source === 'leave'
                            ? 'bg-violet-50 text-violet-700 border border-violet-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {sourceLabel(r)}
                      </span>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap">
                      <div className="font-medium text-slate-900">{r.patientName || 'Patient'}</div>
                      <div className="text-xs font-mono text-slate-400">Appt: {r.appointmentId}</div>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap font-semibold text-slate-900">{formatMoney(r.amount, r.currency)}</td>
                    <td className="px-4 py-4 whitespace-nowrap">
                      {formatMoney(r.policyEligibility?.eligibleAmount, r.currency)}
                      {isKnownNumber(r.refundedAmount) && (
                        <div className="text-[11px] text-emerald-700">Refunded {formatMoney(r.refundedAmount, r.currency)}</div>
                      )}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${statusClass(r.status)}`}>
                        {r.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right whitespace-nowrap">
                      <Button variant="outline" size="sm" onClick={() => openReview(r)}>
                        {REVIEWABLE.has(r.status) ? 'Review' : r.status === 'failed' ? 'Review / retry' : 'View'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedRefund && !isApproveOpen && !isRejectOpen && (
        <Modal
          isOpen={!!selectedRefund}
          onClose={() => setSelectedRefund(null)}
          title={`Refund ${selectedRefund.refundId}`}
          description={`${sourceLabel(selectedRefund)} • Status: ${selectedRefund.status.replace('_', ' ')}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 py-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-brand-600" />
                Existing refund policy (rule-based)
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-slate-500">Captured payment</span>
                  <div className="font-semibold text-slate-900">{formatMoney(selectedRefund.amount, selectedRefund.currency)}</div>
                </div>
                <div>
                  <span className="text-slate-500">Policy amount</span>
                  <div className="font-bold text-emerald-700 text-sm">
                    {formatMoney(selectedRefund.policyEligibility?.eligibleAmount, selectedRefund.currency)}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500">Refunded so far</span>
                  <div className="font-semibold text-slate-900">
                    {isKnownNumber(selectedRefund.refundedAmount)
                      ? formatMoney(selectedRefund.refundedAmount, selectedRefund.currency)
                      : 'Nothing refunded'}
                  </div>
                </div>
              </div>
              <p className="text-xs text-slate-700 bg-white p-2.5 rounded-lg border border-slate-200">
                <span className="font-semibold">Rule applied:</span>{' '}
                {selectedRefund.policyEligibility?.ruleApplied || 'Not recorded'}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 p-4 text-xs space-y-1.5">
              <p>
                <span className="font-semibold text-slate-700">Cancelled by:</span>{' '}
                {selectedRefund.cancelledBy || 'Not recorded'}
              </p>
              <p>
                <span className="font-semibold text-slate-700">Reason given:</span>{' '}
                {selectedRefund.cancellationReason || selectedRefund.reason || 'Not recorded'}
              </p>
              {selectedRefund.reviewNotes && (
                <p>
                  <span className="font-semibold text-slate-700">Reviewer note:</span> {selectedRefund.reviewNotes}
                </p>
              )}
              {selectedRefund.failureReason && (
                <p className="text-orange-700">
                  <span className="font-semibold">Last Stripe error:</span> {selectedRefund.failureReason}. No money was
                  recorded as refunded; retrying uses the same idempotency key.
                </p>
              )}
              {selectedRefund.stripeRefundId && (
                <p className="font-mono text-[11px] text-slate-500">Stripe refund: {selectedRefund.stripeRefundId}</p>
              )}
            </div>

            {selectedRefund.aiSummary && (
              <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-1">
                <span className="text-xs font-bold text-slate-700">Rule-based summary (not AI-generated)</span>
                <p className="text-xs text-slate-600 leading-relaxed">{selectedRefund.aiSummary.summary}</p>
              </div>
            )}

            {REVIEWABLE.has(selectedRefund.status) || selectedRefund.status === 'failed' ? (
              <div className="pt-3 border-t border-slate-100 flex flex-wrap justify-end gap-3">
                {REVIEWABLE.has(selectedRefund.status) && (
                  <Button variant="danger" onClick={() => setIsRejectOpen(true)} disabled={busy}>
                    Reject request
                  </Button>
                )}
                <Button variant="primary" onClick={() => setIsApproveOpen(true)} disabled={busy}>
                  {selectedRefund.status === 'failed' ? 'Retry Stripe refund' : 'Approve refund'}
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

      {selectedRefund && isApproveOpen && (
        <Modal
          isOpen={isApproveOpen}
          onClose={() => setIsApproveOpen(false)}
          title="Confirm refund"
          description={`This sends a refund to Stripe for ${selectedRefund.refundId}.`}
          maxWidth="md"
        >
          <div className="space-y-4 py-2 text-xs">
            <div>
              <label htmlFor="refund-amount" className="block font-semibold text-slate-700 mb-1">
                Amount to refund ({(selectedRefund.currency || 'LKR').toUpperCase()})
              </label>
              <input
                id="refund-amount"
                type="number"
                min={0}
                step="0.01"
                value={customAmount}
                onChange={(e) => setCustomAmount(e.target.value === '' ? '' : Number(e.target.value))}
                aria-invalid={!!amountError}
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-800 font-semibold focus:ring-1 focus:ring-brand-500"
              />
              <p className="mt-1 text-[11px] text-slate-500">
                Policy amount {formatMoney(selectedRefund.policyEligibility?.eligibleAmount, selectedRefund.currency)}. Changing it
                departs from the existing policy; record why below.
              </p>
              {amountError && <p className="mt-1 text-[11px] text-rose-600" role="alert">{amountError}</p>}
            </div>
            <div>
              <label htmlFor="refund-notes" className="block font-semibold text-slate-700 mb-1">Reviewer note (audit log)</label>
              <textarea
                id="refund-notes"
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-800 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsApproveOpen(false)} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="primary"
                isLoading={approveMutation.isPending}
                disabled={!!amountError || busy}
                onClick={() =>
                  once((done) =>
                    approveMutation.mutate(
                      {
                        refundId: selectedRefund.refundId,
                        amount: typeof customAmount === 'number' ? customAmount : undefined,
                        notes: actionNotes.trim() || undefined,
                      },
                      { onSettled: done }
                    )
                  )
                }
              >
                Send refund to Stripe
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {selectedRefund && isRejectOpen && (
        <Modal
          isOpen={isRejectOpen}
          onClose={() => setIsRejectOpen(false)}
          title="Reject refund request"
          description="A reason is required and is recorded in the audit log. The patient is notified."
          maxWidth="md"
        >
          <div className="space-y-4 py-2 text-xs">
            <div>
              <label htmlFor="reject-reason" className="block font-semibold text-slate-700 mb-1">Rejection reason</label>
              <textarea
                id="reject-reason"
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                className="w-full rounded-lg border border-slate-300 p-2.5 text-xs text-slate-800 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setIsRejectOpen(false)} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="danger"
                disabled={actionNotes.trim().length < 3 || busy}
                isLoading={rejectMutation.isPending}
                onClick={() =>
                  once((done) =>
                    rejectMutation.mutate({ refundId: selectedRefund.refundId, reason: actionNotes.trim() }, { onSettled: done })
                  )
                }
              >
                Confirm rejection
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
