import { motion } from 'framer-motion';

export function Footer() {
  return (
    <footer id="contact" className="border-t border-border bg-card">
      <div className="mx-auto max-w-6xl px-4 py-12">
        {/* Animated line */}
        <motion.div
          className="mb-8 h-px bg-border"
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
        />

        <div className="grid gap-8 md:grid-cols-3">
          <div>
            <h3 className="mb-2 text-lg font-semibold text-foreground" style={{ fontFamily: "'Playfair Display', serif" }}>
              🎓 Vidyasetu
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              AI-powered learning for every student. Designed for low bandwidth, simple explanations, and Indian curriculum.
            </p>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold text-foreground">Links</h4>
            <div className="flex flex-col gap-1">
              <a href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Features</a>
              <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">How it Works</a>
              <a href="#contact" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Contact</a>
            </div>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold text-foreground">Legal</h4>
            <div className="flex flex-col gap-1">
              <a href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Privacy Policy</a>
              <a href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Terms of Use</a>
            </div>
          </div>
        </div>

        <div className="mt-8 border-t border-border pt-6 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} Vidyasetu. Made with care for students across India.
        </div>
      </div>
    </footer>
  );
}
