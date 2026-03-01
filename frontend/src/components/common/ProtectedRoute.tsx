import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isInitialized } = useAuthStore();
  if (!isInitialized) return null;
  if (!isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
}
