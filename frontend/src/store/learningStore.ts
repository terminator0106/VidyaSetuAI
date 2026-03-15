import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import * as SubjectsApi from '@/services/subjects';

// Create a safe storage that works on server and client
const safeStorage = createJSONStorage(() => {
  if (typeof window === 'undefined') {
    return {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    };
  }
  return localStorage;
});

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
  loadSubjects: () => Promise<void>;
  addSubject: (name: string) => Promise<string>;
  removeSubject: (id: string) => void;
  addTextbook: (subjectId: string, textbook: Textbook) => void;
  removeTextbook: (subjectId: string, textbookId: string) => void;
  findChapter: (chapterId: string) => ChapterLookup | null;
  hydrateSubject: (subjectId: string) => Promise<void>;
  clear: () => void;
}

export const useLearningStore = create<LearningState>()(
  persist(
    (set, get) => ({
      subjects: [],

      clear: () => set({ subjects: [] }),

      loadSubjects: async () => {
        let remote: { id: string; name: string; icon: string }[] = [];
        try {
          remote = await SubjectsApi.listSubjects();
        } catch {
          // If user isn't logged in yet (401) or backend is down, don't crash the UI.
          // Keep showing the locally persisted subject list.
          return;
        }
        set((state) => {
          const byId = new Map(state.subjects.map((s) => [s.id, s] as const));
          const merged: Subject[] = remote.map((r) => {
            const existing = byId.get(r.id);
            return existing
              ? { ...existing, id: r.id, name: r.name, icon: r.icon }
              : { id: r.id, name: r.name, icon: r.icon, textbooks: [] };
          });
          return { subjects: merged };
        });
      },

      addSubject: async (name: string) => {
        const created = await SubjectsApi.createSubject(name);
        set((state) => ({
          subjects: [
            {
              id: created.id,
              name: created.name,
              icon: created.icon,
              textbooks: [],
            },
            ...state.subjects,
          ],
        }));
        return created.id;
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
              textbooks: [textbook, ...s.textbooks.filter((t) => t.id !== textbook.id)],
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

      hydrateSubject: async (subjectId: string) => {
        const full = await SubjectsApi.getSubject(subjectId);
        const seen = new Set<string>();
        const dedupedTextbooks = (full.textbooks || []).filter((tb) => {
          if (!tb || typeof tb.id !== 'string') return false;
          if (seen.has(tb.id)) return false;
          seen.add(tb.id);
          return true;
        });
        set((state) => {
          const others = state.subjects.filter((s) => s.id !== subjectId);
          const hydrated: Subject = {
            id: full.id,
            name: full.name,
            icon: full.icon,
            textbooks: dedupedTextbooks,
          };
          return { subjects: [hydrated, ...others] };
        });
      },
    }),
    {
      name: 'vidyasetu_subjects_v1',
      storage: safeStorage,
      partialize: (state) => ({
        subjects: state.subjects.map((s) => ({
          id: s.id,
          name: s.name,
          icon: s.icon,
          textbooks: [],
        })),
      }),
    },
  ),
);
