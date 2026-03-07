import api from '@/services/api';

export type AskMode = 'default' | 'simpler' | 'step_by_step';

export interface AskContext {
  subjectId?: string;
  subjectName?: string;
  chapterId?: string;
  chapterName?: string;
}

export interface AskResult {
  answer: string;
  sessionId?: string;
  metrics?: {
    tokensSaved?: number;
    inrSaved?: number;
    avgCostReductionPct?: number;
  };
}

export interface HistoryMessage {
  id: string;
  role: 'user' | 'ai';
  content: string;
  created_at: string;
}

export interface ChapterHistory {
  chapter_id: string;
  sessionId?: string | null;
  messages: HistoryMessage[];
}

export async function ask(params: {
  question: string;
  sessionId?: string;
  chapterId?: string;
  context?: AskContext;
  mode?: AskMode;
}): Promise<AskResult> {
  const chapterId = params.chapterId || params.context?.chapterId;
  if (!chapterId) {
    throw new Error('chapterId is required. Open a chapter to ask chapter-specific questions.');
  }

  const res = await api.post('/ask', {
    question: params.question,
    sessionId: params.sessionId,
    chapter_id: chapterId,
    context: params.context,
    mode: params.mode || 'default',
  });
  return res.data as AskResult;
}

export async function getChapterHistory(chapterId: string): Promise<ChapterHistory> {
  const res = await api.get('/ask/history', {
    params: { chapter_id: chapterId },
  });
  return res.data as ChapterHistory;
}

// Backwards-compatible helper for simple pages.
export async function askQuestion(question: string, chapterId: string): Promise<string> {
  const res = await ask({ question, chapterId });
  return res.answer;
}
