import { motion } from 'framer-motion';
import { MessageSquare, BookOpen, Lightbulb } from 'lucide-react';

const steps = [
  {
    icon: BookOpen,
    title: 'Pick your subject & chapter',
    desc: 'Choose from your syllabus. The AI knows what you\'re studying.',
  },
  {
    icon: MessageSquare,
    title: 'Ask any question',
    desc: 'Type your doubt in plain language — Hindi or English. No fancy terms needed.',
  },
  {
    icon: Lightbulb,
    title: 'Get a clear, simple answer',
    desc: 'Step-by-step explanations that actually make sense. Ask follow-ups anytime.',
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20">
      <div className="mx-auto max-w-4xl px-4">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-12 text-center"
        >
          <h2 className="mb-3 text-3xl font-bold text-foreground md:text-4xl">
            How it works
          </h2>
          <p className="text-muted-foreground">Three simple steps to start learning.</p>
        </motion.div>

        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-6 top-0 hidden h-full w-px bg-border md:block" />

          <div className="flex flex-col gap-10">
            {steps.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.15 }}
                className="flex gap-4 md:gap-6"
              >
                <div className="relative z-10 flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full border border-border bg-background text-primary">
                  <s.icon className="h-5 w-5" />
                </div>
                <div className="pt-1">
                  <h3 className="mb-1 text-lg font-semibold text-foreground" style={{ fontFamily: "'Source Sans 3', sans-serif" }}>
                    {i + 1}. {s.title}
                  </h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
