import React, { createContext, useContext, useEffect, useState } from 'react';
import { AdminUser, AuthContextType } from '../types/auth';
import { AUTH_TOKEN_KEY, AUTH_USER_KEY } from '../api/client';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [admin, setAdmin] = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    try {
      const storedToken = sessionStorage.getItem(AUTH_TOKEN_KEY);
      const storedUser = sessionStorage.getItem(AUTH_USER_KEY);
      if (storedToken && storedUser) {
        const parsed = JSON.parse(storedUser) as AdminUser;
        if (parsed.role === 'ADMIN') {
          setAdmin(parsed);
        } else {
          sessionStorage.removeItem(AUTH_TOKEN_KEY);
          sessionStorage.removeItem(AUTH_USER_KEY);
        }
      }
    } catch {
      sessionStorage.removeItem(AUTH_TOKEN_KEY);
      sessionStorage.removeItem(AUTH_USER_KEY);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = (token: string, user: AdminUser, refreshToken?: string) => {
    sessionStorage.setItem(AUTH_TOKEN_KEY, token);
    sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    if (refreshToken) {
      sessionStorage.setItem('mediconnect_admin_refresh', refreshToken);
    }
    setAdmin(user);
  };

  const logout = () => {
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_USER_KEY);
    sessionStorage.removeItem('mediconnect_admin_refresh');
    setAdmin(null);
  };

  const isAuthenticated = !!admin && admin.role === 'ADMIN';

  return (
    <AuthContext.Provider value={{ admin, isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
