import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, Loader2, Trash2, LogOut, Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTheme } from '@/hooks/useTheme';
import { ingestPdf } from '@/services/ingest';
import { deleteTextbook } from '@/services/textbooks';
import { useAuthStore } from '@/store/authStore';
import { Textbook, useLearningStore } from '@/store/learningStore';

function getDetailMessage(err: unknown): string | null {
    if (!err || typeof err !== 'object') return null;
    const resp = (err as { response?: unknown }).response;
    if (!resp || typeof resp !== 'object') return null;
    const data = (resp as { data?: unknown }).data;
    if (!data || typeof data !== 'object') return null;
    const detail = (data as { detail?: unknown }).detail;
    return typeof detail === 'string' ? detail : null;
}

export default function SubjectPage() {
    const { subjectId } = useParams();
    const navigate = useNavigate();
    const { isDark, toggle } = useTheme();
    const logout = useAuthStore((s) => s.logout);

    const subject = useLearningStore(
        (s) => s.subjects.find((x) => x.id === (subjectId || '')) || null,
    );
    const addTextbook = useLearningStore((s) => s.addTextbook);
    const removeTextbook = useLearningStore((s) => s.removeTextbook);

    const [file, setFile] = useState<File | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const textbooks = subject?.textbooks || [];

    const subjectTitle = useMemo(() => subject?.name || 'Subject', [subject?.name]);

    const onUpload = async () => {
        if (!subjectId || !subject) return;
        if (!file) {
            setError('Please choose a PDF first.');
            return;
        }

        setIsUploading(true);
        setError(null);
        try {
            const inferredTitle = file.name.replace(/\.pdf$/i, '');
            const res = await ingestPdf({ file, subjectId, textbookName: inferredTitle });
            const tbId = String(res.textbook_id || res.documentId);
            const title = inferredTitle;

            const textbook: Textbook = {
                id: tbId,
                title,
                totalPages: res.totalPages ?? null,
                chapters: (res.chapters || []).map((ch) => ({
                    id: ch.id,
                    name: ch.name,
                    pdfUrl: ch.pdfUrl,
                    pageRange: ch.pageRange || {
                        start: ch.start_page ?? 1,
                        end: ch.end_page ?? 1,
                    },
                    documentId: tbId,
                    totalPages: res.totalPages ?? null,
                })),
            };

            addTextbook(subjectId, textbook);
            setFile(null);
        } catch (e: unknown) {
            setError(getDetailMessage(e) || 'Upload failed. Please try again.');
        } finally {
            setIsUploading(false);
        }
    };

    const onDelete = async (tb: Textbook) => {
        if (!subjectId) return;
        const ok = window.confirm(`Delete textbook "${tb.title}"? This will remove stored PDFs and vectors.`);
        if (!ok) return;

        try {
            await deleteTextbook(tb.id);
            removeTextbook(subjectId, tb.id);
        } catch (e: unknown) {
            setError(getDetailMessage(e) || 'Delete failed. Please try again.');
        }
    };

    if (!subjectId || !subject) {
        return (
            <div className="min-h-screen bg-background p-6">
                <p className="mb-4 text-foreground">Subject not found.</p>
                <Button onClick={() => navigate('/dashboard')}>Back to dashboard</Button>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background">
            <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-md">
                <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" className="h-11 w-11" onClick={() => navigate('/dashboard')}>
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                        <div>
                            <p className="text-xl font-bold text-foreground">{subjectTitle}</p>
                            <p className="text-sm text-muted-foreground">Upload a textbook PDF and pick a chapter.</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button variant="ghost" size="icon" className="h-11 w-11" onClick={toggle}>
                            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </Button>
                        <Button
                            variant="ghost"
                            className="h-10 px-4 text-base"
                            onClick={() => {
                                void logout().finally(() => navigate('/'));
                            }}
                        >
                            <LogOut className="mr-2 h-4 w-4" /> Log out
                        </Button>
                    </div>
                </div>
            </header>

            <div className="mx-auto max-w-7xl px-6 py-10">
                {/* Upload section */}
                <div className="rounded-2xl border border-border bg-card p-8 mb-10">
                    <h2 className="mb-1 text-2xl font-bold text-card-foreground">Ingest PDF</h2>
                    <p className="mb-6 text-base text-muted-foreground">Upload a textbook PDF. The backend will automatically split it into per-chapter PDFs.</p>

                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                        <Input
                            type="file"
                            accept="application/pdf"
                            className="h-12 text-base"
                            onChange={(e) => {
                                setError(null);
                                setFile(e.target.files?.[0] || null);
                            }}
                        />
                        <Button onClick={onUpload} disabled={isUploading || !file} className="h-12 px-8 text-base sm:w-44">
                            {isUploading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Upload'}
                        </Button>
                    </div>

                    {error && <p className="mt-4 text-base text-destructive">{error}</p>}
                </div>

                {/* Textbooks section */}
                <div>
                    <h2 className="mb-5 text-2xl font-bold text-foreground">Textbooks</h2>

                    {textbooks.length === 0 ? (
                        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border p-16 text-muted-foreground">
                            <BookOpen className="mb-4 h-12 w-12 opacity-30" />
                            <p className="text-lg font-medium">No textbooks yet</p>
                            <p className="mt-1 text-sm">Upload a PDF above to get started.</p>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-6">
                            {textbooks.map((tb) => (
                                <div key={tb.id} className="rounded-2xl border border-border bg-card overflow-hidden">
                                    <div className="flex items-center justify-between gap-4 bg-card px-8 py-5 border-b border-border">
                                        <div>
                                            <p className="text-lg font-bold text-card-foreground">{tb.title}</p>
                                            {tb.totalPages != null && (
                                                <p className="text-sm text-muted-foreground">{tb.totalPages} pages</p>
                                            )}
                                        </div>
                                        <Button variant="destructive" className="h-10 px-5 text-sm" onClick={() => void onDelete(tb)}>
                                            <Trash2 className="mr-2 h-4 w-4" /> Delete
                                        </Button>
                                    </div>

                                    <div className="divide-y divide-border">
                                        {tb.chapters.map((ch) => (
                                            <div key={ch.id} className="flex flex-col gap-3 px-8 py-5 sm:flex-row sm:items-center sm:justify-between hover:bg-muted/30 transition-colors">
                                                <div>
                                                    <p className="text-base font-semibold text-card-foreground">{ch.name}</p>
                                                    <p className="text-sm text-muted-foreground">
                                                        Pages {ch.pageRange.start}–{ch.pageRange.end}
                                                    </p>
                                                </div>
                                                <Button
                                                    className="h-10 px-6 text-sm"
                                                    onClick={() => navigate(`/chapter/${encodeURIComponent(ch.id)}`)}
                                                    disabled={!ch.pdfUrl}
                                                >
                                                    Open Chapter
                                                </Button>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
