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
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-black">
            {/* Animated gradient orbs background */}
            <div className="fixed inset-0 -z-10 pointer-events-none overflow-hidden">
                <div className="absolute top-40 left-20 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl animate-float" />
                <div className="absolute bottom-40 right-20 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }} />
            </div>

            {/* Header */}
            <header className="sticky top-0 z-40 border-b border-indigo-500/20 bg-black/40 backdrop-blur-xl">
                <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
                    <motion.a
                        href="/"
                        className="flex items-center gap-3 font-bold text-white"
                        whileHover={{ scale: 1.05 }}
                    >
                        <span className="text-3xl">🎓</span>
                        <span className="text-2xl" style={{ fontFamily: "'Playfair Display', serif" }}>Vidyasetu</span>
                    </motion.a>
                    <div className="flex items-center gap-3">
                        <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-10 w-10 text-slate-400 hover:text-white hover:bg-white/10 transition-all rounded-lg"
                                onClick={toggle}
                            >
                                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                            </Button>
                        </motion.div>
                        <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                            <Button
                                className="h-10 px-4 text-base bg-gradient-to-r from-indigo-500 to-cyan-500 text-white border-0 hover:shadow-lg hover:shadow-indigo-500/30 transition-all rounded-lg"
                                onClick={() => {
                                    void logout().finally(() => router.push('/'))
                                }}
                            >
                                <LogOut className="mr-2 h-4 w-4" /> Log out
                            </Button>
                        </motion.div>
                    </div>
                </div>
            </header>

            <div className="mx-auto max-w-7xl px-6 py-12 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                >
                    <h1 className="mb-2 text-4xl font-bold text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
                        Hello, {user?.email?.split('@')[0] || 'Student'} 👋
                    </h1>
                    <p className="mb-10 text-lg text-slate-400">Pick a subject and start learning.</p>
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
                                whileHover={{ y: -8, scale: 1.02 }}
                                onClick={() => router.push(`/subject/${encodeURIComponent(subject.id)}`)}
                                className="group cursor-pointer rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-slate-800/40 to-slate-900/30 p-7 transition-all duration-300 hover:border-indigo-400/40 hover:bg-gradient-to-br hover:from-slate-800/60 hover:to-slate-900/50 backdrop-blur-sm"
                            >
                                <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-indigo-500/5 to-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                                <div className="relative">
                                    <div className="mb-4 flex items-start justify-between">
                                        <span className="text-5xl group-hover:scale-110 transition-transform duration-300">{subject.icon}</span>
                                        <motion.span
                                            className="rounded-full bg-gradient-to-r from-indigo-500/20 to-cyan-500/20 px-3 py-1 text-xs font-medium text-indigo-300 border border-indigo-500/30"
                                            whileHover={{ scale: 1.1 }}
                                        >
                                            {chaptersCount} chapters
                                        </motion.span>
                                    </div>
                                    <h3 className="mb-3 text-xl font-bold text-white group-hover:text-indigo-200 transition-colors">{subject.name}</h3>
                                    <div className="flex items-center gap-3">
                                        <div className="flex-1">
                                            <Progress
                                                value={progress}
                                                className="h-2 flex-1 bg-slate-700 rounded-full"
                                            />
                                        </div>
                                        <span className="text-sm font-medium text-slate-400 group-hover:text-slate-300 transition-colors">{progress}%</span>
                                    </div>
                                </div>
                            </motion.div>
                        )
                    })}

                    {/* Add subject */}
                    {showAdd ? (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            className="flex flex-col gap-4 rounded-2xl border border-indigo-400/30 bg-gradient-to-br from-slate-800/40 to-slate-900/30 p-7 backdrop-blur-sm"
                        >
                            <Input
                                placeholder="e.g. Chemistry"
                                value={newSubject}
                                onChange={(e) => setNewSubject(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                                className="h-12 text-base bg-slate-800/50 border-indigo-500/30 text-white placeholder:text-slate-500 focus:border-indigo-400 focus:ring-indigo-500/20"
                                autoFocus
                            />
                            <div className="flex gap-3">
                                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="flex-1">
                                    <Button
                                        className="h-11 w-full px-6 text-base bg-gradient-to-r from-indigo-500 to-cyan-500 text-white border-0 hover:shadow-lg hover:shadow-indigo-500/30 transition-all rounded-lg"
                                        onClick={handleAdd}
                                    >
                                        Add
                                    </Button>
                                </motion.div>
                                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="flex-1">
                                    <Button
                                        className="h-11 w-full px-6 text-base text-slate-300 hover:text-white hover:bg-white/10 transition-all rounded-lg"
                                        variant="ghost"
                                        onClick={() => setShowAdd(false)}
                                    >
                                        Cancel
                                    </Button>
                                </motion.div>
                            </div>
                        </motion.div>
                    ) : (
                        <motion.button
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.3 }}
                            onClick={() => setShowAdd(true)}
                            whileHover={{ scale: 1.02, borderColor: 'rgb(99, 102, 241)' }}
                            className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-indigo-500/40 p-7 text-slate-400 transition-all duration-300 hover:border-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 min-h-[160px] group backdrop-blur-sm"
                        >
                            <Plus className="h-8 w-8 group-hover:scale-110 transition-transform duration-300" />
                            <span className="text-base font-semibold">Add Subject</span>
                        </motion.button>
                    )}
                </div>
            </div>
        </motion.div>
    )
}
