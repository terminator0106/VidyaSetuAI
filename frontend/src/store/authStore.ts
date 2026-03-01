import { create } from 'zustand';
import axios from 'axios';
import api from '@/services/api';

type UserRole = 'student' | 'admin';

export interface User {
  id: number;
  email: string;
  role: UserRole;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

function getErrorMessage(err: unknown): string {
  if (typeof err === 'string') return err;
  if (axios.isAxiosError(err)) {
    const data = err.response?.data;
    if (data && typeof data === 'object') {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === 'string') return detail;
    }
    if (typeof err.message === 'string' && err.message) return err.message;
  }

  if (err && typeof err === 'object' && 'message' in err) {
    const message = (err as { message?: unknown }).message;
    if (typeof message === 'string') return message;
  }
  return 'Something went wrong. Please try again.';
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  isInitialized: false,
  error: null,

  initialize: async () => {
    try {
      const res = await api.get('/auth/session');
      const user: User = res.data.user;
      set({ user, isAuthenticated: true, isInitialized: true });
    } catch {
      set({ user: null, isAuthenticated: false, isInitialized: true });
    }
  },

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.post('/auth/login', { email, password });
      const user: User = res.data.user;
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (e: unknown) {
      set({ error: getErrorMessage(e), isLoading: false });
    }
  },

  signup: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.post('/auth/signup', { email, password });
      const user: User = res.data.user;
      localStorage.removeItem('onboarding_complete');
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (e: unknown) {
      set({ error: getErrorMessage(e), isLoading: false });
    }
  },

  logout: async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // ignore
    }
    set({ user: null, isAuthenticated: false });
  },

  clearError: () => set({ error: null }),
}));
