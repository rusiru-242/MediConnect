export type UserRole = 'PATIENT' | 'DOCTOR' | 'ADMIN';
export type AccountStatus = 'ACTIVE' | 'PENDING' | 'SUSPENDED' | 'DEACTIVATED';

export interface AdminUser {
  id: string;
  fullName: string;
  email: string;
  phone?: string | null;
  role: UserRole;
  accountStatus: AccountStatus;
  emailVerified: boolean;
  createdAt: string;
  updatedAt?: string | null;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken?: string;
  tokenType: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken?: string;
  tokenType: string;
  user: AdminUser;
}

export interface AuthContextType {
  admin: AdminUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, user: AdminUser, refreshToken?: string) => void;
  logout: () => void;
}
