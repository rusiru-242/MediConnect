// R02: doctor profile pictures in admin views are fetched with the admin session, shown in a fixed square box, and
// fall back to the neutral stethoscope avatar when missing, refused or not a MediConnect picture path.
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DoctorAvatar } from '../components/common/DoctorAvatar';
import { clearDoctorAvatarCache } from '../components/common/doctorAvatarCache';
import { apiClient } from '../api/client';

const blob = new Blob([new Uint8Array([0xff, 0xd8, 0xff])], { type: 'image/jpeg' });

describe('R02 DoctorAvatar', () => {
  beforeEach(() => {
    clearDoctorAvatarCache();
    vi.restoreAllMocks();
    let n = 0;
    globalThis.URL.createObjectURL = vi.fn(() => `blob:test-${++n}`);
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  it('shows the neutral avatar when the doctor has no picture (no request)', () => {
    const get = vi.spyOn(apiClient, 'get');
    render(<DoctorAvatar imageUrl={null} name="Dr. Synthetic" />);
    expect(screen.getByTestId('doctor-avatar-fallback')).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it('never fetches a value that is not a MediConnect picture path', () => {
    const get = vi.spyOn(apiClient, 'get');
    for (const bad of ['https://evil.example/x.jpg', '/api/admin/doctors?v=1', '/api/profile/pictures/../x?v=1', 'javascript:alert(1)']) {
      const { unmount } = render(<DoctorAvatar imageUrl={bad} name="Dr. Synthetic" />);
      expect(screen.getByTestId('doctor-avatar-fallback')).toBeInTheDocument();
      unmount();
    }
    expect(get).not.toHaveBeenCalled();
  });

  it('fetches the picture with the admin session and keeps it square without distortion', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: blob } as never);
    render(<DoctorAvatar imageUrl="/api/profile/pictures/abc123?v=f00d" name="Dr. Synthetic" size={40} />);
    const img = await screen.findByTestId('doctor-avatar-image');
    expect(get).toHaveBeenCalledWith('/profile/pictures/abc123?v=f00d', { responseType: 'blob' });
    expect(img).toHaveAttribute('alt', 'Photo of Dr. Synthetic');
    expect(img.className).toContain('object-cover');
    expect(img).toHaveStyle({ width: '40px', height: '40px' });
  });

  it('falls back when the picture is refused, and the cache is cleared on sign-out', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValueOnce(new Error('404'));
    render(<DoctorAvatar imageUrl="/api/profile/pictures/zzz?v=1" name="Dr. Synthetic" />);
    await waitFor(() => expect(screen.getByTestId('doctor-avatar-fallback')).toBeInTheDocument());

    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: blob } as never);
    const { unmount } = render(<DoctorAvatar imageUrl="/api/profile/pictures/ok?v=2" name="Dr. Two" />);
    await screen.findByTestId('doctor-avatar-image');
    unmount();
    clearDoctorAvatarCache();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-1');
  });
});
