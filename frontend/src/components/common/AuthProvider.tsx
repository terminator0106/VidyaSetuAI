'use client'

import { ReactNode, useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useLearningStore } from '@/store/learningStore';

export function AuthProvider({ children }: { children: ReactNode }) {
    const initialize = useAuthStore((s) => s.initialize);
    const isInitialized = useAuthStore((s) => s.isInitialized);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    const loadSubjects = useLearningStore((s) => s.loadSubjects);
    const clear = useLearningStore((s) => s.clear);

    useEffect(() => {
        try {
            void initialize();
        } catch (e) {
            console.error('Auth initialization error:', e);
        }
    }, [initialize]);

    useEffect(() => {
        if (!isInitialized) return;
        try {
            if (!isAuthenticated) {
                clear();
                return;
            }
            void loadSubjects();
        } catch (e) {
            console.error('Learning store error:', e);
        }
    }, [isAuthenticated, isInitialized, clear, loadSubjects]);

    return <>{children}</>;
}
