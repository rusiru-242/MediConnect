import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Stethoscope, Star } from 'lucide-react';
import { doctorsApi } from '../api/doctorsApi';
import { StatusBadge } from '../components/common/StatusBadge';
import { Pagination } from '../components/common/Pagination';
import { SearchBar } from '../components/common/SearchBar';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { getErrorMessage } from '../api/client';

export const DoctorsPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [specialtyFilter, setSpecialtyFilter] = useState('ALL');

  const {
    data: doctorsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['doctors-directory', page, searchTerm, statusFilter, specialtyFilter],
    queryFn: () =>
      doctorsApi.listDoctors({
        page,
        pageSize: 15,
        search: searchTerm,
        status: statusFilter,
        specialty: specialtyFilter,
      }),
  });

  const doctors = doctorsData?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Doctors Directory</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Registered medical specialists and clinical performance overview.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs">
        <SearchBar
          placeholder="Search by name, email, specialty..."
          value={searchTerm}
          onChange={(v) => {
            setSearchTerm(v);
            setPage(1);
          }}
        />

        <div className="flex items-center gap-3">
          <select
            value={specialtyFilter}
            onChange={(e) => {
              setSpecialtyFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Specialties</option>
            <option value="Cardiology">Cardiology</option>
            <option value="General Medicine">General Medicine</option>
            <option value="Pediatrics">Pediatrics</option>
            <option value="Neurology">Neurology</option>
            <option value="Dermatology">Dermatology</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="ALL">All Verification Statuses</option>
            <option value="APPROVED">Approved Only</option>
            <option value="PENDING">Pending Only</option>
            <option value="REJECTED">Rejected Only</option>
          </select>
        </div>
      </div>

      {/* Directory Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : error ? (
          <ErrorState
            title="Failed to load doctors"
            message={getErrorMessage(error)}
            onRetry={refetch}
          />
        ) : doctors.length === 0 ? (
          <EmptyState
            title="No doctors found"
            description="No practitioners match your current search or filter criteria."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Doctor</th>
                  <th className="px-6 py-3.5">Specialty</th>
                  <th className="px-6 py-3.5">Registration</th>
                  <th className="px-6 py-3.5">Clinic / Hospital</th>
                  <th className="px-6 py-3.5">Experience</th>
                  <th className="px-6 py-3.5">Rating</th>
                  <th className="px-6 py-3.5">Verification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {doctors.map((doc) => (
                  <tr key={doc.doctorProfileId} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-50 text-teal-600 font-bold shrink-0">
                          <Stethoscope className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">{doc.fullName}</p>
                          <p className="text-[11px] text-slate-400">{doc.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 font-medium text-slate-700">{doc.specialty}</td>
                    <td className="px-6 py-4 font-mono text-[11px] text-slate-600">
                      {doc.medicalRegistrationNumber}
                    </td>
                    <td className="px-6 py-4 text-slate-600">{doc.hospitalOrClinic}</td>
                    <td className="px-6 py-4 text-slate-600">{doc.experienceYears} Years</td>
                    <td className="px-6 py-4">
                      {doc.averageRating ? (
                        <div className="flex items-center gap-1 font-semibold text-amber-600">
                          <Star className="w-3.5 h-3.5 fill-current" />
                          <span>{doc.averageRating.toFixed(1)}</span>
                          <span className="text-[10px] text-slate-400 font-normal">
                            ({doc.totalReviews})
                          </span>
                        </div>
                      ) : (
                        <span className="text-[11px] text-slate-400 italic">No reviews yet</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={doc.verificationStatus} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {doctorsData && doctorsData.totalPages > 1 && (
          <Pagination
            currentPage={page}
            totalPages={doctorsData.totalPages}
            totalItems={doctorsData.total}
            pageSize={doctorsData.pageSize}
            onPageChange={setPage}
          />
        )}
      </div>
    </div>
  );
};
