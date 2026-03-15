import { motion } from 'framer-motion';

export function Footer() {
  return (
    <footer id="contact" className="relative border-t border-indigo-500/20 bg-gradient-to-b from-slate-950 to-black overflow-hidden">
      {/* Subtle gradient orbs */}
      <div className="absolute inset-0 -z-10 pointer-events-none">
        <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-72 h-72 bg-cyan-500/5 rounded-full blur-3xl" />
      </div>

      <div className="mx-auto max-w-7xl px-6 py-20 relative z-10">
        <div className="grid gap-12 md:grid-cols-4">
          <div className="md:col-span-2">
            <motion.h3
              className="mb-4 text-2xl font-bold text-white"
              style={{ fontFamily: "'Playfair Display', serif" }}
              whileHover={{ scale: 1.05 }}
            >
              🎓 Vidyasetu
            </motion.h3>
            <p className="mb-6 max-w-sm text-base text-slate-400 leading-relaxed hover:text-slate-300 transition-colors">
              AI-powered learning for every student. Designed for low bandwidth, simple explanations, and aligned to the Indian curriculum.
            </p>
            <p className="text-sm font-medium text-indigo-400">Built with ❤️ for students across India.</p>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-bold uppercase tracking-wider text-indigo-300">Explore</h4>
            <div className="flex flex-col gap-3">
              <motion.a
                href="#features"
                className="text-base text-slate-400 hover:text-indigo-300 transition-colors"
                whileHover={{ x: 4 }}
              >
                Features
              </motion.a>
              <motion.a
                href="#how-it-works"
                className="text-base text-slate-400 hover:text-indigo-300 transition-colors"
                whileHover={{ x: 4 }}
              >
                How it Works
              </motion.a>
              <motion.a
                href="#contact"
                className="text-base text-slate-400 hover:text-indigo-300 transition-colors"
                whileHover={{ x: 4 }}
              >
                Contact
              </motion.a>
            </div>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-bold uppercase tracking-wider text-indigo-300">Legal</h4>
            <div className="flex flex-col gap-3">
              <motion.a
                href="#"
                className="text-base text-slate-400 hover:text-indigo-300 transition-colors"
                whileHover={{ x: 4 }}
              >
                Privacy Policy
              </motion.a>
              <motion.a
                href="#"
                className="text-base text-slate-400 hover:text-indigo-300 transition-colors"
                whileHover={{ x: 4 }}
              >
                Terms of Use
              </motion.a>
            </div>
          </div>
        </div>

        <motion.div
          className="my-10 h-px bg-gradient-to-r from-indigo-500/0 via-indigo-500/30 to-indigo-500/0"
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
        />

        <div className="flex flex-col items-center justify-between gap-4 text-sm text-slate-400 sm:flex-row">
          <span className="hover:text-slate-300 transition-colors">© {new Date().getFullYear()} Vidyasetu. All rights reserved.</span>
          <span className="hover:text-indigo-300 transition-colors">Made with care for students across India 🇮🇳</span>
        </div>
      </div>
    </footer>
  );
}
