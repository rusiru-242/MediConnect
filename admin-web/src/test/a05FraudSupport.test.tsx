/**
 * Agent Completion A05.
 * - Agent 25: a rule-based risk signal shows why each rule fired, its evidence and review history; decisions are
 *   human and change only the review record.
 * - Agent 26: suggested replies are labelled as templates, are inserted only on request, and are sent only by an
 *   explicit admin action with the admin's edits; a requester follow-up is flagged in the queue.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from '../context/ToastContext';
import { SupportTicket } from '../types/adminWorkflow';

const assessment = {
  assessmentId: 'FRAUD-A05SYNTH01',
  relatedAccountId: 'acct-a05',
  relatedEntityReference: 'ACCOUNT-acct-a05',
  riskScore: 25,
  riskLevel: 'MEDIUM' as const,
  triggeredRules: ['SLOT_HOARDING_ATTEMPT'],
  supportingEventReferences: ['appt1', 'appt2'],
  ruleEvidence: [
    {
      rule: 'SLOT_HOARDING_ATTEMPT',
      description: 'Several distinct appointment slots reserved and left unpaid within the observation window.',
      threshold: '4 or more distinct slots held unpaid within 24 hours (provisional)',
      observed: 4,
      references: ['appt1', 'appt2', 'appt3', 'appt4'],
      items: [
        { appointmentId: 'appt1', slot: '2026-12-04 09:00 (Asia/Colombo)', outcome: 'expired_unpaid' },
        { appointmentId: 'appt2', slot: '2026-12-04 09:30 (Asia/Colombo)', outcome: 'released_before_payment' },
      ],
    },
  ],
  explanation: 'Rule weight total 25.0/100 (MEDIUM). These are signals for human review, not a finding of fraud.',
  reviewStatus: 'AWAITING_REVIEW' as const,
  investigationNotes: [{ timestamp: '2026-11-27T10:00:00Z', decision: 'investigate', notes: 'Earlier synthetic note' }],
  createdAt: '2026-11-27T10:00:00Z',
  updatedAt: '2026-11-27T10:00:00Z',
};

vi.mock('../api/securityMonitoringApi', () => ({
  securityMonitoringApi: {
    getPlatformHealth: vi.fn().mockResolvedValue({ dependencies: [], workers: [], openFraudAssessmentsCount: 1, activeIncidentsCount: 0 }),
    getFraudAssessments: vi.fn(),
    reviewFraudAssessment: vi.fn(),
    getIncidents: vi.fn().mockResolvedValue({ items: [] }),
    getNotificationMetrics: vi.fn().mockResolvedValue({ byChannel: [], totalBacklog: 0, failureRatePercent: 0, deadLetterQueueCount: 0, notes: [] }),
    getDeadLetters: vi.fn().mockResolvedValue([]),
    getMonitoredWorkflows: vi.fn().mockResolvedValue([]),
    getAiProviderMetrics: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../api/adminWorkflowApi', () => ({
  adminWorkflowApi: { listTickets: vi.fn(), getTicket: vi.fn(), generateTicketDraft: vi.fn(), replyTicket: vi.fn() },
}));

import { securityMonitoringApi } from '../api/securityMonitoringApi';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { MonitoringPage } from '../pages/MonitoringPage';
import { SupportTicketsPage } from '../pages/SupportTicketsPage';

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

const ticket: SupportTicket = {
  id: 't1',
  ticketId: 'TCK-A05ADM01',
  requesterId: 'p1',
  requesterRole: 'PATIENT',
  requesterEmail: '',
  requesterName: 'A05 Patient',
  category: 'payment_issue',
  subject: 'Payment shows pending',
  description: 'I paid but it shows pending.',
  status: 'open',
  priority: 'high',
  awaitingReplyFrom: 'support',
  messages: [
    { messageId: 'm1', senderId: 'p1', senderRole: 'PATIENT', senderName: 'A05 Patient',
      message: '<img src=x onerror=alert(1)> I paid but it shows pending.', sentAt: '2026-11-27T09:00:00Z' },
  ],
  aiDraft: {
    ticketId: 'TCK-A05ADM01', suggestedCategory: 'payment_issue', suggestedPriority: 'high',
    issueSummary: 'Payment shows pending', suggestedResolution: 'Check the payment record.',
    draftResponse: 'Dear A05 Patient,\n\nWe have received your message.', flags: [], draftType: 'template',
  },
  createdAt: '2026-11-27T09:00:00Z',
  updatedAt: '2026-11-27T09:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('A05 Agent 25: risk signal review', () => {
  it('shows evidence, history and human decisions without presenting the signal as proof', async () => {
    vi.mocked(securityMonitoringApi.getFraudAssessments).mockResolvedValue({ items: [assessment], total: 1 });
    vi.mocked(securityMonitoringApi.reviewFraudAssessment).mockResolvedValue({ ...assessment, reviewStatus: 'DISMISSED' });
    wrap(<MonitoringPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Fraud Risk Center/ }));
    expect(screen.getByText(/not proof of fraud/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: 'Review' }));
    const modal = screen.getByTestId('fraud-review-modal');
    const evidence = within(modal).getByTestId('fraud-evidence');
    expect(evidence).toHaveTextContent('4 or more distinct slots held unpaid within 24 hours (provisional)');
    expect(evidence).toHaveTextContent('2026-12-04 09:00 (Asia/Colombo) · expired unpaid');
    expect(within(modal).getByTestId('fraud-history')).toHaveTextContent('Earlier synthetic note');
    expect(within(modal).getByText(/changes only this review record/)).toBeInTheDocument();
    for (const name of ['Dismiss (not suspicious)', 'Investigate', 'Resolve', 'Confirm finding (human decision)']) {
      expect(within(modal).getByRole('button', { name })).toBeInTheDocument();
    }
    fireEvent.click(within(modal).getByRole('button', { name: 'Dismiss (not suspicious)' }));
    expect(securityMonitoringApi.reviewFraudAssessment).not.toHaveBeenCalled(); // notes are required
    fireEvent.change(within(modal).getByRole('textbox'), { target: { value: 'Synthetic: patient explained.' } });
    fireEvent.click(within(modal).getByRole('button', { name: 'Dismiss (not suspicious)' }));
    await waitFor(() =>
      expect(securityMonitoringApi.reviewFraudAssessment).toHaveBeenCalledWith(
        'FRAUD-A05SYNTH01', 'dismiss', 'Synthetic: patient explained.'),
    );
  });
});

describe('A05 Agent 26: support replies need an explicit admin send', () => {
  it('flags the requester follow-up, labels the template, inserts it on request and sends the edited text', async () => {
    vi.mocked(adminWorkflowApi.listTickets).mockResolvedValue({ items: [ticket], total: 1, page: 1, pageSize: 50 });
    vi.mocked(adminWorkflowApi.getTicket).mockResolvedValue(ticket);
    vi.mocked(adminWorkflowApi.generateTicketDraft).mockResolvedValue(ticket.aiDraft!);
    vi.mocked(adminWorkflowApi.replyTicket).mockResolvedValue({ message: 'ok', ticketId: ticket.ticketId, status: 'waiting_for_user' });
    wrap(<SupportTicketsPage />);
    expect(await screen.findByTestId('awaiting-support-TCK-A05ADM01')).toHaveTextContent('Requester replied');
    expect(screen.queryByText('AI-Assisted')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Respond' }));
    const thread = await screen.findByTestId('ticket-thread');
    // Untrusted text is rendered as text: no <img> element is created from it.
    expect(within(thread).getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
    expect(thread.querySelector('img')).toBeNull();
    expect(screen.getByText('Suggested reply (template, rule-based)')).toBeInTheDocument();
    const box = screen.getByLabelText('Reply to the requester') as HTMLTextAreaElement;
    expect(box.value).toBe(''); // nothing is pre-filled or sent automatically
    fireEvent.click(screen.getByRole('button', { name: 'Insert suggested reply' }));
    await waitFor(() => expect(box.value).toContain('We have received your message.'));
    fireEvent.change(box, { target: { value: `${box.value}\nPlease check Payment History.` } });
    expect(adminWorkflowApi.replyTicket).not.toHaveBeenCalled();
    const send = screen.getByRole('button', { name: 'Send reply' });
    fireEvent.click(send);
    fireEvent.click(send); // A05-BUG-011: a double click sends one request
    await waitFor(() => expect(adminWorkflowApi.replyTicket).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(adminWorkflowApi.replyTicket).toHaveBeenCalledWith(
        'TCK-A05ADM01',
        'Dear A05 Patient,\n\nWe have received your message.\nPlease check Payment History.',
        'waiting_for_user',
        false,
      ),
    );
  });
});
