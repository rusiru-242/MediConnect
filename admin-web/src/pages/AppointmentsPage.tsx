import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Clock, Eye } from 'lucide-react';
import { appointmentsApi } from '../api/appointmentsApi';
import { AppointmentItem } from '../types/appointment';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import { SearchBar } from '../components/common/SearchBar';
import { DateRangeFilter } from '../components/common/DateRangeFilter';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { getErrorMessage } from '../api/client';

export const AppointmentsPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [paymentStatusFilter, setPaymentStatusFilter] = useState('ALL');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedAppt, setSelectedAppt] = useState<AppointmentItem | null>(null);

  const {
    data: apptsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      'admin-appointments',
      page,
      searchTerm,
      statusFilter,
      paymentStatusFilter,
      startDate,
      endDate,
    ],
    queryFn: () =>
      appointmentsApi.listAppointments({
        page,
        pageSize: 15,
        search: searchTerm,
        status: statusFilter,
        paymentStatus: paymentStatusFilter,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
      }),
  });

  const appointments = apptsData?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Appointment Monitoring
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational booking schedule, slot holds, consultation status, and patient notes.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
        <SearchBar
          placeholder="Search patient, doctor, specialty..."
          value={searchTerm}
          onChange={(v) => {
            setSearchTerm(v);
            setPage(1);
          }}
        />

        <div className="flex flex-wrap items-center gap-3">
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

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Appointment Statuses</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="COMPLETED">Completed</option>
            <option value="PENDING">Pending</option>
            <option value="HOLD">Hold</option>
            <option value="CANCELLED">Cancelled</option>
          </select>

          <select
            value={paymentStatusFilter}
            onChange={(e) => {
              setPaymentStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Payment Statuses</option>
            <option value="PAID">Paid</option>
            <option value="UNPAID">Unpaid</option>
            <option value="FAILED">Failed</option>
            <option value="REFUNDED">Refunded</option>
          </select>
        </div>
      </div>

      {/* Appointments Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : error ? (
          <ErrorState
            title="Failed to load appointments"
            message={getErrorMessage(error)}
            onRetry={refetch}
          />
        ) : appointments.length === 0 ? (
          <EmptyState
            title="No appointments found"
            description="No scheduled consultations match your current search or date criteria."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Date & Time</th>
                  <th className="px-6 py-3.5">Patient</th>
                  <th className="px-6 py-3.5">Doctor</th>
                  <th className="px-6 py-3.5">Consultation Fee</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Payment</th>
                  <th className="px-6 py-3.5 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {appointments.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{a.appointmentDate}</div>
                      <div className="text-[11px] text-slate-400 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {a.startTime} - {a.endTime}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-800">{a.patientName}</div>
                      <div className="text-[11px] text-slate-400">{a.patientEmail}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-800">{a.doctorName}</div>
                      <div className="text-[11px] text-teal-600 font-medium">{a.doctorSpecialty}</div>
                    </td>
                    <td className="px-6 py-4 font-mono font-medium text-slate-700">
                      LKR {a.consultationFee.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={a.paymentStatus} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSelectedAppt(a)}
                        leftIcon={<Eye className="w-3.5 h-3.5" />}
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {apptsData && apptsData.totalPages > 1 && (
          <Pagination
            currentPage={page}
            totalPages={apptsData.totalPages}
            totalItems={apptsData.total}
            pageSize={apptsData.pageSize}
            onPageChange={setPage}
          />
        )}
      </div>

      {/* Appointment Detail Modal */}
      {selectedAppt && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedAppt(null)}
          title="Appointment Record Details"
          description={`ID: ${selectedAppt.id}`}
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="rounded-xl bg-slate-50 p-4 border border-slate-100 space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Date & Slot</span>
                  <p className="font-semibold text-slate-900 mt-0.5">
                    {selectedAppt.appointmentDate} ({selectedAppt.startTime} - {selectedAppt.endTime})
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Locked Fee</span>
                  <p className="font-semibold text-slate-900 mt-0.5">
                    LKR {selectedAppt.consultationFee.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Patient</span>
                  <p className="font-semibold text-slate-900 mt-0.5">{selectedAppt.patientName}</p>
                  <p className="text-[10px] text-slate-400">{selectedAppt.patientEmail}</p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Practitioner</span>
                  <p className="font-semibold text-slate-900 mt-0.5">{selectedAppt.doctorName}</p>
                  <p className="text-[10px] text-teal-600 font-medium">{selectedAppt.doctorSpecialty}</p>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Consultation Status</span>
                  <div className="mt-1">
                    <StatusBadge status={selectedAppt.status} />
                  </div>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Payment Status</span>
                  <div className="mt-1">
                    <StatusBadge status={selectedAppt.paymentStatus} />
                  </div>
                </div>
              </div>
            </div>

            {selectedAppt.patientNote && (
              <div>
                <span className="font-bold text-slate-700">Patient Booking Note:</span>
                <p className="mt-1 bg-white border border-slate-200 rounded-lg p-2.5 text-slate-600">
                  {selectedAppt.patientNote}
                </p>
              </div>
            )}

            {selectedAppt.cancellationReason && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-rose-800">
                <p className="font-bold">Cancelled by: {selectedAppt.cancelledBy || 'User'}</p>
                <p className="mt-0.5">Reason: {selectedAppt.cancellationReason}</p>
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <Button variant="outline" onClick={() => setSelectedAppt(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
