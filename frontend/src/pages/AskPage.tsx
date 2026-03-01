import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Sparkles, ListOrdered, ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/hooks/useTheme';
import { Sun, Moon } from 'lucide-react';
import { ask, AskMode } from '@/services/ask';
import { useNavigate } from 'react-router-dom';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
}

const AskPage = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { isDark, toggle } = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const send = async (text: string, mode: AskMode = 'default') => {
    if (!text.trim() || isTyping) return;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await ask({ question: text.trim(), sessionId, mode });
      if (res.sessionId) setSessionId(res.sessionId);
      const aiMsg: Message = { id: (Date.now() + 1).toString(), role: 'ai', content: res.answer };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      const errMsg: Message = { id: (Date.now() + 1).toString(), role: 'ai', content: 'Sorry, something went wrong. Please try again.' };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-border bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex h-18 max-w-4xl items-center gap-4 px-6">
          <Button variant="ghost" size="icon" className="h-11 w-11" onClick={() => navigate('/dashboard')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            <p className="text-base font-bold text-foreground">AI Tutor</p>
            <p className="text-sm text-muted-foreground">General questions (not chapter-specific)</p>
          </div>
          <Button variant="ghost" size="icon" className="h-11 w-11" onClick={toggle}>
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 py-8">
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col items-center justify-center py-24 text-center"
            >
              <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Sparkles className="h-8 w-8" />
              </div>
              <h2 className="mb-3 text-2xl font-bold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>
                Ask anything
              </h2>
              <p className="max-w-sm text-base text-muted-foreground leading-relaxed">
                Type your question below. You can ask in Hindi or English. I will explain step by step.
              </p>
            </motion.div>
          )}

          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={`mb-5 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-5 py-4 text-base leading-relaxed ${msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'border border-border bg-card text-card-foreground'
                    }`}
                  style={{ whiteSpace: 'pre-wrap' }}
                >
                  {msg.content}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mb-5 flex justify-start"
            >
              <div className="flex items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 text-base text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
                Thinking...
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-border bg-background">
        <div className="mx-auto max-w-3xl px-6 py-4">
          {/* Quick actions */}
          {messages.length > 0 && (
            <div className="mb-3 flex gap-2">
              <Button
                variant="outline"
                className="h-9 px-4 text-sm"
                onClick={() => send('Explain that in simpler terms', 'simpler')}
                disabled={isTyping}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Explain simpler
              </Button>
              <Button
                variant="outline"
                className="h-9 px-4 text-sm"
                onClick={() => send('Give me a step-by-step explanation', 'step_by_step')}
                disabled={isTyping}
              >
                <ListOrdered className="mr-2 h-4 w-4" />
                Step-by-step
              </Button>
            </div>
          )}

          <form
            onSubmit={(e) => { e.preventDefault(); send(input); }}
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
  );
};

export default AskPage;
