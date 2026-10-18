import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, AlertCircle } from 'lucide-react';
import { usersApi } from '../api/usersApi';
import { UserItem } from '../types/user';
import { useAuth } from '../context/AuthContext';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import { SearchBar } from '../components/common/SearchBar';
import { Button } from '../components/common/Button';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { getErrorMessage } from '../api/client';

export const UsersPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { admin } = useAuth();
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Status toggle confirmation
  const [targetUser, setTargetUser] = useState<UserItem | null>(null);
  const [newStatus, setNewStatus] = useState<string>('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: usersData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin-users', page, searchTerm, roleFilter, statusFilter],
    queryFn: () =>
      usersApi.listUsers({
        page,
        pageSize: 15,
        search: searchTerm,
        role: roleFilter,
        status: statusFilter,
      }),
  });

  const statusMutation = useMutation({
    mutationFn: ({ userId, status }: { userId: string; status: string }) =>
      usersApi.updateUserStatus(userId, status),
    onSuccess: (data) => {
      setActionSuccess(data.message || 'User status updated.');
      setTargetUser(null);
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      queryClient.invalidateQueries({ queryKey: ['admin-overview'] });
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
    },
  });

  const handleStatusClick = (user: UserItem, targetNewStatus: string) => {
    if (user.id === admin?.id) {
      alert('Security policy: Administrators cannot modify their own account status.');
      return;
    }
    setTargetUser(user);
    setNewStatus(targetNewStatus);
    setActionError(null);
    setActionSuccess(null);
  };

  const users = usersData?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Patients & Platform Users
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Privacy-conscious user administration with least-privilege data access.
          </p>
        </div>
      </div>

      {actionSuccess && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-800">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
        <SearchBar
          placeholder="Search by full name or email address..."
          value={searchTerm}
          onChange={(v) => {
            setSearchTerm(v);
            setPage(1);
          }}
        />

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Roles</option>
            <option value="PATIENT">Patients</option>
            <option value="DOCTOR">Doctors</option>
            <option value="ADMIN">Admins</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Account Statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="SUSPENDED">Suspended</option>
            <option value="PENDING">Pending</option>
            <option value="DEACTIVATED">Deactivated</option>
          </select>
        </div>
      </div>

      {/* Users Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : error ? (
          <ErrorState
            title="Failed to load users"
            message={getErrorMessage(error)}
            onRetry={refetch}
          />
        ) : users.length === 0 ? (
          <EmptyState
            title="No users found"
            description="No user accounts match the current filter or search criteria."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">User</th>
                  <th className="px-6 py-3.5">Role</th>
                  <th className="px-6 py-3.5">Email Verified</th>
                  <th className="px-6 py-3.5">Account Status</th>
                  <th className="px-6 py-3.5">Joined Date</th>
                  <th className="px-6 py-3.5 text-right">Administrative Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => {
                  const isSelf = u.id === admin?.id;
                  return (
                    <tr key={u.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                          {u.fullName}
                          {isSelf && (
                            <span className="text-[10px] font-bold bg-teal-100 text-teal-800 px-1.5 py-0.2 rounded">
                              You
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400">{u.email}</div>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                            u.role === 'ADMIN'
                              ? 'bg-purple-50 text-purple-700 border border-purple-200'
                              : u.role === 'DOCTOR'
                              ? 'bg-teal-50 text-teal-700 border border-teal-200'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {u.emailVerified ? (
                          <span className="text-emerald-600 font-semibold flex items-center gap-1">
                            <Check className="w-3.5 h-3.5" /> Verified
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Unverified</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={u.accountStatus} />
                      </td>
                      <td className="px-6 py-4 text-slate-500">
                        {new Date(u.createdAt).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {!isSelf && (
                          <div className="flex items-center justify-end gap-1.5">
                            {u.accountStatus === 'ACTIVE' ? (
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-rose-600 hover:bg-rose-50 border-rose-200"
                                onClick={() => handleStatusClick(u, 'SUSPENDED')}
                              >
                                Suspend
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-emerald-600 hover:bg-emerald-50 border-emerald-200"
                                onClick={() => handleStatusClick(u, 'ACTIVE')}
                              >
                                Activate
                              </Button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {usersData && usersData.totalPages > 1 && (
          <Pagination
            currentPage={page}
            totalPages={usersData.totalPages}
            totalItems={usersData.total}
            pageSize={usersData.pageSize}
            onPageChange={setPage}
          />
        )}
      </div>

      {/* Confirm Status Modal */}
      {targetUser && (
        <ConfirmDialog
          isOpen={true}
          onClose={() => setTargetUser(null)}
          onConfirm={() =>
            statusMutation.mutate({ userId: targetUser.id, status: newStatus })
          }
          title={`${newStatus === 'ACTIVE' ? 'Activate' : 'Suspend'} User Account`}
          message={`Are you sure you want to change the status of ${targetUser.fullName} (${targetUser.email}) to ${newStatus}?`}
          confirmText={`Yes, ${newStatus === 'ACTIVE' ? 'Activate' : 'Suspend'}`}
          variant={newStatus === 'ACTIVE' ? 'primary' : 'danger'}
          isLoading={statusMutation.isPending}
        />
      )}
    </div>
  );
};
