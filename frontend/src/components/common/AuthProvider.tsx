import { ReactNode, useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';

export function AuthProvider({ children }: { children: ReactNode }) {
    const initialize = useAuthStore((s) => s.initialize);

    useEffect(() => {
        void initialize();
    }, [initialize]);

    return <>{children}</>;
}
