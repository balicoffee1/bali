import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (login: string, password: string) => Promise<void>;
  logout: () => void;
  switchRole: (role: UserRole) => void;
  hasRole: (roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;

    const restoreSession = async () => {
      if (!api.hasSession()) {
        if (active) setIsLoading(false);
        return;
      }

      try {
        const response = await api.getMe();
        if (active) setUser(response.user);
      } catch {
        api.clearSession();
        if (active) setUser(null);
      } finally {
        if (active) setIsLoading(false);
      }
    };

    const expireSession = () => setUser(null);
    window.addEventListener('hi-admin-session-expired', expireSession);
    restoreSession();

    return () => {
      active = false;
      window.removeEventListener('hi-admin-session-expired', expireSession);
    };
  }, []);

  useEffect(() => {
    if (user) {
      localStorage.setItem('hi_admin_current_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('hi_admin_current_user');
    }
  }, [user]);

  const login = async (loginInput: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await api.login(loginInput, password);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    api.clearSession();
  };

  // Useful for quick role testing / simulation during demo
  const switchRole = (role: UserRole) => {
    if (user && api.isMockMode()) {
      const updated: User = {
        ...user,
        role,
        is_staff: ['owner', 'admin', 'employee'].includes(role),
        is_superuser: role === 'owner',
      };
      setUser(updated);
    }
  };

  const hasRole = (allowedRoles: UserRole[]) => {
    if (!user) return false;
    if (user.role === 'owner' || user.is_superuser) return true;
    return allowedRoles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        switchRole,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
