import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios, { AxiosError, AxiosHeaders, InternalAxiosRequestConfig } from 'axios';
import { apiClient, AUTH_REFRESH_KEY, AUTH_TOKEN_KEY, AUTH_USER_KEY } from '../api/client';

/**
 * Phase 05: short-lived access tokens are refreshed once on 401 (single flight, because the backend revokes a
 * session when a used refresh token is replayed), the original request is retried, and a failed refresh ends the
 * session.
 */
function unauthorized(config: InternalAxiosRequestConfig) {
  return Promise.reject(
    new AxiosError('Unauthorized', '401', config, {}, {
      status: 401, statusText: 'Unauthorized', headers: {}, config, data: { detail: 'Access token has expired.' },
    })
  );
}

describe('Phase 05 admin session refresh', () => {
  const originalAdapter = apiClient.defaults.adapter;

  beforeEach(() => {
    sessionStorage.setItem(AUTH_TOKEN_KEY, 'old-access');
    sessionStorage.setItem(AUTH_REFRESH_KEY, 'refresh-1');
    sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify({ role: 'ADMIN' }));
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it('refreshes once for concurrent 401s and retries each request with the new token', async () => {
    const seen: string[] = [];
    apiClient.defaults.adapter = async (config) => {
      const auth = String((config.headers as AxiosHeaders).get?.('Authorization') ?? config.headers?.Authorization);
      seen.push(auth);
      if (auth === 'Bearer old-access') return unauthorized(config);
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
    };
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({
      data: { accessToken: 'new-access', refreshToken: 'refresh-2' },
    });

    const [a, b] = await Promise.all([apiClient.get('/admin/users'), apiClient.get('/admin/payments')]);
    expect(a.data.ok && b.data.ok).toBe(true);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(refresh.mock.calls[0][1]).toEqual({ refreshToken: 'refresh-1' });
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBe('new-access');
    expect(sessionStorage.getItem(AUTH_REFRESH_KEY)).toBe('refresh-2');
    expect(seen.filter((h) => h === 'Bearer new-access')).toHaveLength(2);
  });

  it('ends the session when the refresh token is rejected', async () => {
    apiClient.defaults.adapter = async (config) => unauthorized(config);
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('401'));
    await expect(apiClient.get('/admin/users')).rejects.toBeTruthy();
    expect(sessionStorage.getItem(AUTH_TOKEN_KEY)).toBeNull();
    expect(sessionStorage.getItem(AUTH_REFRESH_KEY)).toBeNull();
  });
});
