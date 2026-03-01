import { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function FloatingShapes() {
  const groupRef = useRef<THREE.Group>(null);
  const shapes = useMemo(() => {
    return Array.from({ length: 8 }, (_, i) => ({
      position: [
        (Math.random() - 0.5) * 6,
        (Math.random() - 0.5) * 4,
        (Math.random() - 0.5) * 3 - 2,
      ] as [number, number, number],
      scale: 0.15 + Math.random() * 0.25,
      speed: 0.2 + Math.random() * 0.3,
      offset: Math.random() * Math.PI * 2,
      type: i % 3,
    }));
  }, []);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    groupRef.current.rotation.y = clock.elapsedTime * 0.02;
    groupRef.current.children.forEach((child, i) => {
      const shape = shapes[i];
      if (!shape) return;
      child.position.y = shape.position[1] + Math.sin(clock.elapsedTime * shape.speed + shape.offset) * 0.3;
      child.rotation.x = clock.elapsedTime * shape.speed * 0.5;
      child.rotation.z = clock.elapsedTime * shape.speed * 0.3;
    });
  });

  return (
    <group ref={groupRef}>
      {shapes.map((s, i) => (
        <mesh key={i} position={s.position} scale={s.scale}>
          {s.type === 0 && <icosahedronGeometry args={[1, 0]} />}
          {s.type === 1 && <octahedronGeometry args={[1, 0]} />}
          {s.type === 2 && <tetrahedronGeometry args={[1, 0]} />}
          <meshStandardMaterial
            color={i % 2 === 0 ? '#4a7c9b' : '#5a9a7a'}
            transparent
            opacity={0.35}
            wireframe
          />
        </mesh>
      ))}
    </group>
  );
}

function canRender3D(): boolean {
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!gl) return false;
    const debugInfo = (gl as WebGLRenderingContext).getExtension('WEBGL_debug_renderer_info');
    if (debugInfo) {
      const renderer = (gl as WebGLRenderingContext).getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
      const lowEnd = /swiftshader|llvmpipe|mesa/i.test(renderer);
      if (lowEnd) return false;
    }
    return true;
  } catch {
    return false;
  }
}

export function HeroBackground() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    setEnabled(canRender3D());
  }, []);

  if (!enabled) return null;

  return (
    <div className="absolute inset-0 -z-10 opacity-60">
      <Canvas
        camera={{ position: [0, 0, 5], fov: 50 }}
        dpr={[1, 1.5]}
        gl={{ antialias: false, powerPreference: 'low-power' }}
      >
        <ambientLight intensity={0.6} />
        <directionalLight position={[5, 5, 5]} intensity={0.4} />
        <FloatingShapes />
      </Canvas>
    </div>
  );
}
