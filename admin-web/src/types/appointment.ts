export interface AppointmentItem {
  id: string;
  patientUserId: string;
  patientName: string;
  patientEmail: string;
  doctorUserId: string;
  doctorName: string;
  doctorSpecialty: string | null;
  appointmentDate: string;
  startTime: string;
  endTime: string;
  status: 'HOLD' | 'PENDING' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED';
  paymentStatus: 'UNPAID' | 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED';
  /** Fee locked at booking; null when unknown (never shown as 0). */
  consultationFee: number | null;
  currency?: string | null;
  consultationType?: 'IN_PERSON';
  refundStatus?: string | null;
  refundId?: string | null;
  patientNote?: string | null;
  cancellationReason?: string | null;
  cancelledBy?: string | null;
  createdAt: string;
}

export interface AppointmentListResponse {
  items: AppointmentItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
