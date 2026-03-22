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
    const delaysMs = [0, 250, 750];
    let lastErr: unknown = null;

    for (let attempt = 0; attempt < delaysMs.length; attempt++) {
      if (delaysMs[attempt] > 0) {
        await new Promise((r) => setTimeout(r, delaysMs[attempt]));
      }

      try {
        const res = await api.get('/auth/session');
        const user: User = res.data?.user;
        if (user) {
          set({ user, isAuthenticated: true, isInitialized: true, error: null });
        } else {
          set({ user: null, isAuthenticated: false, isInitialized: true, error: null });
        }
        return;
      } catch (e) {
        lastErr = e;
        if (axios.isAxiosError(e)) {
          const status = e.response?.status;
          // Only treat auth errors as a real "logged out" state.
          if (status === 401 || status === 403) {
            set({ user: null, isAuthenticated: false, isInitialized: true, error: null });
            return;
          }
        }
        // Otherwise, retry (handles transient 5xx or server reload).
      }
    }

    // If we still can't reach session after retries, don't assume logout —
    // but we must mark initialized to unblock the app.
    set({ user: null, isAuthenticated: false, isInitialized: true, error: getErrorMessage(lastErr) });
  },

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.post('/auth/login', { email, password });
      const user: User = res.data?.user;
      if (user) {
        set({ user, isAuthenticated: true, isLoading: false });
      } else {
        set({ error: 'Login failed. Please try again.', isLoading: false });
      }
    } catch (e: unknown) {
      const msg = getErrorMessage(e);
      set({ error: msg, isLoading: false });
    }
  },

  signup: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await api.post('/auth/signup', { email, password });
      const user: User = res.data?.user;
      if (user) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('onboarding_complete');
        }
        set({ user, isAuthenticated: true, isLoading: false });
      } else {
        set({ error: 'Signup failed. Please try again.', isLoading: false });
      }
    } catch (e: unknown) {
      const msg = getErrorMessage(e);
      set({ error: msg, isLoading: false });
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
