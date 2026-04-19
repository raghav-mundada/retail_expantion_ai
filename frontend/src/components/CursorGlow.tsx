/**
 * CursorGlow — warm amber canvas trail + ambient radial orb.
 *
 * Performance model (inherited from shelf-mind-map):
 *  - shadowBlur for GPU-composited softness; no ctx.filter
 *  - Near-invisible orbs skipped early
 *  - Disabled on touch/reduced-motion
 *  - Active everywhere (not zone-restricted like the shelf variant)
 */
import React, { useEffect, useRef } from 'react';

interface TrailPoint {
  x: number;
  y: number;
  age: number;
  maxAge: number;
  radius: number;
}

const MAX_TRAIL  = 60;
const TRAIL_LIFE = 10;
const SPAWN_STEP = 20;

export const CursorGlow: React.FC = () => {
  const glowRef    = useRef<HTMLDivElement>(null);
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const rafRef     = useRef<number>(0);
  const posRef     = useRef({ x: -1000, y: -1000 });
  const currentRef = useRef({ x: -1000, y: -1000 });
  const prevRef    = useRef<{ x: number; y: number } | null>(null);
  const trail      = useRef<TrailPoint[]>([]);

  useEffect(() => {
    // Respect prefers-reduced-motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    // No trail on touch (no cursor)
    if (window.matchMedia('(hover: none)').matches) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize, { passive: true });

    const ctx = canvas.getContext('2d')!;
    ctx.shadowColor = 'rgba(182, 145, 105, 0.55)';
    ctx.shadowBlur  = 16;

    const spawnOrb = (x: number, y: number) => {
      trail.current.push({
        x, y,
        age: 0,
        maxAge: TRAIL_LIFE + Math.random() * 5,
        radius: 100 + Math.random() * 60,
      });
      if (trail.current.length > MAX_TRAIL) trail.current.shift();
    };

    const handleMove = (e: MouseEvent) => {
      const curr = { x: e.clientX, y: e.clientY };
      posRef.current = curr;

      const prev = prevRef.current;
      if (prev) {
        const dx = curr.x - prev.x;
        const dy = curr.y - prev.y;
        const dist = Math.hypot(dx, dy);
        const steps = Math.max(1, Math.floor(dist / SPAWN_STEP));
        for (let i = 0; i <= steps; i++) {
          const t = steps === 0 ? 1 : i / steps;
          spawnOrb(prev.x + dx * t, prev.y + dy * t);
        }
      } else {
        spawnOrb(curr.x, curr.y);
      }
      prevRef.current = curr;
    };

    window.addEventListener('mousemove', handleMove, { passive: true });

    const animate = () => {
      // Lerp ambient orb
      const target = posRef.current;
      const cur    = currentRef.current;
      const lx = cur.x + (target.x - cur.x) * 0.09;
      const ly = cur.y + (target.y - cur.y) * 0.09;
      currentRef.current = { x: lx, y: ly };
      if (glowRef.current) {
        glowRef.current.style.transform = `translate(${lx}px, ${ly}px)`;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (const pt of trail.current) {
        const life  = 1 - pt.age / pt.maxAge;
        const alpha = life * life * life * life * 0.11;
        if (alpha < 0.003) { pt.age++; continue; }

        const r = pt.radius * (0.75 + 0.25 * life);
        const grad = ctx.createRadialGradient(pt.x, pt.y, 0, pt.x, pt.y, r);
        grad.addColorStop(0,   `rgba(200, 168, 130, ${alpha})`);
        grad.addColorStop(0.3, `rgba(182, 145, 105, ${alpha * 0.55})`);
        grad.addColorStop(0.7, `rgba(160, 124,  88, ${alpha * 0.15})`);
        grad.addColorStop(1,   `rgba(140, 105,  72, 0)`);

        ctx.beginPath();
        ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        pt.age++;
      }

      trail.current = trail.current.filter(pt => pt.age < pt.maxAge);
      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        className="pointer-events-none fixed top-0 left-0 z-[5]"
        style={{ willChange: 'contents' }}
        aria-hidden="true"
      />
      <div
        ref={glowRef}
        className="pointer-events-none fixed z-[4] top-0 left-0"
        style={{
          width:       560,
          height:      560,
          marginLeft:  -280,
          marginTop:   -280,
          background:  'radial-gradient(circle, hsla(30, 38%, 60%, 0.07) 0%, hsla(30, 28%, 45%, 0.035) 45%, transparent 70%)',
          willChange:  'transform',
          borderRadius:'50%',
        }}
        aria-hidden="true"
      />
    </>
  );
};
