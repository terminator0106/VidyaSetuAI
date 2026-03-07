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
        void initialize();
    }, [initialize]);

    useEffect(() => {
        if (!isInitialized) return;
        if (!isAuthenticated) {
            clear();
            return;
        }
        void loadSubjects();
    }, [isAuthenticated, isInitialized, clear, loadSubjects]);

    return <>{children}</>;
}
