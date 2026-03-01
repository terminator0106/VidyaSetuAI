import { useState } from 'react';
import { motion } from 'framer-motion';
import { Plus, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { useAuthStore } from '@/store/authStore';
import { useLearningStore } from '@/store/learningStore';
import { useTheme } from '@/hooks/useTheme';
import { Sun, Moon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const Dashboard = () => {
  const { user, logout } = useAuthStore();
  const { subjects, addSubject } = useLearningStore();
  const [newSubject, setNewSubject] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const { isDark, toggle } = useTheme();
  const navigate = useNavigate();

  const handleAdd = () => {
    if (newSubject.trim()) {
      addSubject(newSubject.trim());
      setNewSubject('');
      setShowAdd(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4">
          <a href="/" className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <span className="text-2xl">🎓</span>
            <span style={{ fontFamily: "'Playfair Display', serif" }}>Vidyasetu</span>
          </a>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={toggle}>
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => { logout(); navigate('/'); }}>
              <LogOut className="mr-1 h-4 w-4" /> Log out
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <h1 className="mb-1 text-3xl font-bold text-foreground">
            Hello, {user?.name || 'Student'} 👋
          </h1>
          <p className="mb-8 text-muted-foreground">Pick a subject and start learning.</p>
        </motion.div>

        {/* Subject cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subjects.map((subject, i) => (
            <motion.div
              key={subject.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
              whileHover={{ y: -2 }}
              onClick={() => navigate('/ask')}
              className="cursor-pointer rounded-xl border border-border bg-card p-5 transition-shadow hover:shadow-md"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-3xl">{subject.icon}</span>
                <span className="text-xs text-muted-foreground">{subject.chaptersCount} chapters</span>
              </div>
              <h3 className="mb-2 text-lg font-semibold text-card-foreground">{subject.name}</h3>
              <div className="flex items-center gap-2">
                <Progress value={subject.progress} className="h-2 flex-1" />
                <span className="text-xs text-muted-foreground">{subject.progress}%</span>
              </div>
            </motion.div>
          ))}

          {/* Add subject */}
          {showAdd ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col gap-3 rounded-xl border border-dashed border-border bg-card p-5"
            >
              <Input
                placeholder="e.g. Chemistry"
                value={newSubject}
                onChange={(e) => setNewSubject(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                autoFocus
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleAdd}>Add</Button>
                <Button size="sm" variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Button>
              </div>
            </motion.div>
          ) : (
            <motion.button
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              onClick={() => setShowAdd(true)}
              className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-border p-5 text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            >
              <Plus className="h-5 w-5" />
              <span className="text-sm font-medium">Add Subject</span>
            </motion.button>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default Dashboard;
