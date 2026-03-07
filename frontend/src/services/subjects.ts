import api from '@/services/api';

export interface SubjectListItem {
    id: string;
    name: string;
    icon: string;
}

export async function listSubjects(): Promise<SubjectListItem[]> {
    const res = await api.get('/subjects');
    return res.data as SubjectListItem[];
}

export async function createSubject(name: string): Promise<SubjectListItem> {
    const res = await api.post('/subjects', { name });
    return res.data as SubjectListItem;
}

export async function getSubject(subjectId: string): Promise<{
    id: string;
    name: string;
    icon: string;
    textbooks: Array<{
        id: string;
        title: string;
        totalPages?: number | null;
        chapters: Array<{
            id: string;
            name: string;
            pdfUrl?: string | null;
            pageRange: { start: number; end: number };
            documentId: string;
            totalPages?: number | null;
        }>;
    }>;
}> {
    const res = await api.get(`/subjects/${encodeURIComponent(subjectId)}`);
    return res.data;
}

export async function deleteSubject(subjectId: string): Promise<void> {
    await api.delete(`/subjects/${encodeURIComponent(subjectId)}`);
}
