import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldX } from 'lucide-react';
import { Button } from '../components/common/Button';

export const UnauthorizedPage: React.FC = () => {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center text-center p-6">
      <div className="rounded-full bg-rose-50 p-6 text-rose-600 ring-1 ring-rose-200 mb-4">
        <ShieldX className="h-12 w-12" />
      </div>
      <h1 className="text-xl font-bold text-slate-900">403 — Unauthorized Access</h1>
      <p className="mt-2 text-xs text-slate-500 max-w-md">
        Your user account does not possess the administrative privileges required to view or execute operations on this portal.
      </p>
      <div className="mt-6">
        <Link to="/login">
          <Button variant="primary">Return to Admin Authentication</Button>
        </Link>
      </div>
    </div>
  );
};
