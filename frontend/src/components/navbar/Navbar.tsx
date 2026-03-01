import { useState } from 'react';
import { motion } from 'framer-motion';
import { Menu, X, Sun, Moon } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/button';

interface NavbarProps {
  onLoginClick: () => void;
  onSignupClick: () => void;
}

export function Navbar({ onLoginClick, onSignupClick }: NavbarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isDark, toggle } = useTheme();
  const { isAuthenticated, logout } = useAuthStore();

  const links = [
    { label: 'Features', href: '#features' },
    { label: 'How it Works', href: '#how-it-works' },
    { label: 'Contact', href: '#contact' },
  ];

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-background/90 backdrop-blur-md"
    >
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
        <a href="/" className="flex items-center gap-3 font-bold text-foreground">
          <span className="text-3xl">🎓</span>
          <span className="text-2xl" style={{ fontFamily: "'Playfair Display', serif" }}>Vidyasetu</span>
        </a>

        {/* Desktop links */}
        <div className="hidden items-center gap-8 md:flex">
          {links.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="text-base font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-4 md:flex">
          <Button variant="ghost" size="icon" className="h-10 w-10" onClick={toggle} aria-label="Toggle theme">
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
          {isAuthenticated ? (
            <>
              <Button variant="ghost" className="text-base px-5 h-10" asChild>
                <a href="/dashboard">Dashboard</a>
              </Button>
              <Button variant="outline" className="text-base px-5 h-10" onClick={logout}>
                Log out
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" className="text-base px-5 h-10" onClick={onLoginClick}>
                Log in
              </Button>
              <Button className="text-base px-6 h-10" onClick={onSignupClick}>
                Sign up free
              </Button>
            </>
          )}
        </div>

        {/* Mobile toggle */}
        <div className="flex items-center gap-2 md:hidden">
          <Button variant="ghost" size="icon" className="h-10 w-10" onClick={toggle}>
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
          <Button variant="ghost" size="icon" className="h-10 w-10" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </Button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="border-t border-border bg-background px-6 py-6 md:hidden"
        >
          <div className="flex flex-col gap-4">
            {links.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="text-lg font-medium text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {l.label}
              </a>
            ))}
            {isAuthenticated ? (
              <>
                <a href="/dashboard" className="text-lg font-semibold text-foreground">Dashboard</a>
                <Button variant="outline" className="h-12 text-base" onClick={logout}>Log out</Button>
              </>
            ) : (
              <div className="flex flex-col gap-3 pt-2">
                <Button variant="ghost" className="h-12 text-base" onClick={() => { onLoginClick(); setMobileOpen(false); }}>Log in</Button>
                <Button className="h-12 text-base" onClick={() => { onSignupClick(); setMobileOpen(false); }}>Sign up free</Button>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </motion.nav>
  );
}
