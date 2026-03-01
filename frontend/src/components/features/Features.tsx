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
    <section id="features" className="bg-card py-28">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-16 text-center"
        >
          <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-primary">Features</p>
          <h2 className="mb-4 text-4xl font-bold text-foreground md:text-5xl" style={{ fontFamily: "'Playfair Display', serif" }}>
            Designed for you
          </h2>
          <p className="mx-auto max-w-xl text-lg text-muted-foreground">
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
              className="group rounded-2xl border border-border bg-background p-8 transition-all hover:shadow-lg hover:-translate-y-1"
            >
              <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                <f.icon className="h-7 w-7" />
              </div>
              <h3 className="mb-3 text-xl font-semibold text-foreground">
                {f.title}
              </h3>
              <p className="text-base leading-relaxed text-muted-foreground">{f.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
