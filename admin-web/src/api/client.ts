import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Storage keys
export const AUTH_TOKEN_KEY = 'mediconnect_admin_token';
export const AUTH_USER_KEY = 'mediconnect_admin_user';

// Attach Bearer token to all outgoing requests
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to catch 401 Unauthorized sessions
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login if session expired
      sessionStorage.removeItem(AUTH_TOKEN_KEY);
      sessionStorage.removeItem(AUTH_USER_KEY);
      if (window.location.pathname !== '/login') {
        window.location.href = '/login?expired=1';
      }
    }
    return Promise.reject(error);
  }
);

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (typeof data?.detail === 'string') return data.detail;
    if (typeof data?.message === 'string') return data.message;
    if (error.message) return error.message;
  }
  if (error instanceof Error) return error.message;
  return 'An unexpected server error occurred.';
}
