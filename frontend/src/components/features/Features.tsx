import { motion } from 'framer-motion';
import { Brain, BookOpen, Wifi, Languages, ListChecks } from 'lucide-react';

const features = [
  {
    icon: Brain,
    title: 'Context-Aware AI Tutor',
    desc: 'Understands your subject, chapter, and learning level. Answers are tailored to what you are studying.',
  },
  {
    icon: BookOpen,
    title: 'Chapter-wise Learning',
    desc: 'Organized by your textbook structure. No jumping around — learn in the order that makes sense.',
  },
  {
    icon: Wifi,
    title: 'Saves Internet & Cost',
    desc: 'Optimized for low data usage. Works on basic phones and slow connections.',
  },
  {
    icon: Languages,
    title: 'Multilingual Support',
    desc: 'Ask in Hindi, English, or your regional language. The AI understands and responds naturally.',
  },
  {
    icon: ListChecks,
    title: 'Step-by-Step Explanations',
    desc: 'No rushing through answers. Every concept is broken down into simple, easy steps.',
  },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export function Features() {
  return (
    <section id="features" className="relative py-28 bg-gradient-to-b from-slate-900 via-slate-950 to-black overflow-hidden">
      {/* Animated gradient orbs */}
      <div className="absolute inset-0 -z-10 pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-0 left-20 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '3s' }} />
      </div>

      <div className="mx-auto max-w-7xl px-6 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-16 text-center"
        >
          <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-indigo-400">Features</p>
          <h2 className="mb-4 text-4xl font-bold text-white md:text-5xl" style={{ fontFamily: "'Playfair Display', serif" }}>
            Designed for you
          </h2>
          <p className="mx-auto max-w-xl text-lg text-slate-400">
            Every feature built with rural and semi-urban students in mind.
          </p>
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-50px' }}
          className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3"
        >
          {features.map((f) => (
            <motion.div
              key={f.title}
              variants={item}
              whileHover={{ scale: 1.05, y: -8 }}
              className="group relative rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-slate-800/40 to-slate-900/30 p-8 transition-all duration-300 hover:border-indigo-400/40 hover:bg-gradient-to-br hover:from-slate-800/60 hover:to-slate-900/50 backdrop-blur-sm"
            >
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-indigo-500/5 to-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div className="relative">
                <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 text-indigo-300 transition-all duration-300 group-hover:from-indigo-500/40 group-hover:to-cyan-500/40 group-hover:text-indigo-200 group-hover:shadow-lg group-hover:shadow-indigo-500/20">
                  <f.icon className="h-7 w-7 group-hover:scale-110 transition-transform" />
                </div>
                <h3 className="mb-3 text-xl font-semibold text-white group-hover:text-indigo-200 transition-colors">
                  {f.title}
                </h3>
                <p className="text-base leading-relaxed text-slate-400 group-hover:text-slate-300 transition-colors">{f.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
