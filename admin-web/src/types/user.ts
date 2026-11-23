export interface UserItem {
  id: string;
  email: string;
  fullName: string;
  phone?: string | null;
  role: 'PATIENT' | 'DOCTOR' | 'ADMIN';
  accountStatus: 'ACTIVE' | 'PENDING' | 'SUSPENDED' | 'DEACTIVATED';
  emailVerified: boolean;
  createdAt: string;
  updatedAt?: string | null;
  lastLoginAt?: string | null;
}

export interface UserListResponse {
  items: UserItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
