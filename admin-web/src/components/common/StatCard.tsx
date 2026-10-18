import React from 'react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

export interface StatCardProps {
  title: string;
  value: string | number;
  change?: string;
  isPositive?: boolean;
  icon: React.ReactNode;
  subtitle?: string;
  iconBgColor?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  change,
  isPositive,
  icon,
  subtitle,
  iconBgColor = 'bg-teal-50 text-teal-600',
}) => {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</span>
        <div className={`p-2.5 rounded-xl ${iconBgColor}`}>{icon}</div>
      </div>
      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight text-slate-900">{value}</span>
        {change && (
          <span
            className={`inline-flex items-center text-xs font-semibold ${
              isPositive ? 'text-emerald-600' : 'text-rose-600'
            }`}
          >
            {isPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
            {change}
          </span>
        )}
      </div>
      {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
    </div>
  );
};
