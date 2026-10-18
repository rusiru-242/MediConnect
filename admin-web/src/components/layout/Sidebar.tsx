import React, { useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  UserCheck,
  Stethoscope,
  Users,
  CalendarCheck,
  CreditCard,
  MessageSquareWarning,
  BookOpen,
  BarChart3,
  Settings,
  ShieldCheck,
  X,
} from 'lucide-react';

export interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const navigationItems = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Doctor Verification', href: '/doctor-verification', icon: UserCheck },
  { name: 'Doctors Directory', href: '/doctors', icon: Stethoscope },
  { name: 'Patients & Users', href: '/users', icon: Users },
  { name: 'Appointments', href: '/appointments', icon: CalendarCheck },
  { name: 'Payments Oversight', href: '/payments', icon: CreditCard },
  { name: 'Reviews & Moderation', href: '/reviews', icon: MessageSquareWarning },
  { name: 'Health Content', href: '/content', icon: BookOpen },
  { name: 'Platform Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings & Profile', href: '/settings', icon: Settings },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  // Listen for Escape key to close mobile sidebar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        aria-label="Sidebar navigation"
        className={`fixed top-0 bottom-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200/80 bg-white transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${
          isOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between px-6 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-600 text-white shadow-sm shadow-teal-500/20">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <span className="text-base font-bold tracking-tight text-slate-900">MediConnect</span>
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-teal-600">
                Administration
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 lg:hidden focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:outline-none"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav aria-label="Operations Menu" className="flex-1 overflow-y-auto px-4 py-5 space-y-1">
          <p className="px-3 text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">
            Operations Menu
          </p>
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2.5 text-xs font-semibold transition-all focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:outline-none ${
                    isActive
                      ? 'bg-teal-50 text-teal-700 shadow-xs font-bold'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={`h-4 w-4 ${isActive ? 'text-teal-600' : 'text-slate-400'}`} />
                    <span>{item.name}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Security & System Info Footer */}
        <div className="border-t border-slate-100 p-4 bg-slate-50/60">
          <div className="rounded-xl border border-slate-200/80 bg-white p-3 shadow-2xs">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-emerald-200" />
              <p className="text-[11px] font-semibold text-slate-700">Production API v1.0</p>
            </div>
            <p className="text-[10px] text-slate-400 mt-0.5">Role: Super Administrator</p>
          </div>
        </div>
      </aside>
    </>
  );
};
