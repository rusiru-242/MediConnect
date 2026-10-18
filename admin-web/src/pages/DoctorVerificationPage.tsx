import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText,
  Eye,
  Download,
  AlertCircle,
  Check,
} from 'lucide-react';
import { doctorVerificationApi } from '../api/doctorVerificationApi';
import { DoctorApplicationSummary } from '../types/doctor';
import { StatusBadge } from '../components/common/StatusBadge';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { SearchBar } from '../components/common/SearchBar';
import { getErrorMessage } from '../api/client';
import { useToast } from '../context/ToastContext';

export const DoctorVerificationPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [statusFilter, setStatusFilter] = useState<'PENDING' | 'APPROVED' | 'REJECTED' | 'ALL'>('PENDING');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null);

  // Modals state
  const [approveDialogTarget, setApproveDialogTarget] = useState<DoctorApplicationSummary | null>(null);
  const [rejectDialogTarget, setRejectDialogTarget] = useState<DoctorApplicationSummary | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Query applications list
  const {
    data: applications,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['doctor-applications', statusFilter],
    queryFn: () => doctorVerificationApi.listApplications(statusFilter),
  });

  // Query application detail when modal is open
  const {
    data: appDetail,
    isLoading: isDetailLoading,
  } = useQuery({
    queryKey: ['doctor-application-detail', selectedAppId],
    queryFn: () => (selectedAppId ? doctorVerificationApi.getApplicationDetail(selectedAppId) : null),
    enabled: !!selectedAppId,
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (profileId: string) => doctorVerificationApi.approveApplication(profileId),
    onSuccess: (data) => {
      const msg = data.message || 'Doctor application approved.';
      setActionSuccess(msg);
      showToast(msg, 'success');
      setApproveDialogTarget(null);
      setSelectedAppId(null);
      queryClient.invalidateQueries({ queryKey: ['doctor-applications'] });
      queryClient.invalidateQueries({ queryKey: ['admin-overview'] });
    },
    onError: (err: unknown) => {
      const errDetail = getErrorMessage(err);
      setActionError(errDetail);
      showToast(errDetail, 'error');
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: ({ profileId, reason }: { profileId: string; reason: string }) =>
      doctorVerificationApi.rejectApplication(profileId, reason),
    onSuccess: (data) => {
      const msg = data.message || 'Doctor application rejected.';
      setActionSuccess(msg);
      showToast(msg, 'success');
      setRejectDialogTarget(null);
      setRejectionReason('');
      setSelectedAppId(null);
      queryClient.invalidateQueries({ queryKey: ['doctor-applications'] });
      queryClient.invalidateQueries({ queryKey: ['admin-overview'] });
    },
    onError: (err: unknown) => {
      const errDetail = getErrorMessage(err);
      setActionError(errDetail);
      showToast(errDetail, 'error');
    },
  });

  // Filtered list
  const filteredApps = (applications || []).filter((app) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      app.fullName.toLowerCase().includes(term) ||
      app.email.toLowerCase().includes(term) ||
      app.specialty.toLowerCase().includes(term) ||
      app.medicalRegistrationNumber.toLowerCase().includes(term) ||
      app.hospitalOrClinic.toLowerCase().includes(term)
    );
  });

  const handleDownloadDoc = async (doctorProfileId: string, documentKey: string, filename: string) => {
    try {
      await doctorVerificationApi.downloadDocument(doctorProfileId, documentKey, filename);
      showToast(`Downloaded ${filename} successfully.`, 'success');
    } catch (err: unknown) {
      const errMsg = `Could not download document: ${getErrorMessage(err)}`;
      setActionError(errMsg);
      showToast(errMsg, 'error');
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Status Alerts */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Doctor Verification Management
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Audit professional medical credentials and approve qualified practitioners.
          </p>
        </div>

        {/* Tab Filters */}
        <div className="flex rounded-xl bg-slate-200/70 p-1 text-xs font-semibold text-slate-600">
          {(['PENDING', 'APPROVED', 'REJECTED', 'ALL'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setStatusFilter(tab);
                setActionError(null);
                setActionSuccess(null);
              }}
              className={`rounded-lg px-3 py-1.5 transition-all ${
                statusFilter === tab
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'hover:text-slate-900'
              }`}
            >
              {tab}
            </button>
          ))}
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

      {/* Table Controls */}
      <div className="flex items-center justify-between gap-4">
        <SearchBar
          placeholder="Search by doctor, specialty, reg no..."
          value={searchTerm}
          onChange={setSearchTerm}
        />
        <span className="text-xs text-slate-400">
          {filteredApps.length} {filteredApps.length === 1 ? 'application' : 'applications'}
        </span>
      </div>

      {/* Main Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        {isLoading ? (
          <LoadingSkeleton rows={5} />
        ) : error ? (
          <ErrorState
            title="Failed to load applications"
            message={getErrorMessage(error)}
            onRetry={refetch}
          />
        ) : filteredApps.length === 0 ? (
          <EmptyState
            title="No applications found"
            description={`No doctor applications currently match status '${statusFilter}'.`}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200/80 bg-slate-50/70 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-6 py-3.5">Doctor</th>
                  <th className="px-6 py-3.5">Specialty</th>
                  <th className="px-6 py-3.5">Medical Reg No</th>
                  <th className="px-6 py-3.5">Hospital / Clinic</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Submitted</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredApps.map((app) => (
                  <tr key={app.doctorProfileId} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{app.fullName}</div>
                      <div className="text-[11px] text-slate-400">{app.email}</div>
                    </td>
                    <td className="px-6 py-4 text-slate-700 font-medium">{app.specialty}</td>
                    <td className="px-6 py-4 font-mono text-[11px] text-slate-600">
                      {app.medicalRegistrationNumber}
                    </td>
                    <td className="px-6 py-4 text-slate-600">{app.hospitalOrClinic}</td>
                    <td className="px-6 py-4">
                      <StatusBadge status={app.verificationStatus} />
                    </td>
                    <td className="px-6 py-4 text-slate-500">
                      {new Date(app.submittedAt).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSelectedAppId(app.doctorProfileId)}
                          leftIcon={<Eye className="w-3.5 h-3.5" />}
                        >
                          Review
                        </Button>
                        {app.verificationStatus === 'PENDING' && (
                          <>
                            <Button
                              variant="primary"
                              size="sm"
                              className="bg-emerald-600 hover:bg-emerald-700"
                              onClick={() => setApproveDialogTarget(app)}
                            >
                              Approve
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => {
                                setRejectDialogTarget(app);
                                setRejectionReason('');
                              }}
                            >
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Review Details Modal */}
      <Modal
        isOpen={!!selectedAppId}
        onClose={() => setSelectedAppId(null)}
        title="Doctor Verification Review"
        description="Detailed credentials & uploaded proof documents"
        maxWidth="2xl"
      >
        {isDetailLoading || !appDetail ? (
          <LoadingSkeleton rows={4} />
        ) : (
          <div className="space-y-6">
            {/* Identity & Contact */}
            <div className="grid grid-cols-2 gap-4 rounded-xl bg-slate-50 p-4 border border-slate-100 text-xs">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Full Name</span>
                <p className="font-semibold text-slate-900 mt-0.5">{appDetail.fullName}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Email & Phone</span>
                <p className="font-semibold text-slate-900 mt-0.5">
                  {appDetail.email} {appDetail.phone ? `• ${appDetail.phone}` : ''}
                </p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Specialty</span>
                <p className="font-semibold text-slate-900 mt-0.5">{appDetail.specialty}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Medical Reg No</span>
                <p className="font-mono font-semibold text-slate-900 mt-0.5">
                  {appDetail.medicalRegistrationNumber}
                </p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Hospital / Clinic</span>
                <p className="font-semibold text-slate-900 mt-0.5">{appDetail.hospitalOrClinic}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400">Experience</span>
                <p className="font-semibold text-slate-900 mt-0.5">{appDetail.experienceYears} Years</p>
              </div>
            </div>

            {/* Qualifications & Bio */}
            <div className="text-xs space-y-2">
              <div>
                <span className="font-bold text-slate-700">Academic Qualifications:</span>
                <p className="text-slate-600 mt-0.5 bg-white border border-slate-200 rounded-lg p-2.5">
                  {appDetail.qualifications || 'None provided'}
                </p>
              </div>
              {appDetail.bio && (
                <div>
                  <span className="font-bold text-slate-700">Practitioner Bio:</span>
                  <p className="text-slate-600 mt-0.5 bg-white border border-slate-200 rounded-lg p-2.5">
                    {appDetail.bio}
                  </p>
                </div>
              )}
            </div>

            {/* Verification Documents List */}
            <div>
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
                Verification Documents ({appDetail.documents.length})
              </h4>
              <div className="space-y-2">
                {appDetail.documents.length > 0 ? (
                  appDetail.documents.map((doc) => (
                    <div
                      key={doc.documentKey}
                      className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-teal-50 text-teal-600">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-slate-900">{doc.title}</p>
                          <p className="text-[10px] text-slate-400">
                            {doc.filename} • {(doc.sizeBytes / 1024).toFixed(1)} KB • {doc.mimeType}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          handleDownloadDoc(appDetail.doctorProfileId, doc.documentKey, doc.filename)
                        }
                        leftIcon={<Download className="w-3.5 h-3.5" />}
                      >
                        Download
                      </Button>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-400 italic">No document attachments found.</p>
                )}
              </div>
            </div>

            {/* Rejection Reason if present */}
            {appDetail.rejectionReason && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                <span className="font-bold">Prior Rejection Reason:</span> {appDetail.rejectionReason}
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <Button variant="outline" onClick={() => setSelectedAppId(null)}>
                Close
              </Button>
              {appDetail.verificationStatus === 'PENDING' && (
                <>
                  <Button
                    variant="danger"
                    onClick={() => {
                      setRejectDialogTarget(appDetail);
                      setRejectionReason('');
                    }}
                  >
                    Reject Application
                  </Button>
                  <Button
                    variant="primary"
                    className="bg-emerald-600 hover:bg-emerald-700"
                    onClick={() => setApproveDialogTarget(appDetail)}
                  >
                    Approve Doctor
                  </Button>
                </>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Confirmation Dialog: Approve */}
      {approveDialogTarget && (
        <ConfirmDialog
          isOpen={true}
          onClose={() => setApproveDialogTarget(null)}
          onConfirm={() => approveMutation.mutate(approveDialogTarget.doctorProfileId)}
          title="Approve Medical Practitioner"
          message={`Are you sure you want to verify ${
            approveDialogTarget.fullName.startsWith('Dr.')
              ? approveDialogTarget.fullName
              : `Dr. ${approveDialogTarget.fullName}`
          }? Their account will be activated and made visible to patients on the booking directory.`}
          confirmText="Yes, Approve Practitioner"
          variant="primary"
          isLoading={approveMutation.isPending}
        />
      )}

      {/* Reject Modal with Reason Input */}
      {rejectDialogTarget && (
        <Modal
          isOpen={true}
          onClose={() => setRejectDialogTarget(null)}
          title="Reject Doctor Application"
          description={`Provide an explanatory reason for rejecting ${
            rejectDialogTarget.fullName.startsWith('Dr.')
              ? rejectDialogTarget.fullName
              : `Dr. ${rejectDialogTarget.fullName}`
          }`}
          maxWidth="md"
        >
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reason for Rejection <span className="text-rose-500">*</span>
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="e.g. SLMC registration document unreadable or expired. Please upload a clear scanned copy."
                rows={4}
                className="w-full rounded-xl border border-slate-300 p-3 text-xs text-slate-900 focus:border-rose-500 focus:outline-none focus:ring-1 focus:ring-rose-500"
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Minimum 3 characters required. This reason will be recorded in the audit log.
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <Button
                variant="outline"
                onClick={() => setRejectDialogTarget(null)}
                disabled={rejectMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() =>
                  rejectMutation.mutate({
                    profileId: rejectDialogTarget.doctorProfileId,
                    reason: rejectionReason,
                  })
                }
                disabled={rejectionReason.trim().length < 3 || rejectMutation.isPending}
                isLoading={rejectMutation.isPending}
              >
                Confirm Rejection
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
