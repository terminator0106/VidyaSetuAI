import api from '@/services/api';

export async function deleteTextbook(textbookId: string | number): Promise<void> {
    await api.delete(`/textbooks/${textbookId}`);
}

export interface TextbookChapterItem {
    id: string;
    title: string;
    start_page: number;
    end_page: number;
    page_count: number;
}

export interface TextbookChaptersResponse {
    textbook_id: string;
    chapters: TextbookChapterItem[];
}

export async function getTextbookChapters(textbookId: string | number): Promise<TextbookChaptersResponse> {
    const res = await api.get(`/textbooks/${textbookId}/chapters/ranges`);
    return res.data as TextbookChaptersResponse;
}

export interface TextbookChapterCloudinaryItem {
    chapter_number: number;
    chapter_title: string;
    cloudinary_url: string | null;
}

export async function getTextbookChaptersCloudinary(
    textbookId: string | number,
): Promise<TextbookChapterCloudinaryItem[]> {
    const res = await api.get(`/textbooks/${textbookId}/chapters`);
    return res.data as TextbookChapterCloudinaryItem[];
}

export interface ChapterPagesResponse {
    textbook_id: string;
    chapter_id: string;
    start_page: number;
    end_page: number;
    pdf_url: string;
}

export async function getChapterPages(
    textbookId: string | number,
    chapterId: string,
): Promise<ChapterPagesResponse> {
    const res = await api.get(`/textbooks/${textbookId}/chapters/${encodeURIComponent(chapterId)}/pages`);
    return res.data as ChapterPagesResponse;
}
