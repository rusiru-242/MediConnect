import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { LoginPage } from '../pages/LoginPage';
import { UnauthorizedPage } from '../pages/UnauthorizedPage';
import { AuthProvider } from '../context/AuthContext';
import { ProtectedRoute } from '../App';
import { authApi } from '../api/authApi';

// Mock authApi
vi.mock('../api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
    checkHealth: vi.fn(),
  },
}));

describe('Admin Authentication & Protected Routes', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('renders login form with validation fields', async () => {
    render(
      <AuthProvider>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>
    );

    expect(screen.getByText('MediConnect Admin')).toBeInTheDocument();
    expect(screen.getByLabelText(/Administrative Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Security Password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In to Console/i })).toBeInTheDocument();
  });

  it('validates invalid email format and short password', async () => {
    render(
      <AuthProvider>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>
    );

    const submitBtn = screen.getByRole('button', { name: /Sign In to Console/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Please enter a valid administrative email address/i)).toBeInTheDocument();
    });
  });

  it('rejects login when user role is not ADMIN', async () => {
    vi.mocked(authApi.login).mockResolvedValueOnce({
      accessToken: 'patient_token',
      tokenType: 'bearer',
      user: {
        id: 'patient_1',
        fullName: 'Normal Patient',
        email: 'patient@mediconnect.lk',
        role: 'PATIENT',
        accountStatus: 'ACTIVE',
        emailVerified: true,
        createdAt: '2026-01-01T00:00:00Z',
      },
    });

    render(
      <AuthProvider>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthProvider>
    );

    fireEvent.change(screen.getByLabelText(/Administrative Email/i), {
      target: { value: 'patient@mediconnect.lk' },
    });
    fireEvent.change(screen.getByLabelText(/Security Password/i), {
      target: { value: 'Password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Sign In to Console/i }));

    await waitFor(() => {
      expect(screen.getByText(/You must hold the ADMIN role/i)).toBeInTheDocument();
    });
  });

  it('renders 403 Unauthorized page with guidance', () => {
    render(
      <MemoryRouter>
        <UnauthorizedPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/403 — Unauthorized Access/i)).toBeInTheDocument();
    expect(screen.getByText(/Your user account does not possess the administrative privileges/i)).toBeInTheDocument();
  });

  it('redirects unauthenticated users in ProtectedRoute', () => {
    render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route path="/login" element={<div>Login Screen Mock</div>} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <div>Secret Dashboard Content</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );

    expect(screen.getByText('Login Screen Mock')).toBeInTheDocument();
    expect(screen.queryByText('Secret Dashboard Content')).not.toBeInTheDocument();
  });
});
