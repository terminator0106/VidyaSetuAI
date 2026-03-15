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
    <section id="how-it-works" className="relative py-28 bg-gradient-to-b from-slate-950 via-slate-900 to-black overflow-hidden">
      {/* Animated gradient orbs */}
      <div className="absolute inset-0 -z-10 pointer-events-none">
        <div className="absolute top-20 left-10 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-20 right-10 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }} />
      </div>

      <div className="mx-auto max-w-5xl px-6 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-16 text-center"
        >
          <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-indigo-400">How It Works</p>
          <h2 className="mb-4 text-4xl font-bold text-white md:text-5xl" style={{ fontFamily: "'Playfair Display', serif" }}>
            Three simple steps
          </h2>
          <p className="mx-auto max-w-lg text-lg text-slate-400">To start learning smarter today.</p>
        </motion.div>

        <div className="flex flex-col gap-6">
          {steps.map((s, i) => (
            <motion.div
              key={s.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.15 }}
              whileHover={{ scale: 1.02, y: -4 }}
              className="flex gap-6 rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-slate-800/40 to-slate-900/30 p-8 transition-all duration-300 hover:border-indigo-400/40 hover:bg-gradient-to-br hover:from-slate-800/60 hover:to-slate-900/50 hover:shadow-lg hover:shadow-indigo-500/10 backdrop-blur-sm"
            >
              <div className="relative z-10 flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-500 text-white shadow-lg shadow-indigo-500/30 group-hover:shadow-indigo-500/50 transition-all">
                <s.icon className="h-8 w-8" />
              </div>
              <div className="flex flex-col justify-center">
                <p className="mb-1 text-xs font-bold uppercase tracking-wider text-indigo-400">Step {i + 1}</p>
                <h3 className="mb-2 text-xl font-bold text-white">
                  {s.title}
                </h3>
                <p className="text-base text-slate-400 leading-relaxed hover:text-slate-300 transition-colors">{s.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
