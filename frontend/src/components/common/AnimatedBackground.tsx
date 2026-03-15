'use client'

import { useEffect, useRef } from 'react'

export function AnimatedBackground() {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const animationRef = useRef<number | null>(null)

    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        // Set canvas size
        const resizeCanvas = () => {
            canvas.width = window.innerWidth
            canvas.height = window.innerHeight
        }
        resizeCanvas()
        window.addEventListener('resize', resizeCanvas)

        // Particles for animation
        const particles = [
            {
                x: canvas.width * 0.2,
                y: canvas.height * 0.2,
                radius: 150,
                color: 'rgba(124, 156, 245, 0.15)',
                vx: 0.02,
                vy: 0.01,
            },
            {
                x: canvas.width * 0.8,
                y: canvas.height * 0.3,
                radius: 120,
                color: 'rgba(94, 234, 212, 0.1)',
                vx: -0.015,
                vy: 0.025,
            },
            {
                x: canvas.width * 0.5,
                y: canvas.height * 0.8,
                radius: 180,
                color: 'rgba(168, 85, 247, 0.08)',
                vx: 0.01,
                vy: -0.02,
            },
        ]

        const animate = () => {
            // Clear canvas with dark background
            ctx.fillStyle = 'rgb(11, 11, 15)'
            ctx.fillRect(0, 0, canvas.width, canvas.height)

            // Apply blur filter
            ctx.filter = 'blur(80px)'

            // Draw and animate particles
            particles.forEach((particle) => {
                // Update position
                particle.x += particle.vx
                particle.y += particle.vy

                // Bounce off edges
                if (particle.x - particle.radius < 0 || particle.x + particle.radius > canvas.width) {
                    particle.vx *= -1
                }
                if (particle.y - particle.radius < 0 || particle.y + particle.radius > canvas.height) {
                    particle.vy *= -1
                }

                // Draw gradient circle
                const gradient = ctx.createRadialGradient(
                    particle.x,
                    particle.y,
                    0,
                    particle.x,
                    particle.y,
                    particle.radius
                )
                gradient.addColorStop(0, particle.color)
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')

                ctx.fillStyle = gradient
                ctx.beginPath()
                ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2)
                ctx.fill()
            })

            // Reset filter
            ctx.filter = 'none'

            animationRef.current = requestAnimationFrame(animate)
        }

        animate()

        return () => {
            window.removeEventListener('resize', resizeCanvas)
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current)
            }
        }
    }, [])

    return (
        <canvas
            ref={canvasRef}
            className="fixed inset-0 -z-50 pointer-events-none"
            style={{ background: 'rgb(11, 11, 15)' }}
        />
    )
}
