import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { BookOpen, MessageSquare, Coins, HelpCircle } from 'lucide-react';

const steps = [
  {
    icon: BookOpen,
    title: 'Welcome to Vidyasetu',
    desc: 'Your personal AI tutor — designed for Indian curriculum, low data, and simple explanations. Learning just got easier.',
  },
  {
    icon: MessageSquare,
    title: 'How questions work',
    desc: 'Pick your subject and chapter, then ask any question in Hindi or English. The AI gives you step-by-step answers tailored to your level.',
  },
  {
    icon: Coins,
    title: 'Saves cost & data',
    desc: 'Our AI is optimized to use minimal internet data. You learn more while spending less on mobile data — perfect for prepaid plans.',
  },
  {
    icon: HelpCircle,
    title: 'Tips for better answers',
    desc: 'Be specific: "Explain Newton\'s 3rd law with an example" works better than "Physics help". You can always ask "explain simpler" for easier language.',
  },
];

interface OnboardingProps {
  onComplete: () => void;
}

export function Onboarding({ onComplete }: OnboardingProps) {
  const [step, setStep] = useState(0);
  const current = steps[step];

  const handleNext = () => {
    if (step < steps.length - 1) {
      setStep(step + 1);
    } else {
      if (typeof window !== 'undefined') {
        localStorage.setItem('onboarding_complete', 'true');
      }
      onComplete();
    }
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-lg">
        {/* Progress dots */}
        <div className="mb-8 flex justify-center gap-2">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`h-2 rounded-full transition-all ${i === step ? 'w-8 bg-primary' : 'w-2 bg-border'}`}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.3 }}
            className="text-center"
          >
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              {current && <current.icon className="h-8 w-8" />}
            </div>
            <h2 className="mb-3 text-2xl font-bold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>
              {current?.title}
            </h2>
            <p className="mb-8 text-muted-foreground leading-relaxed">{current?.desc}</p>
          </motion.div>
        </AnimatePresence>

        <div className="flex justify-center gap-3">
          {step > 0 && (
            <Button variant="outline" onClick={() => setStep(step - 1)}>
              Back
            </Button>
          )}
          <Button onClick={handleNext}>
            {step < steps.length - 1 ? 'Next' : 'Start Learning'}
          </Button>
        </div>

        {step < steps.length - 1 && (
          <button
            onClick={() => {
              if (typeof window !== 'undefined') {
                localStorage.setItem('onboarding_complete', 'true');
              }
              onComplete();
            }}
            className="mt-4 block w-full text-center text-sm text-muted-foreground hover:text-foreground"
          >
            Skip for now
          </button>
        )}
      </div>
    </div>
  );
}
