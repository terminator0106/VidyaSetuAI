'use client'

import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getSavings } from '@/services/admin'
import { useAuthStore } from '@/store/authStore'

export default function AdminPage() {
    const router = useRouter()
    const user = useAuthStore((s) => s.user)

    const { data, isLoading, error } = useQuery({
        queryKey: ['admin-savings'],
        queryFn: getSavings,
        enabled: user?.role === 'admin',
    })

    return (
        <div className="min-h-screen bg-background">
            <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-md">
                <div className="mx-auto flex h-20 max-w-7xl items-center gap-4 px-6">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        onClick={() => router.push('/dashboard')}
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </Button>
                    <div>
                        <p className="text-xl font-bold text-foreground">Admin Dashboard</p>
                        <p className="text-sm text-muted-foreground">Token & cost savings metrics</p>
                    </div>
                </div>
            </header>

            <div className="mx-auto max-w-7xl px-6 py-12">
                {user?.role !== 'admin' ? (
                    <div className="rounded-2xl border border-border bg-card p-10 text-center">
                        <p className="text-xl text-muted-foreground">Admin access required.</p>
                    </div>
                ) : isLoading ? (
                    <div className="rounded-2xl border border-border bg-card p-10 text-center">
                        <p className="text-xl text-muted-foreground">Loading metrics...</p>
                    </div>
                ) : error ? (
                    <div className="rounded-2xl border border-border bg-destructive/10 p-10 text-center">
                        <p className="text-xl text-destructive">Failed to load metrics.</p>
                    </div>
                ) : data ? (
                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                        {[
                            { label: 'Total Queries', value: data.totalQueries.toLocaleString(), icon: '📊' },
                            { label: 'Tokens Saved', value: data.tokensSaved.toLocaleString(), icon: '💡' },
                            { label: 'INR Saved', value: `₹${data.inrSaved.toFixed(2)}`, icon: '💰' },
                            { label: 'Avg Cost Reduction', value: `${data.avgCostReductionPct.toFixed(1)}%`, icon: '📉' },
                        ].map((stat) => (
                            <div key={stat.label} className="rounded-2xl border border-border bg-card p-8">
                                <p className="mb-2 text-3xl">{stat.icon}</p>
                                <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">{stat.label}</p>
                                <p className="mt-2 text-4xl font-bold text-card-foreground">{stat.value}</p>
                            </div>
                        ))}
                    </div>
                ) : null}
            </div>
        </div>
    )
}
