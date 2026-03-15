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
      className="fixed top-0 left-0 right-0 z-50 border-b border-indigo-500/20 bg-black/40 backdrop-blur-xl"
    >
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
        <motion.a
          href="/"
          className="flex items-center gap-3 font-bold text-white"
          whileHover={{ scale: 1.05 }}
          transition={{ type: 'spring', stiffness: 400 }}
        >
          <span className="text-3xl">🎓</span>
          <span className="text-2xl" style={{ fontFamily: "'Playfair Display', serif" }}>Vidyasetu</span>
        </motion.a>

        {/* Desktop links */}
        <div className="hidden items-center gap-8 md:flex">
          {links.map((l) => (
            <motion.a
              key={l.label}
              href={l.href}
              className="relative text-base font-medium text-slate-300 transition-colors hover:text-white group"
              whileHover={{ scale: 1.05 }}
            >
              {l.label}
              <motion.div
                className="absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-indigo-500 to-cyan-500"
                initial={{ width: 0 }}
                whileHover={{ width: '100%' }}
                transition={{ duration: 0.3 }}
              />
            </motion.a>
          ))}
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}>
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 text-slate-400 hover:text-white hover:bg-white/10 transition-colors rounded-lg"
              onClick={toggle}
              aria-label="Toggle theme"
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
          </motion.div>
          {isAuthenticated ? (
            <>
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Button
                  variant="ghost"
                  className="text-base px-5 h-10 text-slate-300 hover:text-white hover:bg-white/10 transition-all rounded-lg"
                  asChild
                >
                  <a href="/dashboard">Dashboard</a>
                </Button>
              </motion.div>
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Button
                  className="text-base px-5 h-10 bg-gradient-to-r from-indigo-500 to-cyan-500 text-white border-0 hover:shadow-lg hover:shadow-indigo-500/30 transition-all rounded-lg"
                  onClick={logout}
                >
                  Log out
                </Button>
              </motion.div>
            </>
          ) : (
            <>
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Button
                  variant="ghost"
                  className="text-base px-5 h-10 text-slate-300 hover:text-white hover:bg-white/10 transition-all rounded-lg"
                  onClick={onLoginClick}
                >
                  Log in
                </Button>
              </motion.div>
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Button
                  className="text-base px-6 h-10 bg-gradient-to-r from-indigo-500 to-cyan-500 text-white border-0 hover:shadow-lg hover:shadow-indigo-500/30 transition-all rounded-lg"
                  onClick={onSignupClick}
                >
                  Sign up free
                </Button>
              </motion.div>
            </>
          )}
        </div>

        {/* Mobile toggle */}
        <div className="flex items-center gap-2 md:hidden">
          <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10 text-slate-400 hover:text-white hover:bg-white/10 transition-colors rounded-lg"
            onClick={toggle}
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10 text-slate-400 hover:text-white hover:bg-white/10 transition-colors rounded-lg"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
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
          className="border-t border-indigo-500/20 bg-black/60 backdrop-blur-xl px-6 py-6 md:hidden"
        >
          <div className="flex flex-col gap-4">
            {links.map((l) => (
              <motion.a
                key={l.label}
                href={l.href}
                className="text-lg font-medium text-slate-300 hover:text-white transition-colors"
                onClick={() => setMobileOpen(false)}
                whileHover={{ x: 8 }}
              >
                {l.label}
              </motion.a>
            ))}
            {isAuthenticated ? (
              <>
                <motion.a
                  href="/dashboard"
                  className="text-lg font-semibold text-white hover:text-indigo-300 transition-colors"
                  onClick={() => setMobileOpen(false)}
                >
                  Dashboard
                </motion.a>
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    className="h-12 w-full text-base bg-gradient-to-r from-indigo-500 to-cyan-500 text-white border-0 hover:shadow-lg hover:shadow-indigo-500/30 transition-all rounded-lg"
                    onClick={() => {
                      void logout();
                      setMobileOpen(false);
                    }}
                  >
                    Log out
                  </Button>
                </motion.div>
              </>
            ) : (
              <div className="flex flex-col gap-3 pt-2">
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    variant="ghost"
                    className="h-12 w-full text-base text-slate-300 hover:text-white hover:bg-white/10 transition-all rounded-lg"
                    onClick={() => {
                      onLoginClick();
                      setMobileOpen(false);
                    }}
                  >
                    Log in
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    className="h-12 w-full text-base bg-gradient-to-r from-indigo-500 to-cyan-500 text-white border-0 hover:shadow-lg hover:shadow-indigo-500/30 transition-all rounded-lg"
                    onClick={() => {
                      onSignupClick();
                      setMobileOpen(false);
                    }}
                  >
                    Sign up free
                  </Button>
                </motion.div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </motion.nav>
  );
}
