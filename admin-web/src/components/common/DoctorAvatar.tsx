import React, { useEffect, useState } from 'react';
import { Stethoscope } from 'lucide-react';
import { apiClient } from '../../api/client';
import { doctorAvatarCache } from './doctorAvatarCache';

/**
 * R02: a doctor's profile picture in admin views (doctor list, verification queue and application detail).
 *
 * Pictures are served only to signed-in users (`/api/profile/pictures/<userId>?v=<version>`), so they are fetched
 * through the authenticated API client and shown from an in-memory object URL. Only `/api/profile/pictures/` paths
 * are fetched; anything else, a refused request or a broken image falls back to the existing stethoscope avatar.
 * The fixed square box with object-cover keeps large images from distorting table rows. Object URLs are revoked
 * on logout (clearDoctorAvatarCache in doctorAvatarCache.ts).
 */
const cache = doctorAvatarCache;

const PICTURE_PATH = /^\/api\/profile\/pictures\/[A-Za-z0-9_-]{1,64}\?v=[A-Za-z0-9]{1,32}$/;

export const DoctorAvatar: React.FC<{ imageUrl?: string | null; name: string; size?: number }> = ({
  imageUrl,
  name,
  size = 32,
}) => {
  const valid = !!imageUrl && PICTURE_PATH.test(imageUrl);
  const [src, setSrc] = useState<string | null>(valid ? cache.get(imageUrl) ?? null : null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
    if (!valid || !imageUrl) {
      setSrc(null);
      return;
    }
    const hit = cache.get(imageUrl);
    if (hit) {
      setSrc(hit);
      return;
    }
    let cancelled = false;
    apiClient
      .get<Blob>(imageUrl.replace(/^\/api/, ''), { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return;
        const objectUrl = URL.createObjectURL(res.data);
        cache.set(imageUrl, objectUrl);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [imageUrl, valid]);

  const box = { width: size, height: size };
  if (src && !failed) {
    return (
      <img
        src={src}
        alt={`Photo of ${name}`}
        data-testid="doctor-avatar-image"
        style={box}
        className="shrink-0 rounded-full object-cover bg-slate-100"
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <div
      data-testid="doctor-avatar-fallback"
      aria-hidden="true"
      style={box}
      className="flex shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 font-bold"
    >
      <Stethoscope className="w-4 h-4" />
    </div>
  );
};
