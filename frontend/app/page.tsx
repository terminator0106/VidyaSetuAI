'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import dynamic from 'next/dynamic'
import { useAuthStore } from '@/store/authStore'

const Navbar = dynamic(() => import('@/components/navbar/Navbar').then(mod => ({ default: mod.Navbar })), { ssr: false })
const Hero = dynamic(() => import('@/components/hero/Hero').then(mod => ({ default: mod.Hero })), { ssr: false })
const Features = dynamic(() => import('@/components/features/Features').then(mod => ({ default: mod.Features })), { ssr: false })
const HowItWorks = dynamic(() => import('@/components/features/HowItWorks').then(mod => ({ default: mod.HowItWorks })), { ssr: false })
const Footer = dynamic(() => import('@/components/footer/Footer').then(mod => ({ default: mod.Footer })), { ssr: false })
const LoginModal = dynamic(() => import('@/components/auth/LoginModal').then(mod => ({ default: mod.LoginModal })), { ssr: false })
const SignupModal = dynamic(() => import('@/components/auth/SignupModal').then(mod => ({ default: mod.SignupModal })), { ssr: false })
const Onboarding = dynamic(() => import('@/components/onboarding/Onboarding').then(mod => ({ default: mod.Onboarding })), { ssr: false })

export default function Home() {
  const [loginOpen, setLoginOpen] = useState(false)
  const [signupOpen, setSignupOpen] = useState(false)
  const [showOnboarding, setShowOnboarding] = useState(false)
  const { isAuthenticated } = useAuthStore()
  const router = useRouter()

  const handleLoginClose = useCallback(() => {
    setLoginOpen(false)
    if (useAuthStore.getState().isAuthenticated) {
      router.push('/dashboard')
    }
  }, [router])

  const handleSignupClose = useCallback(() => {
    setSignupOpen(false)
    if (useAuthStore.getState().isAuthenticated) {
      const done = typeof window !== 'undefined' ? localStorage.getItem('onboarding_complete') : null
      if (!done) {
        setShowOnboarding(true)
      } else {
        router.push('/dashboard')
      }
    }
  }, [router])

  const handleOnboardingComplete = () => {
    setShowOnboarding(false)
    router.push('/dashboard')
  }

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
        onSwitchToSignup={() => {
          setLoginOpen(false)
          setSignupOpen(true)
        }}
      />
      <SignupModal
        open={signupOpen}
        onClose={handleSignupClose}
        onSwitchToLogin={() => {
          setSignupOpen(false)
          setLoginOpen(true)
        }}
      />

      {showOnboarding && <Onboarding onComplete={handleOnboardingComplete} />}
    </motion.div>
  )
}
