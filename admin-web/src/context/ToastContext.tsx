import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
  durationMs: number;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType, durationMs?: number) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = 'info', durationMs = 4000) => {
      const id = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const newToast: ToastItem = { id, message, type, durationMs };

      setToasts((prev) => [...prev, newToast]);

      if (durationMs > 0) {
        setTimeout(() => {
          dismissToast(id);
        }, durationMs);
      }
    },
    [dismissToast]
  );

  const getToastStyles = (type: ToastType) => {
    switch (type) {
      case 'success':
        return {
          container: 'bg-emerald-50 border-emerald-200 text-emerald-900',
          icon: <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />,
          role: 'status' as const,
        };
      case 'error':
        return {
          container: 'bg-rose-50 border-rose-200 text-rose-900',
          icon: <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />,
          role: 'alert' as const,
        };
      case 'warning':
        return {
          container: 'bg-amber-50 border-amber-200 text-amber-900',
          icon: <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />,
          role: 'alert' as const,
        };
      case 'info':
      default:
        return {
          container: 'bg-teal-50 border-teal-200 text-teal-900',
          icon: <Info className="w-4 h-4 text-teal-600 shrink-0" />,
          role: 'status' as const,
        };
    }
  };

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}

      {/* Accessible Toast Container */}
      <div
        aria-label="Notifications"
        className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0"
      >
        {toasts.map((toast) => {
          const styles = getToastStyles(toast.type);
          return (
            <div
              key={toast.id}
              role={styles.role}
              aria-live="polite"
              className={`pointer-events-auto flex items-center justify-between gap-3 p-3.5 rounded-xl border shadow-lg text-xs font-medium transition-all transform animate-in fade-in slide-in-from-bottom-2 duration-200 ${styles.container}`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {styles.icon}
                <span className="truncate">{toast.message}</span>
              </div>
              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                aria-label="Dismiss notification"
                className="rounded-lg p-1 text-slate-400 hover:text-slate-700 hover:bg-black/5 transition-colors shrink-0 focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:outline-none"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    return {
      showToast: () => {},
      dismissToast: () => {},
    };
  }
  return context;
};
