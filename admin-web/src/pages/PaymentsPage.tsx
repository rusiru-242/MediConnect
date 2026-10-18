import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Eye, ShieldCheck } from 'lucide-react';
import { paymentsApi } from '../api/paymentsApi';
import { PaymentItem } from '../types/payment';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import { DateRangeFilter } from '../components/common/DateRangeFilter';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { getErrorMessage } from '../api/client';

export const PaymentsPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [currencyFilter, setCurrencyFilter] = useState('ALL');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedPayment, setSelectedPayment] = useState<PaymentItem | null>(null);

  const {
    data: paymentsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin-payments', page, statusFilter, currencyFilter, startDate, endDate],
    queryFn: () =>
      paymentsApi.listPayments({
        page,
        pageSize: 15,
        status: statusFilter,
        currency: currencyFilter,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      }),
  });

  const payments = paymentsData?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Payment & Financial Monitoring
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit Stripe webhook settlements, test/live transactions, and revenue reconciliation.
          </p>
        </div>
      </div>

      {/* Filter and Date Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
        <DateRangeFilter
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={(d) => {
            setStartDate(d);
            setPage(1);
          }}
          onEndDateChange={(d) => {
            setEndDate(d);
            setPage(1);
          }}
          onClear={() => {
            setStartDate('');
            setEndDate('');
            setPage(1);
          }}
        />

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Payment Statuses</option>
            <option value="SUCCEEDED">Succeeded</option>
            <option value="PENDING">Pending</option>
            <option value="FAILED">Failed</option>
            <option value="REFUNDED">Refunded</option>
          </select>

          <select
            value={currencyFilter}
            onChange={(e) => {
              setCurrencyFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Currencies</option>
            <option value="LKR">LKR (Sri Lanka)</option>
            <option value="USD">USD</option>
          </select>
        </div>
      </div>

      {/* Payments Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : error ? (
          <ErrorState
            title="Failed to load payments"
            message={getErrorMessage(error)}
            onRetry={refetch}
          />
        ) : payments.length === 0 ? (
          <EmptyState
            title="No payment records found"
            description="No transactions match the selected filters or date ranges."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Payment Date</th>
                  <th className="px-6 py-3.5">Patient</th>
                  <th className="px-6 py-3.5">Doctor</th>
                  <th className="px-6 py-3.5">Amount & Currency</th>
                  <th className="px-6 py-3.5">Mode</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {payments.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">
                        {new Date(p.createdAt).toLocaleDateString()}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {new Date(p.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-800">{p.patientName}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-800">{p.doctorName}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-mono font-bold text-slate-900">
                        {p.currency} {p.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {p.isTestMode ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                          TEST MODE
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          LIVE
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={p.status} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSelectedPayment(p)}
                        leftIcon={<Eye className="w-3.5 h-3.5" />}
                      >
                        Audit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {paymentsData && paymentsData.totalPages > 1 && (
          <Pagination
            currentPage={page}
            totalPages={paymentsData.totalPages}
            totalItems={paymentsData.total}
            pageSize={paymentsData.pageSize}
            onPageChange={setPage}
          />
        )}
      </div>

      {/* Payment Inspection Modal */}
      {selectedPayment && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedPayment(null)}
          title="Payment Audit Record"
          description={`Transaction ID: ${selectedPayment.id}`}
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="rounded-xl bg-slate-50 p-4 border border-slate-100 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Total Settlement</span>
                  <p className="text-base font-extrabold text-slate-900 mt-0.5">
                    {selectedPayment.currency} {selectedPayment.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Environment</span>
                  <div className="mt-1">
                    {selectedPayment.isTestMode ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800">
                        Stripe Test Key
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                        Stripe Live Key
                      </span>
                    )}
                  </div>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Patient</span>
                  <p className="font-semibold text-slate-900 mt-0.5">{selectedPayment.patientName}</p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Practitioner</span>
                  <p className="font-semibold text-slate-900 mt-0.5">{selectedPayment.doctorName}</p>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-200/60 space-y-2">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Stripe PaymentIntent</span>
                  <p className="font-mono text-[11px] text-slate-700 mt-0.5 bg-white p-2 rounded border border-slate-200 break-all select-all">
                    {selectedPayment.stripePaymentIntentId}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Linked Appointment ID</span>
                  <p className="font-mono text-[11px] text-slate-700 mt-0.5 bg-white p-2 rounded border border-slate-200 select-all">
                    {selectedPayment.appointmentId}
                  </p>
                </div>
              </div>

              {selectedPayment.paidAt && (
                <div className="text-[11px] text-emerald-700 flex items-center gap-1.5 pt-1">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Settled via Stripe Webhook at {new Date(selectedPayment.paidAt).toLocaleString()}</span>
                </div>
              )}
            </div>

            {selectedPayment.failureReason && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-rose-800">
                <span className="font-bold">Failure Reason:</span> {selectedPayment.failureReason}
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <Button variant="outline" onClick={() => setSelectedPayment(null)}>
                Close Audit View
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
