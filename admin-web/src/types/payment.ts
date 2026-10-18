export interface PaymentItem {
  id: string;
  appointmentId: string;
  patientUserId: string;
  patientName: string;
  doctorUserId: string;
  doctorName: string;
  stripePaymentIntentId: string;
  amount: number;
  currency: string;
  status: 'PENDING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'REFUNDED';
  isTestMode: boolean;
  failureReason?: string | null;
  paidAt?: string | null;
  createdAt: string;
}

export interface PaymentListResponse {
  items: PaymentItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
