import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/authApi';
import { Button } from '../components/common/Button';
import { Shield, Server, CheckCircle2, XCircle, LogOut, RefreshCw } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { admin, logout } = useAuth();
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const checkConnection = async () => {
    setIsChecking(true);
    try {
      const res = await authApi.checkHealth();
      setHealthStatus(`Connected: ${res.status || 'OK'}`);
    } catch {
      setHealthStatus('Connection Error: Backend unreachable');
    } finally {
      setIsChecking(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Admin Profile & System Settings
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Inspect your authenticated administrator credentials, active session parameters, and backend health.
        </p>
      </div>

      {/* Administrator Profile Card */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-600 text-white font-bold text-lg shadow-sm">
            {admin?.fullName ? admin.fullName.charAt(0).toUpperCase() : 'A'}
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">{admin?.fullName || 'Administrator'}</h2>
            <p className="text-xs text-slate-400">{admin?.email}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">Security Role</span>
            <p className="font-bold text-purple-700 mt-0.5">{admin?.role || 'ADMIN'}</p>
          </div>

          <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">Account Status</span>
            <p className="font-bold text-emerald-700 mt-0.5">{admin?.accountStatus || 'ACTIVE'}</p>
          </div>

          <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">User Identifier</span>
            <p className="font-mono text-[11px] text-slate-700 mt-0.5 select-all">{admin?.id}</p>
          </div>

          <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-100">
            <span className="text-[10px] uppercase font-bold text-slate-400">Session Storage Mode</span>
            <p className="font-medium text-slate-700 mt-0.5">Isolated Browser Session (sessionStorage)</p>
          </div>
        </div>

        <div className="pt-2">
          <Button variant="danger" size="sm" onClick={logout} leftIcon={<LogOut className="w-4 h-4" />}>
            Sign Out of Administrative Console
          </Button>
        </div>
      </div>

      {/* Backend Integration Diagnostics */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-sky-50 text-sky-600">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">FastAPI Backend Connection</h3>
              <p className="text-xs text-slate-400">Endpoint: {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'}</p>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={checkConnection}
            isLoading={isChecking}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Test Connection
          </Button>
        </div>

        {healthStatus && (
          <div
            className={`flex items-center gap-2 rounded-xl p-3 text-xs font-semibold ${
              healthStatus.includes('Connected')
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-rose-50 text-rose-800 border border-rose-200'
            }`}
          >
            {healthStatus.includes('Connected') ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            ) : (
              <XCircle className="w-4 h-4 text-rose-600" />
            )}
            <span>{healthStatus}</span>
          </div>
        )}
      </div>

      {/* Security Architecture Summary */}
      <div className="rounded-2xl border border-slate-200/80 bg-slate-900 text-white p-6 shadow-sm space-y-3">
        <div className="flex items-center gap-2 text-teal-400">
          <Shield className="w-5 h-5" />
          <h3 className="text-sm font-bold text-white">Production Security Safeguards</h3>
        </div>
        <ul className="text-xs text-slate-300 space-y-2 list-disc list-inside">
          <li>All endpoints protected by server-side FastAPI <code className="text-teal-300">require_admin</code> dependencies.</li>
          <li>Least-privilege API queries omit password hashes and confidential medical records.</li>
          <li>Verification documents are served through authenticated streaming routes, avoiding raw disk exposure.</li>
          <li>Sensitive long-lived credentials are never written to unencrypted persistent client storage.</li>
        </ul>
      </div>
    </div>
  );
};
