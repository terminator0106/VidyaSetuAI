import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { HeroBackground } from './HeroBackground';
import { useAuthStore } from '@/store/authStore';

interface HeroProps {
  onSignupClick: () => void;
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 100, damping: 10 },
  },
}

export function Hero({ onSignupClick }: HeroProps) {
  const { isAuthenticated } = useAuthStore();
  const router = useRouter();

  const handleStart = () => {
    if (isAuthenticated) {
      router.push('/dashboard');
    } else {
      onSignupClick();
    }
  };

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 pt-20">
      <HeroBackground />

      {/* Animated gradient orbs */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-20 left-10 w-96 h-96 bg-gradient-to-br from-indigo-500/20 to-cyan-500/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-gradient-to-tl from-purple-500/15 to-indigo-500/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative z-10 mx-auto max-w-4xl text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-400/30 bg-gradient-to-r from-indigo-500/10 to-cyan-500/10 px-5 py-2 text-sm font-medium text-indigo-300 backdrop-blur-sm"
        >
          <span>🇮🇳</span> Built for Indian students — Hindi & English supported
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="mb-6 text-5xl font-bold leading-[1.15] tracking-tight text-white md:text-6xl lg:text-7xl"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Learn with{' '}
          <motion.span
            className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-cyan-400 to-purple-400"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.7 }}
          >
            confidence.
          </motion.span>
          <br />
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.7 }}
          >
            One question at a time.
          </motion.span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-slate-300 md:text-xl"
        >
          An AI tutor designed for Indian students. Low data usage, simple explanations,
          aligned to your curriculum. No jargon, no overwhelm.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3 }}
          className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
        >
          <motion.div
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Button
              size="lg"
              onClick={handleStart}
              className="relative h-14 px-10 text-lg font-semibold bg-gradient-to-r from-indigo-500 to-cyan-500 text-white border-0 shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/50 transition-all duration-300"
            >
              Start Learning Free
            </Button>
          </motion.div>
          <motion.div
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Button
              variant="outline"
              size="lg"
              asChild
              className="h-14 px-10 text-lg font-semibold border-indigo-400/30 text-indigo-300 hover:bg-indigo-500/10 hover:text-indigo-200 transition-all duration-300"
            >
              <a href="#how-it-works">See How It Works</a>
            </Button>
          </motion.div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.5 }}
          className="mt-14 flex flex-wrap items-center justify-center gap-8 text-sm text-slate-400"
        >
          {['✅ Free to use', '📚 Chapter-organised', '🌐 Hindi + English', '⚡ Works on slow internet'].map((badge) => (
            <motion.span
              key={badge}
              className="text-base font-medium hover:text-slate-300 transition-colors"
              whileHover={{ scale: 1.1 }}
            >
              {badge}
            </motion.span>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
