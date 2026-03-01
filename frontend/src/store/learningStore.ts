import { create } from 'zustand';

export interface Chapter {
  id: string;
  name: string;
  pdfUrl?: string | null;
  pageRange: { start: number; end: number };
  documentId: string;
  totalPages?: number | null;
}

export interface Textbook {
  id: string;
  title: string;
  totalPages?: number | null;
  chapters: Chapter[];
}

export interface Subject {
  id: string;
  name: string;
  icon: string;
  textbooks: Textbook[];
}

export interface ChapterLookup {
  subject: Subject;
  textbook: Textbook;
  chapter: Chapter;
}

interface LearningState {
  subjects: Subject[];
  addSubject: (name: string) => string;
  removeSubject: (id: string) => void;
  addTextbook: (subjectId: string, textbook: Textbook) => void;
  removeTextbook: (subjectId: string, textbookId: string) => void;
  findChapter: (chapterId: string) => ChapterLookup | null;
}

function safeId(): string {
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export const useLearningStore = create<LearningState>((set, get) => ({
  subjects: [],

  addSubject: (name: string) => {
    const id = safeId();
    set((state) => ({
      subjects: [
        ...state.subjects,
        {
          id,
          name,
          icon: '📖',
          textbooks: [],
        },
      ],
    }));
    return id;
  },

  removeSubject: (id: string) =>
    set((state) => ({
      subjects: state.subjects.filter((s) => s.id !== id),
    })),

  addTextbook: (subjectId: string, textbook: Textbook) =>
    set((state) => ({
      subjects: state.subjects.map((s) => {
        if (s.id !== subjectId) return s;
        return {
          ...s,
          textbooks: [textbook, ...s.textbooks],
        };
      }),
    })),

  removeTextbook: (subjectId: string, textbookId: string) =>
    set((state) => ({
      subjects: state.subjects.map((s) => {
        if (s.id !== subjectId) return s;
        return {
          ...s,
          textbooks: s.textbooks.filter((t) => t.id !== textbookId),
        };
      }),
    })),

  findChapter: (chapterId: string) => {
    const state = get();
    for (const subject of state.subjects) {
      for (const textbook of subject.textbooks) {
        const chapter = textbook.chapters.find((c) => c.id === chapterId);
        if (chapter) return { subject, textbook, chapter };
      }
    }
    return null;
  },
}));
