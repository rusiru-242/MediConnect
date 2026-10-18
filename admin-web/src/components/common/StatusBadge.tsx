import React from 'react';

export type BadgeVariant =
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'neutral'
  | 'primary';

export interface StatusBadgeProps {
  status: string;
  variant?: BadgeVariant;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, variant, className = '' }) => {
  const normalized = status.toUpperCase();

  const getVariant = (): BadgeVariant => {
    if (variant) return variant;
    switch (normalized) {
      case 'ACTIVE':
      case 'APPROVED':
      case 'CONFIRMED':
      case 'COMPLETED':
      case 'PAID':
      case 'SUCCEEDED':
      case 'PUBLISHED':
        return 'success';
      case 'PENDING':
      case 'HOLD':
      case 'REPORTED':
      case 'DRAFT':
        return 'warning';
      case 'REJECTED':
      case 'CANCELLED':
      case 'FAILED':
      case 'SUSPENDED':
      case 'DEACTIVATED':
      case 'HIDDEN':
        return 'danger';
      case 'REFUNDED':
      case 'ARCHIVED':
        return 'info';
      default:
        return 'neutral';
    }
  };

  const currentVariant = getVariant();

  const styles: Record<BadgeVariant, string> = {
    success: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    warning: 'bg-amber-50 text-amber-700 ring-amber-600/20',
    danger: 'bg-rose-50 text-rose-700 ring-rose-600/20',
    info: 'bg-sky-50 text-sky-700 ring-sky-600/20',
    primary: 'bg-teal-50 text-teal-700 ring-teal-600/20',
    neutral: 'bg-slate-50 text-slate-700 ring-slate-500/20',
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ring-1 ring-inset ${styles[currentVariant]} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70" />
      {status}
    </span>
  );
};
