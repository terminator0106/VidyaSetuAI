import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function NotFound() {
    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6">
            <div className="text-center">
                <h1 className="text-6xl font-bold text-foreground mb-3">404</h1>
                <p className="text-2xl font-semibold text-muted-foreground mb-2">Page not found</p>
                <p className="text-base text-muted-foreground mb-8">
                    The page you're looking for doesn't exist or has been moved.
                </p>
                <Link href="/dashboard">
                    <Button size="lg" className="h-12 px-8 text-base">
                        Back to dashboard
                    </Button>
                </Link>
            </div>
        </div>
    )
}
