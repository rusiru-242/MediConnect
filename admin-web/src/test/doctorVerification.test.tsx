import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DoctorVerificationPage } from '../pages/DoctorVerificationPage';
import { doctorVerificationApi } from '../api/doctorVerificationApi';

vi.mock('../api/doctorVerificationApi', () => ({
  doctorVerificationApi: {
    listApplications: vi.fn(),
    getApplicationDetail: vi.fn(),
    approveApplication: vi.fn(),
    rejectApplication: vi.fn(),
    downloadDocument: vi.fn(),
    getDocumentUrl: vi.fn(),
  },
}));

describe('Doctor Verification Management Workflow', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  it('renders pending doctor applications with approve and reject options', async () => {
    vi.mocked(doctorVerificationApi.listApplications).mockResolvedValueOnce([
      {
        doctorProfileId: 'prof_1',
        userId: 'user_1',
        fullName: 'Dr. John Doe',
        email: 'john.doe@hospital.lk',
        phone: '0771234567',
        specialty: 'Neurology',
        medicalRegistrationNumber: 'SLMC-98765',
        hospitalOrClinic: 'Colombo General Hospital',
        experienceYears: 8,
        verificationStatus: 'PENDING',
        submittedAt: '2026-10-18T08:00:00Z',
      },
    ]);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DoctorVerificationPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Doctor Verification Management')).toBeInTheDocument();
      expect(screen.getByText('Dr. John Doe')).toBeInTheDocument();
      expect(screen.getByText('SLMC-98765')).toBeInTheDocument();
      expect(screen.getByText('Colombo General Hospital')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^Approve$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^Reject$/i })).toBeInTheDocument();
    });
  });

  it('prompts confirmation and calls approveApplication', async () => {
    vi.mocked(doctorVerificationApi.listApplications).mockResolvedValueOnce([
      {
        doctorProfileId: 'prof_1',
        userId: 'user_1',
        fullName: 'Dr. Jane Smith',
        email: 'jane@clinic.lk',
        phone: '0779988776',
        specialty: 'Pediatrics',
        medicalRegistrationNumber: 'SLMC-55443',
        hospitalOrClinic: 'Lady Ridgeway Hospital',
        experienceYears: 6,
        verificationStatus: 'PENDING',
        submittedAt: '2026-10-18T08:30:00Z',
      },
    ]);

    vi.mocked(doctorVerificationApi.approveApplication).mockResolvedValueOnce({
      message: 'Doctor application approved successfully.',
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DoctorVerificationPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Dr. Jane Smith')).toBeInTheDocument();
    });

    // Click Approve button
    fireEvent.click(screen.getByRole('button', { name: /^Approve$/i }));

    // Confirm dialog should appear
    expect(screen.getByText(/Approve Medical Practitioner/i)).toBeInTheDocument();
    expect(screen.getByText(/Are you sure you want to verify Dr\. Jane Smith\?/i)).toBeInTheDocument();

    // Confirm
    fireEvent.click(screen.getByRole('button', { name: /Yes, Approve Practitioner/i }));

    await waitFor(() => {
      expect(doctorVerificationApi.approveApplication).toHaveBeenCalledWith('prof_1');
      expect(screen.getByText('Doctor application approved successfully.')).toBeInTheDocument();
    });
  });

  it('requires reason when rejecting doctor application', async () => {
    vi.mocked(doctorVerificationApi.listApplications).mockResolvedValueOnce([
      {
        doctorProfileId: 'prof_2',
        userId: 'user_2',
        fullName: 'Dr. Fraud Doctor',
        email: 'fraud@bad.lk',
        phone: '0770000000',
        specialty: 'Dermatology',
        medicalRegistrationNumber: 'SLMC-00000',
        hospitalOrClinic: 'Fake Clinic',
        experienceYears: 1,
        verificationStatus: 'PENDING',
        submittedAt: '2026-10-18T09:00:00Z',
      },
    ]);

    vi.mocked(doctorVerificationApi.rejectApplication).mockResolvedValueOnce({
      message: 'Doctor application rejected.',
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DoctorVerificationPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Dr. Fraud Doctor')).toBeInTheDocument();
    });

    // Click Reject
    fireEvent.click(screen.getByRole('button', { name: /^Reject$/i }));

    expect(screen.getByText(/Reject Doctor Application/i)).toBeInTheDocument();
    const confirmBtn = screen.getByRole('button', { name: /Confirm Rejection/i });
    expect(confirmBtn).toBeDisabled();

    // Type reason
    const textarea = screen.getByPlaceholderText(/e\.g\. SLMC registration document unreadable/i);
    fireEvent.change(textarea, { target: { value: 'Registration certificate is invalid or unverifiable.' } });

    expect(confirmBtn).not.toBeDisabled();
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(doctorVerificationApi.rejectApplication).toHaveBeenCalledWith(
        'prof_2',
        'Registration certificate is invalid or unverifiable.'
      );
    });
  });
});
