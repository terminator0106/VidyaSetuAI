import { create } from 'zustand';

export interface Subject {
  id: string;
  name: string;
  icon: string;
  chaptersCount: number;
  progress: number;
}

interface LearningState {
  subjects: Subject[];
  addSubject: (name: string) => void;
  removeSubject: (id: string) => void;
}

const defaultSubjects: Subject[] = [
  { id: '1', name: 'Physics', icon: '⚛️', chaptersCount: 12, progress: 35 },
  { id: '2', name: 'Biology', icon: '🧬', chaptersCount: 15, progress: 20 },
  { id: '3', name: 'History', icon: '📜', chaptersCount: 10, progress: 60 },
  { id: '4', name: 'Mathematics', icon: '📐', chaptersCount: 14, progress: 45 },
];

export const useLearningStore = create<LearningState>((set) => ({
  subjects: defaultSubjects,
  addSubject: (name: string) =>
    set((state) => ({
      subjects: [
        ...state.subjects,
        {
          id: Date.now().toString(),
          name,
          icon: '📖',
          chaptersCount: 0,
          progress: 0,
        },
      ],
    })),
  removeSubject: (id: string) =>
    set((state) => ({
      subjects: state.subjects.filter((s) => s.id !== id),
    })),
}));
