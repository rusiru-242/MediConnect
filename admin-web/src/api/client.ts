import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

/**
 * Resolves and normalizes the backend API base URL.
 * Ensures the trailing `/api` prefix is present so requests to
 * `/auth/login`, `/admin/users`, etc. match backend route mount points.
 * Prevents unintentional `localhost` fallbacks in production builds.
 */
export function resolveApiBaseUrl(
  rawEnvUrl?: string,
  isProd: boolean = import.meta.env.PROD
): string {
  const envUrl = (
    rawEnvUrl ?? (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
  ).trim();

  if (envUrl) {
    const cleanUrl = envUrl.replace(/\/+$/, '');
    return cleanUrl.endsWith('/api') ? cleanUrl : `${cleanUrl}/api`;
  }

  if (isProd) {
    console.warn(
      '[MediConnect Admin] VITE_API_BASE_URL is not defined in production environment. Defaulting to relative "/api".'
    );
    return '/api';
  }

  // Development without VITE_API_BASE_URL uses the isolated local UAT backend (127.0.0.1:8001), never port 8000,
  // which is the production-like default (Phase 05, P4-B3). Set VITE_API_BASE_URL explicitly in .env.local.
  console.warn(
    '[MediConnect Admin] VITE_API_BASE_URL is not set; using the local UAT backend http://127.0.0.1:8001/api.'
  );
  return 'http://127.0.0.1:8001/api';
}

export const API_BASE_URL = resolveApiBaseUrl();

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

export const AUTH_REFRESH_KEY = 'mediconnect_admin_refresh';

/**
 * One refresh at a time (Phase 05). Access tokens are short-lived (15 minutes by default) and the backend revokes
 * a whole session when a used refresh token is presented again, so concurrent 401s must share a single refresh.
 */
let refreshInFlight: Promise<string | null> | null = null;

export function refreshAccessToken(): Promise<string | null> {
  const refreshToken = sessionStorage.getItem(AUTH_REFRESH_KEY);
  if (!refreshToken) return Promise.resolve(null);
  if (!refreshInFlight) {
    refreshInFlight = axios
      .post(`${API_BASE_URL}/auth/refresh`, { refreshToken }, { timeout: 15000 })
      .then((res) => {
        const access = res.data?.accessToken as string | undefined;
        const next = res.data?.refreshToken as string | undefined;
        if (!access || !next) return null;
        sessionStorage.setItem(AUTH_TOKEN_KEY, access);
        sessionStorage.setItem(AUTH_REFRESH_KEY, next);
        return access;
      })
      .catch(() => null)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

function endSession() {
  sessionStorage.removeItem(AUTH_TOKEN_KEY);
  sessionStorage.removeItem(AUTH_USER_KEY);
  sessionStorage.removeItem(AUTH_REFRESH_KEY);
  if (window.location.pathname !== '/login') {
    window.location.href = '/login?expired=1';
  }
}

// Response interceptor: refresh once on 401, retry the request, otherwise end the session.
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string; message?: string }>) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const url = original?.url ?? '';
    const isAuthCall = /\/auth\/(login|refresh|logout)/.test(url);
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      const token = await refreshAccessToken();
      if (token) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${token}`;
        return apiClient(original);
      }
      endSession();
    } else if (error.response?.status === 401 && !isAuthCall) {
      endSession();
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
