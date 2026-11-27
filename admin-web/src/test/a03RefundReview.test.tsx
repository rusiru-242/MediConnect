/**
 * Agent Completion A03 (A03-BUG-009): refund states that only a human can resolve are visible to administrators.
 * - requiresReview: Stripe reported the refund as failed after it had succeeded (records are not changed).
 * - stripeOutcome "uncertain": the provider did not answer the refund request; approving again is discouraged.
 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RefundsPage } from '../pages/RefundsPage';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { ToastProvider } from '../context/ToastContext';
import { RefundRequest } from '../types/adminWorkflow';

vi.mock('../api/adminWorkflowApi', () => ({
  adminWorkflowApi: { listRefunds: vi.fn(), approveRefund: vi.fn(), rejectRefund: vi.fn() },
}));

const base: RefundRequest = {
  id: 'r1',
  refundId: 'REF-A03REVIEW',
  paymentId: 'pay1',
  appointmentId: 'appt1',
  patientUserId: 'p1',
  patientName: 'A03 Patient',
  amount: 3000,
  currency: 'lkr',
  reason: 'Doctor unavailable',
  status: 'succeeded',
  policyEligibility: { eligible: true, eligibleAmount: 3000, penaltyAmount: 0, ruleApplied: 'Appointment was cancelled by the doctor; 100% full refund guaranteed.' } as RefundRequest['policyEligibility'],
  idempotencyKey: 'ref_x',
  source: 'doctor',
  refundedAmount: 3000,
  stripeRefundId: 're_a03',
  stripeRefundStatus: 'failed',
  requiresReview: true,
  reviewReason: 'Stripe reported failed after success',
  createdAt: '2026-11-27T10:00:00Z',
  updatedAt: '2026-11-27T10:00:00Z',
};

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe('A03 refund review states', () => {
  it('flags a refund Stripe failed after success, in the list and in the detail', async () => {
    vi.mocked(adminWorkflowApi.listRefunds).mockResolvedValue({ items: [base], total: 1, page: 1, pageSize: 50 });
    wrap(<RefundsPage />);
    const row = await screen.findByTestId('refund-row-REF-A03REVIEW');
    expect(within(row).getByTestId('refund-review-REF-A03REVIEW')).toHaveTextContent('Needs review: Stripe reported failed');
    fireEvent.click(within(row).getByRole('button', { name: 'View' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/has not changed any record/);
  });

  it('tells the administrator not to approve again while the outcome is uncertain', async () => {
    vi.mocked(adminWorkflowApi.listRefunds).mockResolvedValue({
      items: [{ ...base, status: 'processing', requiresReview: null, stripeRefundId: null, stripeRefundStatus: null,
                refundedAmount: null, stripeOutcome: 'uncertain', failureReason: 'APIConnectionError' }],
      total: 1, page: 1, pageSize: 50,
    });
    wrap(<RefundsPage />);
    const row = await screen.findByTestId('refund-row-REF-A03REVIEW');
    expect(within(row).getByText('Outcome being checked with Stripe')).toBeInTheDocument();
    fireEvent.click(within(row).getByRole('button', { name: 'View' }));
    expect(await screen.findByText(/Do not approve it again/)).toBeInTheDocument();
    expect(screen.queryByText(/No money was recorded as refunded/)).not.toBeInTheDocument();
  });
});
