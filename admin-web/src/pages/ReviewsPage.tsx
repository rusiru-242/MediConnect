import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Star,
  ShieldAlert,
  EyeOff,
  RotateCcw,
  AlertCircle,
  Check,
  MessageSquare,
} from 'lucide-react';
import { reviewsApi } from '../api/reviewsApi';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { getErrorMessage } from '../api/client';

export const ReviewsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'REPORTED' | 'ALL'>('REPORTED');
  const [page, setPage] = useState(1);
  const [moderationTarget, setModerationTarget] = useState<{
    id: string;
    action: 'HIDE' | 'RESTORE';
    patientName?: string;
  } | null>(null);
  const [moderationNotes, setModerationNotes] = useState('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Reported reviews query
  const {
    data: reportedReviews,
    isLoading: isReportedLoading,
    error: reportedError,
    refetch: refetchReported,
  } = useQuery({
    queryKey: ['admin-reported-reviews', page],
    queryFn: () => reviewsApi.listReportedReviews(page, 20),
    enabled: activeTab === 'REPORTED',
  });

  // All reviews query
  const {
    data: allReviewsData,
    isLoading: isAllLoading,
    error: allError,
    refetch: refetchAll,
  } = useQuery({
    queryKey: ['admin-all-reviews', page],
    queryFn: () => reviewsApi.listAllReviews({ page, pageSize: 15 }),
    enabled: activeTab === 'ALL',
  });

  // Moderate mutation
  const moderateMutation = useMutation({
    mutationFn: ({
      reviewId,
      action,
      notes,
    }: {
      reviewId: string;
      action: 'HIDE' | 'RESTORE';
      notes?: string;
    }) => reviewsApi.moderateReview(reviewId, action, notes),
    onSuccess: (data) => {
      setActionSuccess(data.message || 'Review moderation updated.');
      setModerationTarget(null);
      setModerationNotes('');
      queryClient.invalidateQueries({ queryKey: ['admin-reported-reviews'] });
      queryClient.invalidateQueries({ queryKey: ['admin-all-reviews'] });
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Reviews & Feedback Moderation
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit patient reviews, address reported inappropriate content, and enforce community safety.
          </p>
        </div>

        {/* Tab switch */}
        <div className="flex rounded-xl bg-slate-200/70 p-1 text-xs font-semibold text-slate-600">
          <button
            onClick={() => {
              setActiveTab('REPORTED');
              setPage(1);
            }}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-all ${
              activeTab === 'REPORTED'
                ? 'bg-white text-slate-900 shadow-xs font-bold'
                : 'hover:text-slate-900'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
            <span>Reported Queue</span>
          </button>
          <button
            onClick={() => {
              setActiveTab('ALL');
              setPage(1);
            }}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-all ${
              activeTab === 'ALL'
                ? 'bg-white text-slate-900 shadow-xs font-bold'
                : 'hover:text-slate-900'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>All Published Reviews</span>
          </button>
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

      {/* Main Content Area */}
      {activeTab === 'REPORTED' ? (
        <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
          {isReportedLoading ? (
            <LoadingSkeleton rows={4} />
          ) : reportedError ? (
            <ErrorState
              title="Failed to load reported reviews"
              message={getErrorMessage(reportedError)}
              onRetry={refetchReported}
            />
          ) : !reportedReviews || reportedReviews.length === 0 ? (
            <EmptyState
              title="Reported review queue is clear"
              description="No patient reviews have been reported by practitioners or system moderators."
            />
          ) : (
            <div className="divide-y divide-slate-100">
              {reportedReviews.map((r) => (
                <div key={r.id} className="p-6 space-y-3 hover:bg-slate-50/50 transition-colors">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center text-amber-500">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <Star
                            key={i}
                            className={`w-4 h-4 ${
                              i < r.rating ? 'fill-current' : 'text-slate-200'
                            }`}
                          />
                        ))}
                      </div>
                      <span className="text-xs font-bold text-slate-800">{r.rating}.0 / 5.0</span>
                      <StatusBadge status={r.status} />
                    </div>
                    <span className="text-xs text-slate-400">
                      Reported: {new Date(r.reportedAt).toLocaleDateString()}
                    </span>
                  </div>

                  <p className="text-xs text-slate-800 leading-relaxed font-medium bg-slate-50 p-3 rounded-xl border border-slate-100">
                    "{r.reviewText || 'No written commentary provided.'}"
                  </p>

                  <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3 text-xs text-amber-900">
                    <span className="font-bold">Flagged Reason:</span> {r.reportReason}
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setModerationTarget({
                          id: r.id,
                          action: 'RESTORE',
                        })
                      }
                      leftIcon={<RotateCcw className="w-3.5 h-3.5 text-emerald-600" />}
                    >
                      Dismiss Report & Restore
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() =>
                        setModerationTarget({
                          id: r.id,
                          action: 'HIDE',
                        })
                      }
                      leftIcon={<EyeOff className="w-3.5 h-3.5" />}
                    >
                      Hide from Public View
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
          {isAllLoading ? (
            <LoadingSkeleton rows={5} />
          ) : allError ? (
            <ErrorState
              title="Failed to load reviews"
              message={getErrorMessage(allError)}
              onRetry={refetchAll}
            />
          ) : !allReviewsData || allReviewsData.items.length === 0 ? (
            <EmptyState title="No reviews found" description="No platform reviews have been recorded." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-6 py-3.5">Doctor</th>
                    <th className="px-6 py-3.5">Patient</th>
                    <th className="px-6 py-3.5">Rating</th>
                    <th className="px-6 py-3.5">Commentary</th>
                    <th className="px-6 py-3.5">Status</th>
                    <th className="px-6 py-3.5 text-right">Moderation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {allReviewsData.items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-6 py-4 font-semibold text-slate-900">{item.doctorName}</td>
                      <td className="px-6 py-4 text-slate-600">{item.patientName}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-1 font-bold text-amber-600">
                          <Star className="w-3.5 h-3.5 fill-current" />
                          <span>{item.rating}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-slate-600 max-w-xs truncate">
                        {item.reviewText || <span className="italic text-slate-400">None</span>}
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-6 py-4 text-right">
                        {item.status === 'HIDDEN' ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setModerationTarget({
                                id: item.id,
                                action: 'RESTORE',
                              })
                            }
                          >
                            Restore
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-rose-600 hover:bg-rose-50"
                            onClick={() =>
                              setModerationTarget({
                                id: item.id,
                                action: 'HIDE',
                              })
                            }
                          >
                            Hide
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {allReviewsData && allReviewsData.totalPages > 1 && (
            <Pagination
              currentPage={page}
              totalPages={allReviewsData.totalPages}
              totalItems={allReviewsData.total}
              pageSize={allReviewsData.pageSize}
              onPageChange={setPage}
            />
          )}
        </div>
      )}

      {/* Moderation Notes Modal */}
      {moderationTarget && (
        <Modal
          isOpen={true}
          onClose={() => setModerationTarget(null)}
          title={`${moderationTarget.action === 'HIDE' ? 'Hide' : 'Restore'} Review`}
          description="Enforce moderation policy without silently altering patient rating star value"
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Moderation Audit Notes (Optional)
              </label>
              <textarea
                value={moderationNotes}
                onChange={(e) => setModerationNotes(e.target.value)}
                placeholder="e.g. Inappropriate language or spam detected. Hidden in compliance with community terms."
                rows={3}
                className="w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => setModerationTarget(null)}
                disabled={moderateMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant={moderationTarget.action === 'HIDE' ? 'danger' : 'primary'}
                onClick={() =>
                  moderateMutation.mutate({
                    reviewId: moderationTarget.id,
                    action: moderationTarget.action,
                    notes: moderationNotes,
                  })
                }
                isLoading={moderateMutation.isPending}
              >
                Confirm {moderationTarget.action === 'HIDE' ? 'Hide' : 'Restore'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
