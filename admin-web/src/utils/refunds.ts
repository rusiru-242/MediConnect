import { RefundRequest } from '../types/adminWorkflow';
import { formatMoney, isKnownNumber } from './format';

/** The amount an admin may approve: never more than the policy amount or the captured payment. */
export function validateRefundAmount(value: number | '', refund: RefundRequest): string | null {
  if (value === '' || !isKnownNumber(value)) return 'Enter the amount to refund.';
  if (value <= 0) return 'The refund amount must be greater than 0.';
  const limit = refund.amount;
  if (value > limit) return `The refund cannot exceed the captured payment (${formatMoney(limit, refund.currency)}).`;
  if (Math.round(value * 100) !== value * 100) return 'Use at most two decimal places.';
  return null;
}
