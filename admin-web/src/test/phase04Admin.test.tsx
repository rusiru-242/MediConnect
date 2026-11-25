/**
 * Phase 04 admin regression tests (P3-B2 null fee, B15/P3-B3 refund review, truthful formatting).
 * Network calls are mocked here; the same pages were also exercised against the live UAT backend
 * (docs/uat/phase-04/evidence).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppointmentsPage } from '../pages/AppointmentsPage';
import { RefundsPage } from '../pages/RefundsPage';
import { appointmentsApi } from '../api/appointmentsApi';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { ToastProvider } from '../context/ToastContext';
import { formatMoney, formatPercent } from '../utils/format';
import { validateRefundAmount } from '../utils/refunds';
import { AppointmentItem } from '../types/appointment';
import { RefundRequest } from '../types/adminWorkflow';

vi.mock('../api/appointmentsApi', () => ({ appointmentsApi: { listAppointments: vi.fn() } }));
vi.mock('../api/adminWorkflowApi', () => ({
  adminWorkflowApi: { listRefunds: vi.fn(), approveRefund: vi.fn(), rejectRefund: vi.fn() },
}));

const base: AppointmentItem = {
  id: 'appt-null-fee',
  patientUserId: 'p1',
  patientName: 'P04 Patient',
  patientEmail: 'p04.patient@uat.mediconnect.lk',
  doctorUserId: 'd1',
  doctorName: 'Dr. P04',
  doctorSpecialty: null,
  appointmentDate: '2026-12-01',
  startTime: '09:00',
  endTime: '09:30',
  status: 'CANCELLED',
  paymentStatus: 'UNPAID',
  consultationFee: null,
  createdAt: '2026-11-20T10:00:00Z',
};

const refund: RefundRequest = {
  id: 'r1',
  refundId: 'REF-P04DOCTOR',
  paymentId: 'pay1',
  appointmentId: 'appt1',
  patientUserId: 'p1',
  patientName: 'P04 Patient',
  amount: 2000,
  currency: 'lkr',
  reason: 'Doctor unavailable',
  status: 'requested',
  policyEligibility: { eligible: true, eligibleAmount: 2000, penaltyAmount: 0, ruleApplied: 'Appointment was cancelled by the doctor; 100% full refund guaranteed.' } as RefundRequest['policyEligibility'],
  idempotencyKey: 'ref_x',
  source: 'doctor',
  cancelledBy: 'DOCTOR',
  cancellationReason: 'Doctor unavailable',
  createdAt: '2026-11-25T10:00:00Z',
  updatedAt: '2026-11-25T10:00:00Z',
};

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe('Phase 04 formatting helpers', () => {
  it('shows unknown amounts and rates as "Not available", but keeps real zeros', () => {
    expect(formatMoney(null)).toBe('Not available');
    expect(formatMoney(undefined)).toBe('Not available');
    expect(formatMoney(Number.NaN)).toBe('Not available');
    expect(formatMoney(0, 'lkr')).toBe('LKR 0.00');
    expect(formatMoney(2000, 'lkr')).toBe('LKR 2,000.00');
    expect(formatPercent(null)).toBe('Not available');
  });

  it('validates the refund amount against the captured payment', () => {
    expect(validateRefundAmount('', refund)).toMatch(/Enter the amount/);
    expect(validateRefundAmount(0, refund)).toMatch(/greater than 0/);
    expect(validateRefundAmount(2000.01, refund)).toMatch(/cannot exceed/);
    expect(validateRefundAmount(10.555, refund)).toMatch(/two decimal/);
    expect(validateRefundAmount(1600, refund)).toBeNull();
  });
});

describe('Appointments page (P3-B2)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders an appointment whose fee is null without crashing and without inventing 0.00', async () => {
    vi.mocked(appointmentsApi.listAppointments).mockResolvedValue({
      items: [base, { ...base, id: 'appt-fee', consultationFee: 2500, currency: 'LKR', status: 'CONFIRMED', paymentStatus: 'PAID', doctorSpecialty: 'Cardiology' }],
      total: 2, page: 1, pageSize: 15, totalPages: 1,
    });
    wrap(<AppointmentsPage />);
    const fees = await screen.findAllByTestId('appointment-fee');
    expect(fees.map((f) => f.textContent)).toEqual(['Not available', 'LKR 2,500.00']);
    expect(screen.getByText('Specialty not recorded')).toBeInTheDocument();
    expect(screen.queryByText(/LKR 0\.00/)).not.toBeInTheDocument();
    expect(screen.queryByText(/video/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /Inspect/i })[0]);
    expect(await screen.findByTestId('appointment-detail-fee')).toHaveTextContent('Not available');
    expect(screen.getByText('In-person visit')).toBeInTheDocument();
  });
});

describe('Refunds page (B15 / P3-B3)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('labels doctor-initiated requests and requires a valid amount before sending to Stripe', async () => {
    vi.mocked(adminWorkflowApi.listRefunds).mockResolvedValue({ items: [refund], total: 1, page: 1, pageSize: 50 });
    vi.mocked(adminWorkflowApi.approveRefund).mockResolvedValue({ message: 'Refund of LKR 2,000.00 succeeded in Stripe.', refundId: refund.refundId, status: 'succeeded' });
    wrap(<RefundsPage />);
    const row = await screen.findByTestId('refund-row-REF-P04DOCTOR');
    expect(within(row).getByText('Doctor cancelled')).toBeInTheDocument();
    expect(within(row).getAllByText('LKR 2,000.00').length).toBeGreaterThan(0);
    fireEvent.click(within(row).getByRole('button', { name: 'Review' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve refund' }));
    const input = await screen.findByLabelText(/Amount to refund/);
    fireEvent.change(input, { target: { value: '2500' } });
    const send = screen.getByRole('button', { name: /Send refund to Stripe/ });
    expect(send).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent(/cannot exceed/);
    fireEvent.change(input, { target: { value: '2000' } });
    expect(send).not.toBeDisabled();
    fireEvent.click(send);
    await waitFor(() => expect(adminWorkflowApi.approveRefund).toHaveBeenCalledTimes(1));
    expect(vi.mocked(adminWorkflowApi.approveRefund).mock.calls[0].slice(0, 2)).toEqual(['REF-P04DOCTOR', 2000]);
  });

  it('shows an error state instead of "no requests" when loading fails, and offers retry for failed refunds', async () => {
    vi.mocked(adminWorkflowApi.listRefunds).mockRejectedValueOnce(new Error('Network Error'));
    const { unmount } = wrap(<RefundsPage />);
    expect(await screen.findByText('Failed to load refund requests')).toBeInTheDocument();
    expect(screen.queryByText('No refund requests')).not.toBeInTheDocument();
    unmount();

    vi.mocked(adminWorkflowApi.listRefunds).mockResolvedValue({
      items: [{ ...refund, status: 'failed', failureReason: 'APIConnectionError' }], total: 1, page: 1, pageSize: 50,
    });
    wrap(<RefundsPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Review / retry' }));
    expect(await screen.findByText(/same idempotency key/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry Stripe refund' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject request' })).not.toBeInTheDocument();
  });
});
