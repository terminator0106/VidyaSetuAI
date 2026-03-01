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
    <section className="relative flex min-h-[85vh] items-center justify-center overflow-hidden px-4 pt-16">
      <HeroBackground />
      <div className="relative z-10 mx-auto max-w-2xl text-center">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-4 text-4xl font-bold leading-tight text-foreground md:text-5xl lg:text-6xl"
        >
          Learn with confidence.{' '}
          <span className="text-primary">One question at a time.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mb-8 text-lg text-muted-foreground leading-relaxed md:text-xl"
        >
          An AI tutor designed for Indian students. Low data usage, simple explanations,
          aligned to your curriculum. No jargon, no overwhelm.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
        >
          <Button size="lg" onClick={handleStart} className="min-w-[160px]">
            Start Learning
          </Button>
          <Button variant="outline" size="lg" asChild className="min-w-[160px]">
            <a href="#how-it-works">See How It Works</a>
          </Button>
        </motion.div>
      </div>
    </section>
  );
}
