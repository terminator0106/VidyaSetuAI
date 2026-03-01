import api from '@/services/api';

export interface IngestChapter {
    id: string;
    name: string;
    pageRange: { start: number; end: number };
    pdfUrl?: string | null;
    start_page?: number;
    end_page?: number;
}

export interface IngestResponse {
    textbook_id?: string;
    documentId: string;
    subjectId?: string | null;
    totalPages?: number | null;
    chapters: IngestChapter[];
    structure?: unknown;
}

export async function ingestPdf(params: {
    file: File;
    subjectId?: string;
    textbookName?: string;
}): Promise<IngestResponse> {
    const form = new FormData();
    form.append('file', params.file);
    if (params.subjectId) {
        // backend supports both; keep backwards compat
        form.append('subjectId', params.subjectId);
        form.append('subject_id', params.subjectId);
    }
    if (params.textbookName) {
        form.append('textbookName', params.textbookName);
        form.append('textbook_name', params.textbookName);
    }

    const res = await api.post('/ingest/pdf', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });

    return res.data as IngestResponse;
}
