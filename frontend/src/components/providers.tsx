'use client'

import { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/components/common/AuthProvider'
import { ThemeProvider } from 'next-themes'

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 60 * 1000,
            gcTime: 5 * 60 * 1000,
        },
    },
})

export default function Providers({ children }: { children: ReactNode }) {
    return (
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
            <QueryClientProvider client={queryClient}>
                <TooltipProvider>
                    <AuthProvider>
                        {children}
                    </AuthProvider>
                </TooltipProvider>
            </QueryClientProvider>
        </ThemeProvider>
    )
}
