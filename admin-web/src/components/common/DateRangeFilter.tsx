import React from 'react';
import { Calendar } from 'lucide-react';

export interface DateRangeFilterProps {
  startDate?: string;
  endDate?: string;
  onStartDateChange: (date: string) => void;
  onEndDateChange: (date: string) => void;
  onClear?: () => void;
}

export const DateRangeFilter: React.FC<DateRangeFilterProps> = ({
  startDate = '',
  endDate = '',
  onStartDateChange,
  onEndDateChange,
  onClear,
}) => {
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="flex items-center gap-1.5 bg-white border border-slate-300 rounded-lg px-2.5 py-1">
        <Calendar className="w-3.5 h-3.5 text-slate-400" />
        <input
          type="date"
          value={startDate}
          onChange={(e) => onStartDateChange(e.target.value)}
          className="text-slate-700 bg-transparent focus:outline-none"
        />
        <span className="text-slate-400">to</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => onEndDateChange(e.target.value)}
          className="text-slate-700 bg-transparent focus:outline-none"
        />
      </div>
      {(startDate || endDate) && onClear && (
        <button
          onClick={onClear}
          className="text-xs text-slate-500 hover:text-rose-600 underline"
        >
          Reset
        </button>
      )}
    </div>
  );
};
