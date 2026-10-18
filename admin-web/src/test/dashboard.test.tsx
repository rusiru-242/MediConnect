import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardPage } from '../pages/DashboardPage';
import { analyticsApi } from '../api/analyticsApi';

vi.mock('../api/analyticsApi', () => ({
  analyticsApi: {
    getOverview: vi.fn(),
    getAppointments: vi.fn(),
    getPayments: vi.fn(),
  },
}));

describe('Dashboard Component & Analytics Loading', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  it('renders dashboard with real KPI metrics', async () => {
    vi.mocked(analyticsApi.getOverview).mockResolvedValueOnce({
      generatedAt: '2026-10-18T10:00:00Z',
      totals: {
        totalUsers: 150,
        totalPatients: 120,
        totalDoctors: 30,
        verifiedDoctors: 25,
        pendingDoctorApprovals: 5,
        totalAppointments: 200,
        completedAppointments: 180,
        cancelledAppointments: 20,
      },
      payments: {
        totalRevenueByCurrency: { LKR: 450000.0 },
        succeededTransactions: 180,
        failedTransactions: 5,
        pendingTransactions: 2,
      },
      recentActivity: [
        {
          type: 'DOCTOR_VERIFIED',
          description: 'Approved Dr. Silva (Cardiology)',
          timestamp: '2026-10-18T09:00:00Z',
        },
      ],
    });

    vi.mocked(analyticsApi.getAppointments).mockResolvedValueOnce({
      totalBookings: 200,
      completedBookings: 180,
      cancelledBookings: 20,
      completionRatePercent: 90,
      statusBreakdown: { COMPLETED: 180, CANCELLED: 20 },
      dailyTrends: [
        { date: '2026-10-17', count: 12 },
        { date: '2026-10-18', count: 15 },
      ],
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Platform Command Center')).toBeInTheDocument();
      expect(screen.getByText('Total Registered Patients')).toBeInTheDocument();
      expect(screen.getByText('120')).toBeInTheDocument();
      expect(screen.getByText('Verified Practitioners')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('5 Approvals Pending')).toBeInTheDocument();
      expect(screen.getByText('LKR 450,000.00')).toBeInTheDocument();
      expect(screen.getByText('Approved Dr. Silva (Cardiology)')).toBeInTheDocument();
    });
  });

  it('handles backend API errors gracefully with retry option', async () => {
    vi.mocked(analyticsApi.getOverview).mockRejectedValueOnce(
      new Error('Database cluster connection timeout')
    );

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Failed to load dashboard metrics')).toBeInTheDocument();
      expect(screen.getByText(/Could not retrieve platform analytics/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry Request/i })).toBeInTheDocument();
    });
  });
});
