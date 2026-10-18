import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ShieldCheck, Lock, Mail, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/authApi';
import { getErrorMessage } from '../api/client';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid administrative email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

type LoginFormData = z.infer<typeof loginSchema>;

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const queryParams = new URLSearchParams(location.search);
  const sessionExpired = queryParams.get('expired') === '1';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    setServerError(null);
    try {
      const res = await authApi.login(data.email, data.password);
      if (res.user.role !== 'ADMIN') {
        setServerError('Access denied: You must hold the ADMIN role to access this portal.');
        return;
      }
      login(res.accessToken, res.user, res.refreshToken);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      setServerError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4 py-12 sm:px-6 lg:px-8">
      {/* Subtle radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-teal-900/20 via-slate-900 to-slate-950 pointer-events-none" />

      <div className="relative w-full max-w-md space-y-8 rounded-3xl border border-slate-800 bg-slate-900/90 p-8 shadow-2xl backdrop-blur-xl sm:p-10">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-500 text-white shadow-lg shadow-teal-500/30">
            <ShieldCheck className="h-8 w-8" />
          </div>
          <h2 className="mt-5 text-2xl font-bold tracking-tight text-white">MediConnect Admin</h2>
          <p className="mt-2 text-xs text-slate-400">
            Secure clinical administration and operations console
          </p>
        </div>

        {/* Notices */}
        {sessionExpired && (
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3.5 text-xs text-amber-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
            <span>Your administrative session has expired. Please authenticate again.</span>
          </div>
        )}

        {serverError && (
          <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3.5 text-xs text-rose-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{serverError}</span>
          </div>
        )}

        {/* Form */}
        <form className="mt-8 space-y-5" onSubmit={handleSubmit(onSubmit)}>
          <div>
            <Input
              label="Administrative Email"
              type="email"
              autoComplete="email"
              placeholder="admin@mediconnect.lk"
              leftIcon={<Mail className="w-4 h-4" />}
              error={errors.email?.message}
              className="bg-slate-950/60 border-slate-700 text-white placeholder-slate-500 focus:border-teal-400"
              {...register('email')}
            />
          </div>

          <div>
            <Input
              label="Security Password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••••••"
              leftIcon={<Lock className="w-4 h-4" />}
              error={errors.password?.message}
              className="bg-slate-950/60 border-slate-700 text-white placeholder-slate-500 focus:border-teal-400"
              {...register('password')}
            />
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold"
              isLoading={isLoading}
            >
              Sign In to Console
            </Button>
          </div>
        </form>

        <div className="border-t border-slate-800/80 pt-4 text-center">
          <p className="text-[11px] text-slate-500">
            Protected by role-based access control and strict JWT signature verification.
          </p>
        </div>
      </div>
    </div>
  );
};
