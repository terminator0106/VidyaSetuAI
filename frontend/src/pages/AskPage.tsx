import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Sparkles, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/hooks/useTheme';
import { Sun, Moon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
}

const AskPage = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { isDark, toggle } = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const canAsk = false;

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
            <p className="text-sm text-muted-foreground">Open a chapter to ask questions</p>
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
                Select a chapter first
              </h2>
              <p className="max-w-sm text-base text-muted-foreground leading-relaxed">
                To keep answers accurate, questions are answered using only the selected chapter’s content.
              </p>
              <Button className="mt-6 h-11 px-6" onClick={() => navigate('/dashboard')}>
                Go to dashboard
              </Button>
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

          {isTyping && null}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-border bg-background">
        <div className="mx-auto max-w-3xl px-6 py-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
            }}
            className="flex items-center gap-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Open a chapter to ask a question..."
              className="flex-1 rounded-xl border border-input bg-background px-5 py-3.5 text-base text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={!canAsk}
            />
            <Button type="submit" size="icon" disabled={!canAsk || !input.trim() || isTyping} className="h-12 w-12 rounded-xl">
              <Send className="h-5 w-5" />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AskPage;
