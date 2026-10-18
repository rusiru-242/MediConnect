import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UsersPage } from '../pages/UsersPage';
import { AppointmentsPage } from '../pages/AppointmentsPage';
import { ReviewsPage } from '../pages/ReviewsPage';
import { ContentPage } from '../pages/ContentPage';
import { usersApi } from '../api/usersApi';
import { appointmentsApi } from '../api/appointmentsApi';
import { reviewsApi } from '../api/reviewsApi';
import { contentApi } from '../api/contentApi';
import { AuthProvider } from '../context/AuthContext';

vi.mock('../api/usersApi', () => ({
  usersApi: {
    listUsers: vi.fn(),
    updateUserStatus: vi.fn(),
  },
}));

vi.mock('../api/appointmentsApi', () => ({
  appointmentsApi: {
    listAppointments: vi.fn(),
  },
}));

vi.mock('../api/reviewsApi', () => ({
  reviewsApi: {
    listReportedReviews: vi.fn(),
    listAllReviews: vi.fn(),
    moderateReview: vi.fn(),
    deleteReview: vi.fn(),
  },
}));

vi.mock('../api/contentApi', () => ({
  contentApi: {
    listArticles: vi.fn(),
    createArticle: vi.fn(),
    updateArticle: vi.fn(),
    publishArticle: vi.fn(),
    archiveArticle: vi.fn(),
  },
}));

describe('Admin Management Modules (Users, Appointments, Reviews, Content)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it('renders privacy-conscious user administration table with search', async () => {
    vi.mocked(usersApi.listUsers).mockResolvedValueOnce({
      items: [
        {
          id: 'u_1',
          fullName: 'Kamal Perera',
          email: 'kamal@gmail.com',
          role: 'PATIENT',
          accountStatus: 'ACTIVE',
          emailVerified: true,
          createdAt: '2026-05-10T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 15,
      totalPages: 1,
    });

    render(
      <AuthProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <UsersPage />
          </MemoryRouter>
        </QueryClientProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Patients & Platform Users')).toBeInTheDocument();
      expect(screen.getByText('Kamal Perera')).toBeInTheDocument();
      expect(screen.getByText('kamal@gmail.com')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Suspend/i })).toBeInTheDocument();
    });
  });

  it('renders appointments list with status and fee data', async () => {
    vi.mocked(appointmentsApi.listAppointments).mockResolvedValueOnce({
      items: [
        {
          id: 'appt_101',
          patientUserId: 'p_1',
          patientName: 'Nimal Bandara',
          patientEmail: 'nimal@gmail.com',
          doctorUserId: 'd_1',
          doctorName: 'Dr. Wickramasinghe',
          doctorSpecialty: 'Cardiology',
          appointmentDate: '2026-10-25',
          startTime: '10:00',
          endTime: '10:30',
          status: 'CONFIRMED',
          paymentStatus: 'PAID',
          consultationFee: 3500.0,
          createdAt: '2026-10-18T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 15,
      totalPages: 1,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AppointmentsPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Appointment Monitoring')).toBeInTheDocument();
      expect(screen.getByText('Nimal Bandara')).toBeInTheDocument();
      expect(screen.getByText('Dr. Wickramasinghe')).toBeInTheDocument();
      expect(screen.getByText('LKR 3,500.00')).toBeInTheDocument();
    });
  });

  it('renders review moderation queue and allows hiding review', async () => {
    vi.mocked(reviewsApi.listReportedReviews).mockResolvedValueOnce([
      {
        id: 'rev_1',
        doctorId: 'd_1',
        patientId: 'p_1',
        rating: 1,
        reviewText: 'Inappropriate spam promotional text',
        status: 'REPORTED',
        isReported: true,
        reportReason: 'Spam and abusive advertising',
        reportedAt: '2026-10-18T10:00:00Z',
        createdAt: '2026-10-17T10:00:00Z',
      },
    ]);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ReviewsPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Reviews & Feedback Moderation')).toBeInTheDocument();
      expect(screen.getByText(/"Inappropriate spam promotional text"/i)).toBeInTheDocument();
      expect(screen.getByText(/Spam and abusive advertising/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Hide from Public View/i })).toBeInTheDocument();
    });
  });

  it('renders health content CMS with article creation trigger', async () => {
    vi.mocked(contentApi.listArticles).mockResolvedValueOnce({
      items: [
        {
          id: 'art_1',
          title: 'Heart Health and Sodium Intake',
          slug: 'heart-health-sodium',
          summary: 'Guidelines on managing dietary sodium in Sri Lankan cooking.',
          body: 'Detailed dietary guidelines for hypertension prevention.',
          category: 'Cardiology',
          tags: ['cardio', 'diet'],
          status: 'PUBLISHED',
          readTimeMinutes: 4,
          viewCount: 150,
          bookmarkCount: 20,
          authorId: 'admin_1',
          createdAt: '2026-10-15T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 10,
      totalPages: 1,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ContentPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Health & Wellness Content CMS')).toBeInTheDocument();
      expect(screen.getByText('Heart Health and Sodium Intake')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /New Health Article/i })).toBeInTheDocument();
    });
  });
});
