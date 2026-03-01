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

export async function ask(params: {
  question: string;
  sessionId?: string;
  context?: AskContext;
  mode?: AskMode;
}): Promise<AskResult> {
  const res = await api.post('/ask', {
    question: params.question,
    sessionId: params.sessionId,
    context: params.context,
    mode: params.mode || 'default',
  });
  return res.data as AskResult;
}

// Backwards-compatible helper for simple pages.
export async function askQuestion(question: string): Promise<string> {
  const res = await ask({ question });
  return res.answer;
}
