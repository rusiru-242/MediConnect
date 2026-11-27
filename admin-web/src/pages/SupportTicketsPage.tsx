import React, { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, Send, AlertCircle } from 'lucide-react';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { SupportTicket } from '../types/adminWorkflow';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { useToast } from '../context/ToastContext';

const STATUS_FILTERS = ['ALL', 'open', 'in_progress', 'waiting_for_user', 'resolved', 'closed'] as const;
const REPLY_STATUSES = [
  { value: 'waiting_for_user', label: 'Waiting for the requester' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
] as const;

const label = (value: string) => value.replace(/_/g, ' ');

/**
 * Customer support queue (Agent 26). Suggested replies are fixed templates chosen by keyword rules, not generated
 * text; nothing is sent until an administrator reviews, edits and sends the reply (A05).
 */
export const SupportTicketsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState<string>('');
  const [replyStatus, setReplyStatus] = useState<string>('waiting_for_user');
  // A05-BUG-011: a double click sent two requests before the button was disabled (the server kept one).
  const sending = useRef(false);

  const { data: ticketsData, isLoading } = useQuery({
    queryKey: ['support-tickets', statusFilter],
    queryFn: () => adminWorkflowApi.listTickets({ status: statusFilter, pageSize: 50 }),
  });

  // The open ticket is read fresh, so a requester's follow-up is shown even if the list is older.
  const { data: selectedTicket } = useQuery({
    queryKey: ['support-ticket', selectedTicketId],
    queryFn: () => adminWorkflowApi.getTicket(selectedTicketId as string),
    enabled: !!selectedTicketId,
  });

  const closeModal = () => {
    setSelectedTicketId(null);
    setReplyText('');
    setReplyStatus('waiting_for_user');
  };

  const replyMutation = useMutation({
    mutationFn: ({ ticketId, message, status }: { ticketId: string; message: string; status: string }) =>
      adminWorkflowApi.replyTicket(ticketId, message, status, false),
    onSettled: () => {
      sending.current = false;
    },
    onSuccess: (data) => {
      showToast(
        data.duplicate ? 'This reply was already sent; it was not sent again.' : 'Reply sent and ticket updated.',
        data.duplicate ? 'info' : 'success'
      );
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['support-tickets'] });
      queryClient.invalidateQueries({ queryKey: ['support-ticket'] });
    },
    onError: () => {
      showToast('Failed to send support reply. Please try again.', 'error');
    },
  });

  const generateDraftMutation = useMutation({
    mutationFn: (ticketId: string) => adminWorkflowApi.generateTicketDraft(ticketId),
    onSuccess: (data) => {
      setReplyText(data.draftResponse);
      showToast('Suggested reply inserted. Review and edit it before sending.', 'info');
    },
    onError: () => {
      showToast('Could not load the suggested reply.', 'error');
    },
  });

  const tickets = ticketsData?.items || [];

  const openTicket = (t: SupportTicket) => {
    setSelectedTicketId(t.ticketId);
    setReplyText('');
    setReplyStatus('waiting_for_user');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Customer Support & Ticketing</h1>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700 border border-slate-200">
              Rule-based triage
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Tickets are sorted by latest activity. Categories and suggested replies come from keyword rules and fixed
            templates; every reply is reviewed and sent by an administrator.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors capitalize ${
                statusFilter === st
                  ? 'bg-brand-600 text-white shadow-xs'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {label(st)}
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
                      <div className="text-xs text-slate-400">{t.requesterRole}</div>
                    </td>
                    <td className="px-6 py-4 max-w-sm">
                      <span className="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 uppercase mb-1">
                        {label(t.category)}
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
                          t.status === 'resolved' || t.status === 'closed'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : t.status === 'in_progress'
                            ? 'bg-brand-50 text-brand-700 border border-brand-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {label(t.status)}
                      </span>
                      {t.awaitingReplyFrom === 'support' && (
                        <span
                          data-testid={`awaiting-support-${t.ticketId}`}
                          className="ml-2 inline-flex rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-200"
                        >
                          Requester replied
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right whitespace-nowrap">
                      <Button variant="outline" size="sm" onClick={() => openTicket(t)}>
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

      {/* Ticket Response Modal */}
      {selectedTicketId && (
        <Modal
          isOpen={!!selectedTicketId}
          onClose={closeModal}
          title={`Ticket ${selectedTicketId}${selectedTicket ? `: ${selectedTicket.subject}` : ''}`}
          description={
            selectedTicket
              ? `From: ${selectedTicket.requesterName} (${selectedTicket.requesterRole}) · ${label(selectedTicket.status)}`
              : 'Loading ticket…'
          }
          maxWidth="2xl"
        >
          {!selectedTicket ? (
            <div className="p-4">
              <LoadingSkeleton rows={3} />
            </div>
          ) : (
            <div className="space-y-5 py-2">
              {selectedTicket.safetyNotice && (
                <div className="rounded-md bg-rose-50 border border-rose-200 p-2 text-xs text-rose-900">
                  <AlertCircle className="h-3.5 w-3.5 inline mr-1" />
                  Possible emergency wording. The requester was shown the emergency notice (1990). Support gives no
                  medical advice.
                </div>
              )}
              {/* Conversation Messages (plain text; never rendered as HTML) */}
              <div
                className="max-h-64 overflow-y-auto space-y-3 p-3 rounded-xl bg-slate-50 border border-slate-200"
                data-testid="ticket-thread"
              >
                {selectedTicket.messages.map((m) => (
                  <div
                    key={m.messageId}
                    className={`p-3 rounded-lg text-xs leading-relaxed ${
                      m.senderRole === 'ADMIN'
                        ? 'bg-brand-600 text-white ml-6 shadow-xs'
                        : 'bg-white text-slate-800 mr-6 border border-slate-200'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1 opacity-80 text-[10px]">
                      <span className="font-bold">
                        {m.senderName || m.senderRole} · {m.senderRole}
                      </span>
                      <span>{new Date(m.sentAt).toLocaleString()}</span>
                    </div>
                    <p className="whitespace-pre-wrap break-words">{m.message}</p>
                  </div>
                ))}
              </div>

              {/* Rule-based triage card */}
              {selectedTicket.aiDraft && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <FileText className="h-4 w-4 text-slate-600" />
                      Suggested reply (template, rule-based)
                    </span>
                    <button
                      type="button"
                      onClick={() => generateDraftMutation.mutate(selectedTicket.ticketId)}
                      disabled={generateDraftMutation.isPending}
                      className="text-[11px] font-semibold text-brand-700 hover:text-brand-900 underline"
                    >
                      Insert suggested reply
                    </button>
                  </div>
                  <p className="text-xs text-slate-700">
                    <span className="font-semibold">Summary:</span> {selectedTicket.aiDraft.issueSummary}
                  </p>
                  <p className="text-xs text-slate-700">
                    <span className="font-semibold">Suggested handling:</span>{' '}
                    {selectedTicket.aiDraft.suggestedResolution}
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
                <label htmlFor="supportReply" className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                  Reply to the requester
                </label>
                <textarea
                  id="supportReply"
                  rows={5}
                  maxLength={4000}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type your reply, or insert the suggested reply and edit it…"
                  className="w-full rounded-lg border border-slate-300 p-3 text-xs text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                <p className="text-[11px] text-slate-500">
                  Do not promise refunds, appointment changes or medical outcomes; refunds are decided in Refund
                  Management.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="replyStatus" className="text-xs font-medium text-slate-700">
                  Status after sending
                </label>
                <select
                  id="replyStatus"
                  value={replyStatus}
                  onChange={(e) => setReplyStatus(e.target.value)}
                  className="rounded-lg border border-slate-300 px-2 py-1 text-xs"
                >
                  {REPLY_STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <Button variant="secondary" onClick={closeModal}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  disabled={!replyText.trim() || replyMutation.isPending}
                  isLoading={replyMutation.isPending}
                  onClick={() => {
                    if (sending.current) return;
                    sending.current = true;
                    replyMutation.mutate({
                      ticketId: selectedTicket.ticketId,
                      message: replyText.trim(),
                      status: replyStatus,
                    });
                  }}
                  leftIcon={<Send className="h-4 w-4" />}
                >
                  Send reply
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
};
