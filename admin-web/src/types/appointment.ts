export interface AppointmentItem {
  id: string;
  patientUserId: string;
  patientName: string;
  patientEmail: string;
  doctorUserId: string;
  doctorName: string;
  doctorSpecialty: string;
  appointmentDate: string;
  startTime: string;
  endTime: string;
  status: 'HOLD' | 'PENDING' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED';
  paymentStatus: 'UNPAID' | 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED';
  consultationFee: number;
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
