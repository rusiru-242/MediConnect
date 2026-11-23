export interface ReviewItem {
  id: string;
  appointmentId: string;
  doctorId: string;
  doctorName: string;
  patientId: string;
  patientName: string;
  rating: number;
  reviewText?: string | null;
  status: 'PUBLISHED' | 'HIDDEN' | 'REPORTED';
  isReported: boolean;
  reportReason?: string | null;
  moderationNotes?: string | null;
  createdAt: string;
}

export interface ReviewListResponse {
  items: ReviewItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ReportedReviewItem {
  id: string;
  doctorId: string;
  patientId: string;
  rating: number;
  reviewText?: string | null;
  status: string;
  isReported: boolean;
  reportReason: string;
  reportedAt: string;
  createdAt: string;
}
