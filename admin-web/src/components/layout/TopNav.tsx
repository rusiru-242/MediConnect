import React, { useState, useEffect, useRef } from 'react';
import { Menu, LogOut, Shield, ChevronDown } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Link } from 'react-router-dom';

export interface TopNavProps {
  onOpenSidebar: () => void;
}

export const TopNav: React.FC<TopNavProps> = ({ onOpenSidebar }) => {
  const { admin, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && dropdownOpen) {
        setDropdownOpen(false);
      }
    };

    if (dropdownOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [dropdownOpen]);

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200/80 bg-white/95 px-4 backdrop-blur-md sm:px-6">
      {/* Left section: mobile hamburger & system status */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open navigation menu"
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 lg:hidden focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:outline-none"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="hidden sm:flex items-center gap-2">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-teal-50 text-teal-700 border border-teal-200/60">
            Healthcare Operations Console
          </span>
        </div>
      </div>

      {/* Right section: Admin account dropdown */}
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          aria-label="Administrator profile menu"
          aria-haspopup="true"
          aria-expanded={dropdownOpen}
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-2.5 rounded-full border border-slate-200/80 bg-slate-50/50 py-1.5 pl-2 pr-3 hover:bg-slate-100 transition-colors focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:outline-none"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-teal-600 text-white text-xs font-bold">
            {admin?.fullName ? admin.fullName.charAt(0).toUpperCase() : 'A'}
          </div>
          <div className="hidden text-left sm:block">
            <p className="text-xs font-semibold text-slate-800 leading-none">
              {admin?.fullName || 'Administrator'}
            </p>
            <p className="text-[10px] text-slate-400 leading-none mt-1">{admin?.email}</p>
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
        </button>

        {dropdownOpen && (
          <div
            role="menu"
            aria-orientation="vertical"
            aria-label="Profile actions"
            className="absolute right-0 mt-2 w-56 rounded-xl border border-slate-200/80 bg-white py-1.5 shadow-xl animate-in fade-in zoom-in-95 duration-100"
          >
            <div className="border-b border-slate-100 px-4 py-2 sm:hidden">
              <p className="text-xs font-semibold text-slate-800">{admin?.fullName}</p>
              <p className="text-[10px] text-slate-400 truncate">{admin?.email}</p>
            </div>
            <Link
              to="/settings"
              role="menuitem"
              onClick={() => setDropdownOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:outline-none"
            >
              <Shield className="h-3.5 w-3.5 text-slate-400" />
              Settings & Security
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setDropdownOpen(false);
                logout();
              }}
              className="flex w-full items-center gap-2 px-4 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50 focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:outline-none"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign Out
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
