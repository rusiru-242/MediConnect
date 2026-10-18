import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AdminLayout } from './components/layout/AdminLayout';

// Pages
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { DoctorVerificationPage } from './pages/DoctorVerificationPage';
import { DoctorsPage } from './pages/DoctorsPage';
import { UsersPage } from './pages/UsersPage';
import { AppointmentsPage } from './pages/AppointmentsPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { ReviewsPage } from './pages/ReviewsPage';
import { ContentPage } from './pages/ContentPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { SettingsPage } from './pages/SettingsPage';
import { UnauthorizedPage } from './pages/UnauthorizedPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000,
    },
  },
});

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, admin } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 text-white">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-teal-500 border-t-transparent" />
          <p className="text-xs text-slate-400">Verifying administrative credentials...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (admin?.role !== 'ADMIN') {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />

            {/* Protected Admin Routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AdminLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="doctor-verification" element={<DoctorVerificationPage />} />
              <Route path="doctors" element={<DoctorsPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="appointments" element={<AppointmentsPage />} />
              <Route path="payments" element={<PaymentsPage />} />
              <Route path="reviews" element={<ReviewsPage />} />
              <Route path="content" element={<ContentPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
