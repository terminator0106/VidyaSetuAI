import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Eye, EyeOff, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/store/authStore';

interface SignupModalProps {
  open: boolean;
  onClose: () => void;
  onSwitchToLogin: () => void;
}

function getStrength(pw: string): { label: string; pct: number; color: string } {
  if (pw.length < 4) return { label: 'Too short', pct: 10, color: 'bg-destructive' };
  if (pw.length < 6) return { label: 'Weak', pct: 30, color: 'bg-destructive' };
  let score = 0;
  if (/[a-z]/.test(pw)) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  if (pw.length >= 10) score++;
  if (score <= 2) return { label: 'Fair', pct: 50, color: 'bg-warning' };
  if (score <= 3) return { label: 'Good', pct: 75, color: 'bg-primary' };
  return { label: 'Strong', pct: 100, color: 'bg-accent' };
}

export function SignupModal({ open, onClose, onSwitchToLogin }: SignupModalProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPass, setShowPass] = useState(false);
  const { signup, isLoading, error, clearError } = useAuthStore();

  const strength = useMemo(() => getStrength(password), [password]);
  const mismatch = confirm.length > 0 && password !== confirm;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mismatch) return;
    await signup(email, password);
    if (useAuthStore.getState().isAuthenticated) onClose();
  };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center bg-foreground/20 backdrop-blur-sm p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.25 }}
          className="relative w-full max-w-lg rounded-2xl border border-border bg-background p-8 shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <button onClick={onClose} className="absolute right-5 top-5 text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>

          <h2 className="mb-2 text-3xl font-bold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>Create your account</h2>
          <p className="mb-8 text-base text-muted-foreground">Start your learning journey today</p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <Label className="text-base" htmlFor="signup-email">Email</Label>
              <Input id="signup-email" type="email" className="h-12 text-base" value={email} onChange={(e) => { setEmail(e.target.value); clearError(); }} placeholder="you@example.com" required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-base" htmlFor="signup-password">Password</Label>
              <div className="relative">
                <Input id="signup-password" type={showPass ? 'text' : 'password'} className="h-12 text-base pr-12" value={password} onChange={(e) => { setPassword(e.target.value); clearError(); }} placeholder="At least 6 characters" required />
                <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {showPass ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {password.length > 0 && (
                <div className="mt-2">
                  <div className="h-2 w-full rounded-full bg-secondary">
                    <div className={`h-full rounded-full transition-all ${strength.color}`} style={{ width: `${strength.pct}%` }} />
                  </div>
                  <p className="mt-1.5 text-sm text-muted-foreground">{strength.label}</p>
                </div>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-base" htmlFor="signup-confirm">Confirm Password</Label>
              <Input id="signup-confirm" type="password" className="h-12 text-base" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Re-enter password" required />
              {mismatch && <p className="mt-1.5 text-sm text-destructive">Passwords don't match</p>}
            </div>

            {error && <p className="text-base text-destructive">{error}</p>}

            <Button type="submit" disabled={isLoading || mismatch} className="h-12 w-full text-base">
              {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Create Account'}
            </Button>
          </form>

          <p className="mt-6 text-center text-base text-muted-foreground">
            Already have an account?{' '}
            <button onClick={onSwitchToLogin} className="text-primary hover:underline font-semibold">Log in</button>
          </p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
