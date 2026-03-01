import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Eye, EyeOff, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/store/authStore';

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  onSwitchToSignup: () => void;
}

export function LoginModal({ open, onClose, onSwitchToSignup }: LoginModalProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const { login, isLoading, error, clearError } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(email, password);
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

          <h2 className="mb-2 text-3xl font-bold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>Welcome back</h2>
          <p className="mb-8 text-base text-muted-foreground">Log in to continue learning</p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <Label className="text-base" htmlFor="login-email">Email</Label>
              <Input id="login-email" type="email" className="h-12 text-base" value={email} onChange={(e) => { setEmail(e.target.value); clearError(); }} placeholder="you@example.com" required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-base" htmlFor="login-password">Password</Label>
              <div className="relative">
                <Input id="login-password" type={showPass ? 'text' : 'password'} className="h-12 text-base pr-12" value={password} onChange={(e) => { setPassword(e.target.value); clearError(); }} placeholder="••••••" required />
                <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {showPass ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
            </div>

            {error && <p className="text-base text-destructive">{error}</p>}

            <Button type="submit" disabled={isLoading} className="h-12 w-full text-base">
              {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : 'Log in'}
            </Button>
          </form>

          <p className="mt-6 text-center text-base text-muted-foreground">
            Don't have an account?{' '}
            <button onClick={onSwitchToSignup} className="text-primary hover:underline font-semibold">Sign up</button>
          </p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
