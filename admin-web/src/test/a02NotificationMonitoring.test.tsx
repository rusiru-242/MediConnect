/**
 * A02: the notification monitoring table distinguishes delivery evidence, provider acceptance and disabled channels.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ToastProvider } from '../context/ToastContext';

vi.mock('../api/securityMonitoringApi', () => ({
  securityMonitoringApi: {
    getPlatformHealth: vi.fn().mockResolvedValue({ dependencies: [], workers: [], openFraudAssessmentsCount: 0, activeIncidentsCount: 0 }),
    getFraudAssessments: vi.fn().mockResolvedValue({ items: [] }),
    getIncidents: vi.fn().mockResolvedValue({ items: [] }),
    getNotificationMetrics: vi.fn().mockResolvedValue({
      timestamp: '2026-11-26T12:00:00Z',
      byChannel: [
        { channel: 'push', pending: 0, delivered: 0, accepted: 0, failed: 0, retryScheduled: 0, deadLettered: 0,
          skipped: 1, disabled: 7, uncertain: 0, total: 8, providerStatus: 'not_configured' },
        { channel: 'email', pending: 0, delivered: 0, accepted: 3, failed: 1, retryScheduled: 0, deadLettered: 0,
          skipped: 0, disabled: 0, uncertain: 0, total: 4, providerStatus: 'configured' },
      ],
      totalBacklog: 0,
      failureRatePercent: 25,
      deadLetterQueueCount: 0,
      notes: ['push: provider not configured; 7 disabled, 0 failed and 1 skipped. Nothing was sent on this channel.'],
    }),
    getDeadLetters: vi.fn().mockResolvedValue([]),
    getMonitoredWorkflows: vi.fn().mockResolvedValue([]),
    getAiProviderMetrics: vi.fn().mockResolvedValue([]),
  },
}));

import { MonitoringPage } from '../pages/MonitoringPage';

describe('A02 notification monitoring', () => {
  it('shows provider-accepted and disabled counts separately from delivered', async () => {
    render(
      <ToastProvider>
        <MemoryRouter>
          <MonitoringPage />
        </MemoryRouter>
      </ToastProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: /Outbox & Workflows/i }));
    const header = await screen.findByRole('columnheader', { name: 'Provider accepted' });
    const table = header.closest('table') as HTMLTableElement;
    expect(within(table).getByRole('columnheader', { name: 'Disabled' })).toBeTruthy();
    await waitFor(() => expect(within(table).getAllByRole('row').length).toBe(3));
    const [push, email] = within(table).getAllByRole('row').slice(1).map((row) =>
      within(row).getAllByRole('cell').map((cell) => cell.textContent));
    // columns: channel, provider, delivered, accepted, pending, failed, skipped, disabled
    expect(push).toEqual(['push', 'not configured', '0', '0', '0', '0', '1', '7']);
    expect(email).toEqual(['email', 'configured', '0', '3', '0', '1', '0', '0']);
    expect(screen.getByText(/Nothing was sent on this channel/)).toBeTruthy();
  });
});
