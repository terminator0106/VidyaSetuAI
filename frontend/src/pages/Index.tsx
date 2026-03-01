import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Navbar } from '@/components/navbar/Navbar';
import { Hero } from '@/components/hero/Hero';
import { Features } from '@/components/features/Features';
import { HowItWorks } from '@/components/features/HowItWorks';
import { Footer } from '@/components/footer/Footer';
import { LoginModal } from '@/components/auth/LoginModal';
import { SignupModal } from '@/components/auth/SignupModal';
import { Onboarding } from '@/components/onboarding/Onboarding';
import { useAuthStore } from '@/store/authStore';
import { useNavigate } from 'react-router-dom';

const Index = () => {
  const [loginOpen, setLoginOpen] = useState(false);
  const [signupOpen, setSignupOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();

  const handleLoginClose = useCallback(() => {
    setLoginOpen(false);
    if (useAuthStore.getState().isAuthenticated) {
      navigate('/dashboard');
    }
  }, [navigate]);

  const handleSignupClose = useCallback(() => {
    setSignupOpen(false);
    if (useAuthStore.getState().isAuthenticated) {
      const done = localStorage.getItem('onboarding_complete');
      if (!done) {
        setShowOnboarding(true);
      } else {
        navigate('/dashboard');
      }
    }
  }, [navigate]);

  const handleOnboardingComplete = () => {
    setShowOnboarding(false);
    navigate('/dashboard');
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
      <Navbar
        onLoginClick={() => setLoginOpen(true)}
        onSignupClick={() => setSignupOpen(true)}
      />
      <main>
        <Hero onSignupClick={() => setSignupOpen(true)} />
        <Features />
        <HowItWorks />
      </main>
      <Footer />

      <LoginModal
        open={loginOpen}
        onClose={handleLoginClose}
        onSwitchToSignup={() => { setLoginOpen(false); setSignupOpen(true); }}
      />
      <SignupModal
        open={signupOpen}
        onClose={handleSignupClose}
        onSwitchToLogin={() => { setSignupOpen(false); setLoginOpen(true); }}
      />

      {showOnboarding && <Onboarding onComplete={handleOnboardingComplete} />}
    </motion.div>
  );
};

export default Index;
