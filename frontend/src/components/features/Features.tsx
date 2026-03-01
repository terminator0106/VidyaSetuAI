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
    <section id="features" className="bg-card py-20">
      <div className="mx-auto max-w-6xl px-4">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="mb-12 text-center"
        >
          <h2 className="mb-3 text-3xl font-bold text-foreground md:text-4xl">
            Designed for you
          </h2>
          <p className="text-muted-foreground">
            Every feature built with rural and semi-urban students in mind.
          </p>
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-50px' }}
          className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {features.map((f) => (
            <motion.div
              key={f.title}
              variants={item}
              className="group rounded-xl border border-border bg-background p-6 transition-shadow hover:shadow-md"
            >
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <f.icon className="h-5 w-5" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-foreground" style={{ fontFamily: "'Source Sans 3', sans-serif" }}>
                {f.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
