import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles,
  Send,
  AlertCircle,
} from 'lucide-react';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { SupportTicket } from '../types/adminWorkflow';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../context/ToastContext';

export const SupportTicketsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
  const [replyText, setReplyText] = useState<string>('');
  const [resolveTicket, setResolveTicket] = useState<boolean>(false);

  const { data: ticketsData, isLoading } = useQuery({
    queryKey: ['support-tickets', statusFilter],
    queryFn: () => adminWorkflowApi.listTickets({ status: statusFilter, pageSize: 50 }),
  });

  const replyMutation = useMutation({
    mutationFn: ({
      ticketId,
      message,
      resolve,
    }: {
      ticketId: string;
      message: string;
      resolve: boolean;
    }) => adminWorkflowApi.replyTicket(ticketId, message, undefined, resolve),
    onSuccess: () => {
      showToast('Support reply sent and ticket updated.', 'success');
      setReplyText('');
      setResolveTicket(false);
      setSelectedTicket(null);
      queryClient.invalidateQueries({ queryKey: ['support-tickets'] });
    },
    onError: () => {
      showToast('Failed to send support reply. Please try again.', 'error');
    },
  });

  const generateDraftMutation = useMutation({
    mutationFn: (ticketId: string) => adminWorkflowApi.generateTicketDraft(ticketId),
    onSuccess: (data) => {
      setReplyText(data.draftResponse);
      showToast('AI draft response generated and populated.', 'info');
    },
    onError: () => {
      showToast('Could not generate AI response draft.', 'error');
    },
  });

  const tickets = ticketsData?.items || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Customer Support & Ticketing
            </h1>
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold text-brand-700 border border-brand-200">
              AI-Assisted
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            AI-classified patient and clinician inquiries with human-authorized resolution workflows.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-2">
          {['ALL', 'open', 'in_progress', 'resolved'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors capitalize ${
                statusFilter === st
                  ? 'bg-brand-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {st.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Tickets Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} />
          </div>
        ) : tickets.length === 0 ? (
          <div className="py-12">
            <EmptyState
              title="No Support Tickets Found"
              description="No user inquiries matching the selected criteria in the system queue."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Ticket</th>
                  <th className="px-6 py-3.5">Requester</th>
                  <th className="px-6 py-3.5">Category & Subject</th>
                  <th className="px-6 py-3.5">Priority</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tickets.map((t) => (
                  <tr key={t.ticketId} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap font-mono text-xs font-semibold text-slate-900">
                      {t.ticketId}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-slate-900">{t.requesterName || 'User'}</div>
                      <div className="text-xs text-slate-400">{t.requesterEmail}</div>
                    </td>
                    <td className="px-6 py-4 max-w-sm">
                      <span className="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 uppercase mb-1">
                        {t.category.replace('_', ' ')}
                      </span>
                      <div className="font-semibold text-slate-800 line-clamp-1">{t.subject}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
                          t.priority === 'urgent'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : t.priority === 'high'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {t.priority}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
                          t.status === 'resolved'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : t.status === 'in_progress'
                            ? 'bg-brand-50 text-brand-700 border border-brand-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {t.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right whitespace-nowrap">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedTicket(t);
                          setReplyText(t.aiDraft?.draftResponse || '');
                        }}
                      >
                        Respond
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Ticket Response & AI Drafting Modal */}
      {selectedTicket && (
        <Modal
          isOpen={!!selectedTicket}
          onClose={() => setSelectedTicket(null)}
          title={`Ticket ${selectedTicket.ticketId}: ${selectedTicket.subject}`}
          description={`From: ${selectedTicket.requesterName} (${selectedTicket.requesterRole})`}
          maxWidth="2xl"
        >
          <div className="space-y-5 py-2">
            {/* Conversation Messages */}
            <div className="max-h-56 overflow-y-auto space-y-3 p-3 rounded-xl bg-slate-50 border border-slate-200">
              {selectedTicket.messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg text-xs leading-relaxed ${
                    m.senderRole === 'ADMIN'
                      ? 'bg-brand-600 text-white ml-6 shadow-xs'
                      : 'bg-white text-slate-800 mr-6 border border-slate-200'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1 opacity-80 text-[10px]">
                    <span className="font-bold">{m.senderName || m.senderRole}</span>
                    <span>{new Date(m.sentAt).toLocaleTimeString()}</span>
                  </div>
                  <p className="whitespace-pre-wrap">{m.message}</p>
                </div>
              ))}
            </div>

            {/* AI Assistant Suggestions Card */}
            {selectedTicket.aiDraft && (
              <div className="rounded-xl border border-brand-200 bg-brand-50/50 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-brand-900 flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4 text-brand-600" />
                    AI Support Intelligence
                  </span>
                  <button
                    type="button"
                    onClick={() => generateDraftMutation.mutate(selectedTicket.ticketId)}
                    disabled={generateDraftMutation.isPending}
                    className="text-[11px] font-semibold text-brand-700 hover:text-brand-900 underline"
                  >
                    Regenerate Draft
                  </button>
                </div>
                <p className="text-xs text-brand-800">
                  <span className="font-semibold">Summary:</span> {selectedTicket.aiDraft.issueSummary}
                </p>
                {selectedTicket.aiDraft.flags && selectedTicket.aiDraft.flags.length > 0 && (
                  <div className="rounded-md bg-amber-100 border border-amber-300 p-2 text-xs text-amber-900">
                    <AlertCircle className="h-3.5 w-3.5 inline mr-1" />
                    {selectedTicket.aiDraft.flags.join('; ')}
                  </div>
                )}
              </div>
            )}

            {/* Response Composer */}
            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                Authorized Reply Message
              </label>
              <textarea
                rows={5}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Type your response to the user or edit the AI draft..."
                className="w-full rounded-lg border border-slate-300 p-3 text-xs text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>

            {/* Resolve Checkbox */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="resolveTicket"
                checked={resolveTicket}
                onChange={(e) => setResolveTicket(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <label htmlFor="resolveTicket" className="text-xs font-medium text-slate-700">
                Mark ticket as resolved upon sending
              </label>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setSelectedTicket(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={!replyText.trim() || replyMutation.isPending}
                isLoading={replyMutation.isPending}
                onClick={() =>
                  replyMutation.mutate({
                    ticketId: selectedTicket.ticketId,
                    message: replyText.trim(),
                    resolve: resolveTicket,
                  })
                }
                leftIcon={<Send className="h-4 w-4" />}
              >
                Send Authorized Reply
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
