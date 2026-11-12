export interface DoctorDocumentMetadata {
  documentKey: string;
  title: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  uploadedAt?: string | null;
}

export interface DoctorApplicationSummary {
  doctorProfileId: string;
  userId: string;
  fullName: string;
  email: string;
  phone?: string | null;
  specialty: string;
  medicalRegistrationNumber: string;
  qualifications?: string;
  hospitalOrClinic: string;
  experienceYears: number;
  emailVerified?: boolean;
  verificationStatus: 'PENDING' | 'PENDING_EMAIL_VERIFICATION' | 'PENDING_ADMIN_APPROVAL' | 'APPROVED' | 'REJECTED' | string;
  submittedAt: string;
}

export interface DoctorApplicationDetail extends DoctorApplicationSummary {
  qualifications: string;
  bio?: string | null;
  rejectionReason?: string | null;
  emailVerified?: boolean;
  emailVerifiedAt?: string | null;
  verifiedAt?: string | null;
  verifiedBy?: string | null;
  documents: DoctorDocumentMetadata[];
}

export interface DoctorListItem {
  doctorProfileId: string;
  userId: string;
  fullName: string;
  email: string;
  phone?: string | null;
  specialty: string;
  medicalRegistrationNumber: string;
  hospitalOrClinic: string;
  experienceYears: number;
  verificationStatus: string;
  accountStatus: string;
  submittedAt: string;
  verifiedAt?: string | null;
  averageRating?: number | null;
  totalReviews: number;
}

export interface DoctorListResponse {
  items: DoctorListItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
