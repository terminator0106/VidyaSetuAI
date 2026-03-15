'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { ArrowLeft, ChevronLeft, ChevronRight, Loader2, Send, Sparkles, ListOrdered } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ask, AskMode, getChapterHistory } from '@/services/ask'
import { getChapterPages } from '@/services/textbooks'
import { useLearningStore } from '@/store/learningStore'

interface Message {
    id: string
    role: 'user' | 'ai'
    content: string
}

function getDetailMessage(err: unknown): string | null {
    if (!err || typeof err !== 'object') return null
    const resp = (err as { response?: unknown }).response
    if (!resp || typeof resp !== 'object') return null
    const data = (resp as { data?: unknown }).data
    if (!data || typeof data !== 'object') return null
    const detail = (data as { detail?: unknown }).detail
    return typeof detail === 'string' ? detail : null
}

export default function ChapterPage() {
    const params = useParams()
    const chapterId = params.chapterId as string
    const router = useRouter()
    const lookup = useLearningStore((s) => (chapterId ? s.findChapter(decodeURIComponent(chapterId)) : null))

    const resolvedTextbookId = lookup ? lookup.textbook.id || lookup.chapter.documentId || null : null
    const resolvedChapterId = lookup?.chapter.id ?? null
    const fallbackPdfUrl = lookup?.chapter.pdfUrl ?? ''
    const fallbackRangeStart = lookup?.chapter.pageRange?.start ?? null
    const fallbackRangeEnd = lookup?.chapter.pageRange?.end ?? null

    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [isTyping, setIsTyping] = useState(false)
    const [sessionId, setSessionId] = useState<string | undefined>(undefined)
    const bottomRef = useRef<HTMLDivElement>(null)

    const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false)

    const [chapterPdfUrl, setChapterPdfUrl] = useState<string>('')
    const [rangeInfo, setRangeInfo] = useState<{ start: number; end: number } | null>(null)
    const [pageInChapter, setPageInChapter] = useState<number>(1)
    const [isLoadingPages, setIsLoadingPages] = useState<boolean>(false)

    const chapterPageCount = useMemo(() => {
        if (!rangeInfo) return null
        return Math.max(1, rangeInfo.end - rangeInfo.start + 1)
    }, [rangeInfo])

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, isTyping])

    useEffect(() => {
        if (!resolvedChapterId) return

        let cancelled = false
        const run = async () => {
            setIsLoadingHistory(true)
            try {
                const hist = await getChapterHistory(resolvedChapterId)
                if (cancelled) return

                const msgs: Message[] = (hist.messages || []).map((m) => ({
                    id: m.id,
                    role: m.role,
                    content: m.content,
                }))
                setMessages(msgs)
                if (hist.sessionId) setSessionId(String(hist.sessionId))
            } catch {
                // If history fails (e.g., 401 before auth), don't block the page.
            } finally {
                if (!cancelled) setIsLoadingHistory(false)
            }
        }

        void run()
        return () => {
            cancelled = true
        }
    }, [resolvedChapterId])

    useEffect(() => {
        if (!resolvedTextbookId || !resolvedChapterId) return

        let cancelled = false
        const run = async () => {
            setIsLoadingPages(true)
            try {
                const res = await getChapterPages(resolvedTextbookId, resolvedChapterId)
                if (cancelled) return
                setChapterPdfUrl(res.pdf_url)
                setRangeInfo({ start: res.start_page, end: res.end_page })
                setPageInChapter(1)
            } catch {
                if (cancelled) return
                if (fallbackRangeStart != null && fallbackRangeEnd != null) {
                    setChapterPdfUrl(fallbackPdfUrl || '')
                    setRangeInfo({ start: fallbackRangeStart, end: fallbackRangeEnd })
                    setPageInChapter(1)
                } else {
                    setChapterPdfUrl('')
                    setRangeInfo(null)
                }
            } finally {
                if (!cancelled) setIsLoadingPages(false)
            }
        }

        void run()
        return () => {
            cancelled = true
        }
    }, [resolvedTextbookId, resolvedChapterId, fallbackPdfUrl, fallbackRangeStart, fallbackRangeEnd])

    const send = async (text: string, mode: AskMode = 'default') => {
        if (!text.trim() || isTyping) return

        const userMsg: Message = { id: `${Date.now()}_u`, role: 'user', content: text.trim() }
        setMessages((prev) => [...prev, userMsg])
        setInput('')
        setIsTyping(true)

        try {
            const res = await ask({
                question: text.trim(),
                sessionId,
                mode,
                context: lookup
                    ? {
                        subjectId: lookup.subject.id,
                        subjectName: lookup.subject.name,
                        chapterId: lookup.chapter.id,
                        chapterName: lookup.chapter.name,
                    }
                    : undefined,
            })

            if (res.sessionId) setSessionId(res.sessionId)
            const aiMsg: Message = { id: `${Date.now()}_a`, role: 'ai', content: res.answer }
            setMessages((prev) => [...prev, aiMsg])
        } catch (e: unknown) {
            const msg = getDetailMessage(e) || 'Sorry, something went wrong. Please try again.'
            const errMsg: Message = { id: `${Date.now()}_e`, role: 'ai', content: msg }
            setMessages((prev) => [...prev, errMsg])
        } finally {
            setIsTyping(false)
        }
    }

    if (!chapterId || !lookup) {
        return (
            <div className="min-h-screen bg-background p-6">
                <p className="mb-4 text-foreground">Chapter not found.</p>
                <Button onClick={() => router.push('/dashboard')}>Back to dashboard</Button>
            </div>
        )
    }

    const pdfUrl = chapterPdfUrl || lookup.chapter.pdfUrl || ''
    const safePage = Math.max(1, Math.floor(pageInChapter || 1))
    const iframeSrc = pdfUrl ? `${pdfUrl}#page=${safePage}` : ''

    return (
        <div className="flex h-screen flex-col bg-background">
            <header className="flex-shrink-0 border-b border-border bg-background/90 backdrop-blur-md">
                <div className="mx-auto flex h-20 w-full items-center gap-4 px-6">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        onClick={() => router.push(`/subject/${encodeURIComponent(lookup.subject.id)}`)}
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </Button>
                    <div className="flex-1">
                        <p className="text-base font-bold text-foreground">{lookup.subject.name}</p>
                        <p className="text-sm text-muted-foreground">{lookup.chapter.name}</p>
                    </div>
                </div>
            </header>

            <div className="flex-1 min-h-0 md:grid md:grid-cols-2">
                {/* PDF viewer */}
                <div className="hidden md:flex flex-col border-r border-border h-full min-h-0">
                    <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-3">
                        <div>
                            <p className="text-sm font-semibold text-foreground">Reader</p>
                            {rangeInfo && (
                                <p className="text-xs text-muted-foreground">
                                    Book pages {rangeInfo.start}–{rangeInfo.end}
                                </p>
                            )}
                        </div>

                        <div className="flex items-center gap-2">
                            <Button
                                variant="outline"
                                size="icon"
                                className="h-9 w-9"
                                onClick={() => setPageInChapter((p) => Math.max(1, p - 1))}
                                disabled={isLoadingPages || !pdfUrl || pageInChapter <= 1}
                                aria-label="Previous page"
                            >
                                <ChevronLeft className="h-4 w-4" />
                            </Button>
                            <div className="flex items-center gap-2">
                                <input
                                    value={String(pageInChapter)}
                                    onChange={(e) => {
                                        const n = Number(e.target.value)
                                        if (!Number.isFinite(n)) return
                                        const max = chapterPageCount ?? 9999
                                        setPageInChapter(Math.max(1, Math.min(max, Math.floor(n))))
                                    }}
                                    className="h-9 w-16 rounded-md border border-input bg-background px-2 text-center text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                    disabled={isLoadingPages || !pdfUrl}
                                    inputMode="numeric"
                                />
                                <span className="text-xs text-muted-foreground">
                                    / {chapterPageCount ?? '—'}
                                </span>
                            </div>
                            <Button
                                variant="outline"
                                size="icon"
                                className="h-9 w-9"
                                onClick={() => {
                                    const max = chapterPageCount ?? pageInChapter + 1
                                    setPageInChapter((p) => Math.min(max, p + 1))
                                }}
                                disabled={isLoadingPages || !pdfUrl || (chapterPageCount != null && pageInChapter >= chapterPageCount)}
                                aria-label="Next page"
                            >
                                <ChevronRight className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>

                    <div className="flex-1 min-h-0">
                        {pdfUrl ? (
                            <iframe title="Chapter PDF" src={iframeSrc} className="h-full w-full" />
                        ) : isLoadingPages ? (
                            <div className="flex h-full w-full items-center justify-center p-8 text-base text-muted-foreground">
                                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                Loading chapter...
                            </div>
                        ) : (
                            <div className="flex h-full w-full items-center justify-center p-8 text-base text-muted-foreground">
                                No PDF available for this chapter.
                            </div>
                        )}
                    </div>
                </div>

                {/* Chat side */}
                <div className="flex min-h-0 flex-1 flex-col">
                    <div className="flex-1 overflow-y-auto">
                        <div className="mx-auto max-w-3xl px-6 py-8">
                            {messages.length === 0 && (
                                <div className="flex flex-col items-center justify-center py-16 text-center">
                                    <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                                        <Sparkles className="h-8 w-8" />
                                    </div>
                                    <h2 className="mb-3 text-2xl font-bold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>Ask about this chapter</h2>
                                    <p className="max-w-sm text-base text-muted-foreground leading-relaxed">
                                        Questions can be in Hindi or English. The tutor uses the chapter context to answer.
                                    </p>
                                </div>
                            )}

                            {isLoadingHistory && messages.length === 0 && (
                                <div className="mb-5 flex justify-start">
                                    <div className="flex items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 text-base text-muted-foreground">
                                        <Loader2 className="h-5 w-5 animate-spin" />
                                        Loading chat...
                                    </div>
                                </div>
                            )}

                            {messages.map((msg) => (
                                <div key={msg.id} className={`mb-5 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    <div
                                        className={`max-w-[85%] rounded-2xl px-5 py-4 text-base leading-relaxed ${msg.role === 'user'
                                            ? 'bg-primary text-primary-foreground'
                                            : 'border border-border bg-card text-card-foreground'
                                            }`}
                                        style={{ whiteSpace: 'pre-wrap' }}
                                    >
                                        {msg.content}
                                    </div>
                                </div>
                            ))}

                            {isTyping && (
                                <div className="mb-5 flex justify-start">
                                    <div className="flex items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 text-base text-muted-foreground">
                                        <Loader2 className="h-5 w-5 animate-spin" />
                                        Thinking...
                                    </div>
                                </div>
                            )}

                            <div ref={bottomRef} />
                        </div>
                    </div>

                    <div className="flex-shrink-0 border-t border-border bg-background">
                        <div className="mx-auto max-w-3xl px-6 py-4">
                            {messages.length > 0 && (
                                <div className="mb-3 flex gap-2">
                                    <Button
                                        variant="outline"
                                        className="h-9 px-4 text-sm"
                                        onClick={() => void send('Explain that in simpler terms', 'simpler')}
                                        disabled={isTyping}
                                    >
                                        <Sparkles className="mr-2 h-4 w-4" />
                                        Explain simpler
                                    </Button>
                                    <Button
                                        variant="outline"
                                        className="h-9 px-4 text-sm"
                                        onClick={() => void send('Give me a step-by-step explanation', 'step_by_step')}
                                        disabled={isTyping}
                                    >
                                        <ListOrdered className="mr-2 h-4 w-4" />
                                        Step-by-step
                                    </Button>
                                </div>
                            )}

                            <form
                                onSubmit={(e) => {
                                    e.preventDefault()
                                    void send(input)
                                }}
                                className="flex items-center gap-3"
                            >
                                <input
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Type your question..."
                                    className="flex-1 rounded-xl border border-input bg-background px-5 py-3.5 text-base text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                    disabled={isTyping}
                                />
                                <Button type="submit" size="icon" disabled={!input.trim() || isTyping} className="h-12 w-12 rounded-xl">
                                    <Send className="h-5 w-5" />
                                </Button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
