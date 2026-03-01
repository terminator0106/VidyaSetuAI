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
    <section id="how-it-works" className="py-28">
      <div className="mx-auto max-w-5xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-16 text-center"
        >
          <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-primary">How It Works</p>
          <h2 className="mb-4 text-4xl font-bold text-foreground md:text-5xl" style={{ fontFamily: "'Playfair Display', serif" }}>
            Three simple steps
          </h2>
          <p className="mx-auto max-w-lg text-lg text-muted-foreground">To start learning smarter today.</p>
        </motion.div>

        <div className="flex flex-col gap-6">
          {steps.map((s, i) => (
            <motion.div
              key={s.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.15 }}
              className="flex gap-6 rounded-2xl border border-border bg-card p-8 transition-shadow hover:shadow-md"
            >
              <div className="relative z-10 flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md">
                <s.icon className="h-8 w-8" />
              </div>
              <div className="flex flex-col justify-center">
                <p className="mb-1 text-xs font-bold uppercase tracking-wider text-primary">Step {i + 1}</p>
                <h3 className="mb-2 text-xl font-bold text-foreground">
                  {s.title}
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">{s.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
