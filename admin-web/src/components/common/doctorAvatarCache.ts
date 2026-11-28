/** R02: object URLs of doctor pictures fetched in this admin session (cleared on logout). */
export const doctorAvatarCache = new Map<string, string>();

export function clearDoctorAvatarCache(): void {
  doctorAvatarCache.forEach((url) => URL.revokeObjectURL(url));
  doctorAvatarCache.clear();
}
