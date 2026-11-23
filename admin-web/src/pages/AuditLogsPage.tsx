import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Filter,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { adminWorkflowApi } from '../api/adminWorkflowApi';
import { AdminAuditLogItem } from '../types/adminWorkflow';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';

const ACTION_TYPES = [
  'ALL',
  'DOCTOR_VERIFICATION_DECISION',
  'REFUND_APPROVAL',
  'REFUND_REJECTION',
  'REFUND_EXECUTION',
  'SUPPORT_TICKET_RESOLVED',
  'SUPPORT_RESPONSE_SENT',
  'PAYMENT_RECONCILIATION_ACTION',
  'USER_STATUS_CHANGE',
  'REPORT_GENERATED',
];

export const AuditLogsPage: React.FC = () => {
  const [actionFilter, setActionFilter] = useState<string>('ALL');
  const [selectedLog, setSelectedLog] = useState<AdminAuditLogItem | null>(null);

  const { data: logsData, isLoading } = useQuery({
    queryKey: ['admin-audit-logs', actionFilter],
    queryFn: () => adminWorkflowApi.listAuditLogs({ actionType: actionFilter, pageSize: 50 }),
  });

  const logs = logsData?.items || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Administrative Audit Trail
            </h1>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700 border border-slate-200">
              Immutable Log
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Append-only audit records of privileged doctor verifications, refunds, and support resolutions.
          </p>
        </div>

        {/* Filter Dropdown */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 focus:ring-1 focus:ring-brand-500"
          >
            {ACTION_TYPES.map((act) => (
              <option key={act} value={act}>
                {act === 'ALL' ? 'All Operations' : act.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Logs Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-12">
            <EmptyState
              title="No Audit Records"
              description="No administrative operations recorded for the selected filter."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Timestamp</th>
                  <th className="px-6 py-3.5">Actor</th>
                  <th className="px-6 py-3.5">Action & Target</th>
                  <th className="px-6 py-3.5">State Transition</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.auditId} className="hover:bg-slate-50/70 transition-colors text-xs">
                    <td className="px-6 py-4 whitespace-nowrap text-slate-500">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-semibold text-slate-900">{log.actorRole}</div>
                      <div className="font-mono text-[10px] text-slate-400">{log.actorId}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-bold text-slate-800">{log.actionType.replace(/_/g, ' ')}</div>
                      <div className="text-[11px] text-slate-500">
                        Target: <span className="font-mono">{log.targetType}/{log.targetId}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {log.previousState || log.newState ? (
                        <div className="font-mono text-[11px]">
                          <span className="text-slate-400">{log.previousState || 'none'}</span>
                          <span className="mx-1 text-slate-400">→</span>
                          <span className="font-bold text-slate-900">{log.newState}</span>
                        </div>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                          log.status === 'SUCCESS'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}
                      >
                        {log.status === 'SUCCESS' ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        {log.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right whitespace-nowrap">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedLog(log)}>
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Inspect Log Modal */}
      {selectedLog && (
        <Modal
          isOpen={!!selectedLog}
          onClose={() => setSelectedLog(null)}
          title={`Audit Event: ${selectedLog.auditId}`}
          description={`Timestamp: ${new Date(selectedLog.timestamp).toISOString()}`}
          maxWidth="lg"
        >
          <div className="space-y-3 py-2 text-xs">
            <div className="rounded-lg bg-slate-50 p-3 space-y-1.5 border border-slate-200">
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Actor:</span>
                <span className="font-mono text-slate-800">{selectedLog.actorId} ({selectedLog.actorRole})</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Action:</span>
                <span className="font-bold text-slate-900">{selectedLog.actionType}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Correlation ID:</span>
                <span className="font-mono text-slate-600">{selectedLog.correlationId || '-'}</span>
              </div>
              {selectedLog.reason && (
                <div className="pt-1.5 border-t border-slate-200">
                  <span className="text-slate-500 font-medium block mb-0.5">Decision Reason:</span>
                  <p className="text-slate-800 bg-white p-2 rounded border border-slate-200">{selectedLog.reason}</p>
                </div>
              )}
            </div>

            <div>
              <span className="font-bold uppercase tracking-wider text-slate-500 block mb-1">
                Sanitized Event Metadata (Secrets Redacted)
              </span>
              <pre className="p-3 bg-slate-900 text-emerald-400 rounded-lg overflow-x-auto text-[11px] font-mono">
                {JSON.stringify(selectedLog.metadata || {}, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <Button variant="secondary" onClick={() => setSelectedLog(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
