'use client'

import { ReactNode, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'

export default function ProtectedLayout({
    children,
}: {
    children: ReactNode
}) {
    const router = useRouter()
    const { isAuthenticated, isInitialized } = useAuthStore()

    useEffect(() => {
        if (isInitialized && !isAuthenticated) {
            router.push('/')
        }
    }, [isInitialized, isAuthenticated, router])

    if (!isInitialized) {
        return null
    }

    if (!isAuthenticated) {
        return null
    }

    return <>{children}</>
}
