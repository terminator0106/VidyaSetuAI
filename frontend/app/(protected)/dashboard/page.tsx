'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Plus, LogOut, Sun, Moon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { useAuthStore } from '@/store/authStore'
import { useLearningStore } from '@/store/learningStore'
import { useTheme } from '@/hooks/useTheme'

export default function Dashboard() {
    const { user, logout } = useAuthStore()
    const { subjects, addSubject, loadSubjects } = useLearningStore()
    const [newSubject, setNewSubject] = useState('')
    const [showAdd, setShowAdd] = useState(false)
    const { isDark, toggle } = useTheme()
    const router = useRouter()

    useEffect(() => {
        void loadSubjects()
    }, [loadSubjects])

    const handleAdd = () => {
        if (newSubject.trim()) {
            void (async () => {
                const id = await addSubject(newSubject.trim())
                setNewSubject('')
                setShowAdd(false)
                router.push(`/subject/${encodeURIComponent(id)}`)
            })()
        }
    }

    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-background">
            {/* Header */}
            <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-md">
                <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
                    <a href="/" className="flex items-center gap-3 font-bold text-foreground">
                        <span className="text-3xl">🎓</span>
                        <span className="text-2xl" style={{ fontFamily: "'Playfair Display', serif" }}>Vidyasetu</span>
                    </a>
                    <div className="flex items-center gap-3">
                        <Button variant="ghost" size="icon" className="h-10 w-10" onClick={toggle}>
                            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </Button>
                        <Button
                            variant="ghost"
                            className="h-10 px-4 text-base"
                            onClick={() => {
                                void logout().finally(() => router.push('/'))
                            }}
                        >
                            <LogOut className="mr-2 h-4 w-4" /> Log out
                        </Button>
                    </div>
                </div>
            </header>

            <div className="mx-auto max-w-7xl px-6 py-12">
                <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                >
                    <h1 className="mb-2 text-4xl font-bold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>
                        Hello, {user?.email?.split('@')[0] || 'Student'} 👋
                    </h1>
                    <p className="mb-10 text-lg text-muted-foreground">Pick a subject and start learning.</p>
                </motion.div>

                {/* Subject cards */}
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                    {subjects.map((subject, i) => {
                        const chaptersCount = subject.textbooks.reduce((acc, t) => acc + (t.chapters?.length || 0), 0)
                        const progress = 0
                        return (
                            <motion.div
                                key={subject.id}
                                initial={{ opacity: 0, y: 16 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.1 + i * 0.05 }}
                                whileHover={{ y: -4, boxShadow: '0 12px 32px rgba(0,0,0,0.12)' }}
                                onClick={() => router.push(`/subject/${encodeURIComponent(subject.id)}`)}
                                className="cursor-pointer rounded-2xl border border-border bg-card p-7 transition-all hover:border-primary/40"
                            >
                                <div className="mb-4 flex items-start justify-between">
                                    <span className="text-5xl">{subject.icon}</span>
                                    <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
                                        {chaptersCount} chapters
                                    </span>
                                </div>
                                <h3 className="mb-3 text-xl font-bold text-card-foreground">{subject.name}</h3>
                                <div className="flex items-center gap-3">
                                    <Progress value={progress} className="h-2 flex-1" />
                                    <span className="text-sm font-medium text-muted-foreground">{progress}%</span>
                                </div>
                            </motion.div>
                        )
                    })}

                    {/* Add subject */}
                    {showAdd ? (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className="flex flex-col gap-4 rounded-2xl border border-dashed border-border bg-card p-7"
                        >
                            <Input
                                placeholder="e.g. Chemistry"
                                value={newSubject}
                                onChange={(e) => setNewSubject(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                                className="h-12 text-base"
                                autoFocus
                            />
                            <div className="flex gap-3">
                                <Button className="h-11 px-6 text-base" onClick={handleAdd}>
                                    Add
                                </Button>
                                <Button
                                    className="h-11 px-6 text-base"
                                    variant="ghost"
                                    onClick={() => setShowAdd(false)}
                                >
                                    Cancel
                                </Button>
                            </div>
                        </motion.div>
                    ) : (
                        <motion.button
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            onClick={() => setShowAdd(true)}
                            className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-border p-7 text-muted-foreground transition-colors hover:border-primary hover:text-primary min-h-[160px]"
                        >
                            <Plus className="h-8 w-8" />
                            <span className="text-base font-semibold">Add Subject</span>
                        </motion.button>
                    )}
                </div>
            </div>
        </motion.div>
    )
}
