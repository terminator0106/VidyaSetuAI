import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { HeroBackground } from './HeroBackground';
import { useAuthStore } from '@/store/authStore';
import { useNavigate } from 'react-router-dom';

interface HeroProps {
  onSignupClick: () => void;
}

export function Hero({ onSignupClick }: HeroProps) {
  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();

  const handleStart = () => {
    if (isAuthenticated) {
      navigate('/dashboard');
    } else {
      onSignupClick();
    }
  };

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 pt-20">
      <HeroBackground />
      {/* Subtle radial gradient overlay */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_60%_at_50%_40%,hsl(var(--primary)/0.08),transparent)]" />
      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-5 py-2 text-sm font-medium text-primary"
        >
          <span>🇮🇳</span> Built for Indian students — Hindi & English supported
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65 }}
          className="mb-6 text-5xl font-bold leading-[1.15] tracking-tight text-foreground md:text-6xl lg:text-7xl"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Learn with confidence.{' '}
          <span className="text-primary">One question at a time.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.15 }}
          className="mx-auto mb-10 max-w-2xl text-xl leading-relaxed text-muted-foreground md:text-2xl"
        >
          An AI tutor designed for Indian students. Low data usage, simple explanations,
          aligned to your curriculum. No jargon, no overwhelm.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.3 }}
          className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
        >
          <Button size="lg" onClick={handleStart} className="h-14 px-10 text-lg font-semibold shadow-md">
            Start Learning Free
          </Button>
          <Button variant="outline" size="lg" asChild className="h-14 px-10 text-lg font-semibold">
            <a href="#how-it-works">See How It Works</a>
          </Button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.5 }}
          className="mt-14 flex flex-wrap items-center justify-center gap-8 text-sm text-muted-foreground"
        >
          {['✅ Free to use', '📚 Chapter-organised', '🌐 Hindi + English', '⚡ Works on slow internet'].map((badge) => (
            <span key={badge} className="text-base font-medium">{badge}</span>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
