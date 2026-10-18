import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

const pathNameMap: Record<string, string> = {
  dashboard: 'Dashboard',
  'doctor-verification': 'Doctor Verification',
  doctors: 'Doctors Directory',
  users: 'Patients & Users',
  appointments: 'Appointments',
  payments: 'Payments Oversight',
  reviews: 'Reviews & Moderation',
  content: 'Health Content',
  analytics: 'Platform Analytics',
  settings: 'Settings & Profile',
};

export const Breadcrumbs: React.FC = () => {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter((x) => x);

  if (pathnames.length === 0 || pathnames[0] === 'login') return null;

  return (
    <nav className="flex items-center text-xs text-slate-500 mb-6" aria-label="Breadcrumb">
      <Link to="/dashboard" className="flex items-center hover:text-slate-800 transition-colors">
        <Home className="h-3.5 w-3.5 mr-1 text-slate-400" />
        <span>Admin</span>
      </Link>
      {pathnames.map((name, index) => {
        const routeTo = `/${pathnames.slice(0, index + 1).join('/')}`;
        const isLast = index === pathnames.length - 1;
        const displayName = pathNameMap[name] || name;

        return (
          <React.Fragment key={name}>
            <ChevronRight className="h-3 w-3 mx-2 text-slate-300" />
            {isLast ? (
              <span className="font-semibold text-slate-800">{displayName}</span>
            ) : (
              <Link to={routeTo} className="hover:text-slate-800 transition-colors">
                {displayName}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};
