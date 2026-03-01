import { motion } from 'framer-motion';

export function Footer() {
  return (
    <footer id="contact" className="border-t border-border bg-card">
      <div className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-12 md:grid-cols-4">
          <div className="md:col-span-2">
            <h3 className="mb-4 text-2xl font-bold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>
              🎓 Vidyasetu
            </h3>
            <p className="mb-6 max-w-sm text-base text-muted-foreground leading-relaxed">
              AI-powered learning for every student. Designed for low bandwidth, simple explanations, and aligned to the Indian curriculum.
            </p>
            <p className="text-sm font-medium text-primary">Built with ❤️ for students across India.</p>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-bold uppercase tracking-wider text-foreground">Explore</h4>
            <div className="flex flex-col gap-3">
              <a href="#features" className="text-base text-muted-foreground hover:text-foreground transition-colors">Features</a>
              <a href="#how-it-works" className="text-base text-muted-foreground hover:text-foreground transition-colors">How it Works</a>
              <a href="#contact" className="text-base text-muted-foreground hover:text-foreground transition-colors">Contact</a>
            </div>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-bold uppercase tracking-wider text-foreground">Legal</h4>
            <div className="flex flex-col gap-3">
              <a href="#" className="text-base text-muted-foreground hover:text-foreground transition-colors">Privacy Policy</a>
              <a href="#" className="text-base text-muted-foreground hover:text-foreground transition-colors">Terms of Use</a>
            </div>
          </div>
        </div>

        <motion.div
          className="my-10 h-px bg-border"
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
        />

        <div className="flex flex-col items-center justify-between gap-4 text-sm text-muted-foreground sm:flex-row">
          <span>© {new Date().getFullYear()} Vidyasetu. All rights reserved.</span>
          <span>Made with care for students across India 🇮🇳</span>
        </div>
      </div>
    </footer>
  );
}
