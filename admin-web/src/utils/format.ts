/**
 * Display helpers that never invent a value (Phase 04, P04-N03 / P3-B2).
 *
 * The backend sends null when a fee, amount or rate is unknown. Calling toLocaleString() on null crashed the
 * Appointments page; replacing it with 0 would show an invented "LKR 0.00". These helpers show "Not available".
 */
export const NOT_AVAILABLE = 'Not available';

export function isKnownNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** "LKR 2,000.00" for a known amount (0 is a real, valid amount); "Not available" otherwise. */
export function formatMoney(amount: number | null | undefined, currency?: string | null): string {
  if (!isKnownNumber(amount)) return NOT_AVAILABLE;
  const code = (currency || 'LKR').toUpperCase();
  return `${code} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** "12.5%" for a known rate; "Not available" when there was nothing to compute it from. */
export function formatPercent(rate: number | null | undefined): string {
  return isKnownNumber(rate) ? `${rate}%` : NOT_AVAILABLE;
}

export function formatCount(value: number | null | undefined): string {
  return isKnownNumber(value) ? value.toLocaleString() : NOT_AVAILABLE;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return NOT_AVAILABLE;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? NOT_AVAILABLE : d.toLocaleString();
}

/** Asia/Colombo calendar date (YYYY-MM-DD) `daysAgo` days before today. */
export function colomboDate(daysAgo = 0): string {
  const now = new Date(Date.now() - daysAgo * 86_400_000);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Colombo', year: 'numeric', month: '2-digit', day: '2-digit' })
    .format(now);
}

/** Show only the last characters of a long identifier (PaymentIntent, refund id) in tables. */
export function maskIdentifier(value: string | null | undefined, visible = 6): string {
  if (!value) return NOT_AVAILABLE;
  return value.length <= visible + 4 ? value : `${value.slice(0, 3)}…${value.slice(-visible)}`;
}
