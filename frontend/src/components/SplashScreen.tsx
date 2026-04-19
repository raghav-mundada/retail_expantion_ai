/**
 * SplashScreen — RetailIQ branded launch screen.
 *
 * Timeline:
 *   0.0 s → Background + logo fade in
 *   0.7 s → "Retail" text visible; "IQ" slides out liquid-spring style
 *   1.4 s → Particle burst plays; progress bar fills
 *   2.6 s → Gradient colour-wave sweeps full screen
 *   3.1 s → Entire splash fades out (clip-path upward reveal)
 *   3.6 s → onComplete fires
 *
 * Only shown once per browser session via sessionStorage.
 */
import React, { useEffect, useState, useRef } from 'react';

interface Props {
  onComplete: () => void;
}

interface Particle {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
  color: string;
}

const PARTICLE_COLORS = [
  'rgba(200,168,130,',
  'rgba(182,145,105,',
  'rgba(160,120, 80,',
  'rgba(220,190,155,',
  'rgba(240,215,180,',
];

export const SplashScreen: React.FC<Props> = ({ onComplete }) => {
  const [phase, setPhase]           = useState<'logo' | 'text' | 'burst' | 'wave' | 'out'>('logo');
  const [progress, setProgress]     = useState(0);
  const [waveVisible, setWaveVisible] = useState(false);
  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const rafRef      = useRef<number>(0);
  const particles   = useRef<Particle[]>([]);

  /* ── Particle burst on canvas ──────────────────────────────────────── */
  useEffect(() => {
    if (phase !== 'burst') return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
    const cx = canvas.width  / 2;
    const cy = canvas.height / 2;

    // Spawn 80 particles
    particles.current = Array.from({ length: 80 }, (_, i) => {
      const angle  = (Math.PI * 2 * i) / 80 + Math.random() * 0.15;
      const speed  = 1.8 + Math.random() * 3.5;
      return {
        id:     i,
        x:      cx,
        y:      cy,
        vx:     Math.cos(angle) * speed,
        vy:     Math.sin(angle) * speed,
        radius: 1.5 + Math.random() * 3,
        alpha:  0.8 + Math.random() * 0.2,
        color:  PARTICLE_COLORS[i % PARTICLE_COLORS.length],
      };
    });

    const ctx = canvas.getContext('2d')!;

    const step = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      let alive = false;
      for (const p of particles.current) {
        if (p.alpha <= 0.01) continue;
        alive = true;
        p.x     += p.vx;
        p.y     += p.vy;
        p.vx    *= 0.965;
        p.vy    *= 0.965;
        p.vy    += 0.04; // slight gravity
        p.alpha -= 0.012;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${Math.max(0, p.alpha)})`;
        ctx.fill();
      }
      if (alive) rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);

    return () => cancelAnimationFrame(rafRef.current);
  }, [phase]);

  /* ── Phase sequencer ───────────────────────────────────────────────── */
  useEffect(() => {
    const t1 = setTimeout(() => setPhase('text'), 700);

    const t2 = setTimeout(() => {
      setPhase('burst');
      let p = 0;
      progressRef.current = setInterval(() => {
        p += 2;
        setProgress(Math.min(p, 100));
        if (p >= 100 && progressRef.current) clearInterval(progressRef.current);
      }, 24);
    }, 1400);

    const t3 = setTimeout(() => {
      setPhase('wave');
      setWaveVisible(true);
    }, 2600);

    const t4 = setTimeout(() => setPhase('out'), 3100);
    const t5 = setTimeout(() => onComplete(),    3600);

    return () => {
      [t1, t2, t3, t4, t5].forEach(clearTimeout);
      if (progressRef.current) clearInterval(progressRef.current);
    };
  }, [onComplete]);

  const logoVisible     = phase !== 'out';
  const textVisible     = phase !== 'logo';
  const progressVisible = !['logo', 'text'].includes(phase);

  return (
    <div
      style={{
        position:       'fixed',
        inset:          0,
        zIndex:         99999,
        display:        'flex',
        flexDirection:  'column',
        alignItems:     'center',
        justifyContent: 'center',
        background:     '#1A0C06',
        overflow:       'hidden',
        opacity:        phase === 'out' ? 0 : 1,
        transition:     phase === 'out' ? 'opacity 0.5s ease' : 'none',
      }}
    >
      {/* ── Subtle dot pattern on dark background ───────────────────── */}
      <div
        style={{
          position:        'absolute',
          inset:           0,
          opacity:         0.06,
          backgroundImage: 'radial-gradient(circle, #C8A882 1px, transparent 1px)',
          backgroundSize:  '32px 32px',
          pointerEvents:   'none',
        }}
      />

      {/* ── Particle burst canvas ────────────────────────────────────── */}
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
        aria-hidden="true"
      />

      {/* ── Ambient glow behind logo ─────────────────────────────────── */}
      <div
        style={{
          position:     'absolute',
          width:        '380px',
          height:       '380px',
          borderRadius: '50%',
          background:   'radial-gradient(circle, rgba(200,168,130,0.14) 0%, transparent 70%)',
          top:          '50%',
          left:         '50%',
          transform:    'translate(-50%, -50%)',
          opacity:      logoVisible ? 1 : 0,
          transition:   'opacity 0.6s ease',
        }}
      />

      {/* ── Logo row ─────────────────────────────────────────────────── */}
      <div
        style={{
          display:    'flex',
          alignItems: 'center',
          gap:        '20px',
          position:   'relative',
          zIndex:     2,
          overflow:   'hidden',
        }}
      >
        {/* Icon mark */}
        <div
          style={{
            width:          '80px',
            height:         '80px',
            borderRadius:   '20px',
            background:     'linear-gradient(145deg, #2a1508, #1a0c06)',
            border:         '2px solid rgba(200,168,130,0.32)',
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'center',
            boxShadow:      '0 8px 32px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)',
            opacity:        logoVisible ? 1 : 0,
            transform:      logoVisible ? 'scale(1)' : 'scale(0.55)',
            transition:     'opacity 0.5s ease, transform 0.65s cubic-bezier(0.34,1.56,0.64,1)',
            flexShrink:     0,
          }}
        >
          {/* RetailIQ mark — stylised "R" with data bars */}
          <svg width="46" height="46" viewBox="0 0 46 46" fill="none">
            {/* Location pin */}
            <path
              d="M23 8C18.03 8 14 12.03 14 17c0 7 9 21 9 21s9-14 9-21c0-4.97-4.03-9-9-9z"
              stroke="#F5ECD7" strokeWidth="2" fill="none" strokeLinejoin="round"
            />
            <circle cx="23" cy="17" r="3.5" fill="#F5ECD7" opacity="0.9" />
            {/* Bar chart below */}
            <rect x="10" y="33" width="4" height="6" rx="1" fill="#F5ECD7" opacity="0.5" />
            <rect x="16" y="30" width="4" height="9" rx="1" fill="#F5ECD7" opacity="0.65" />
            <rect x="22" y="27" width="4" height="12" rx="1" fill="#F5ECD7" opacity="0.8" />
            <rect x="28" y="31" width="4" height="8" rx="1" fill="#F5ECD7" opacity="0.65" />
            <rect x="34" y="34" width="4" height="5" rx="1" fill="#F5ECD7" opacity="0.5" />
          </svg>
        </div>

        {/* "Retail" — visible with logo */}
        <div
          style={{
            fontFamily:           '"Inter", "Geist", system-ui, sans-serif',
            fontSize:             '34px',
            fontWeight:           700,
            letterSpacing:        '-0.5px',
            background:           'linear-gradient(135deg, #F5ECD7 0%, #C8A882 55%, #B8916E 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor:  'transparent',
            backgroundClip:       'text',
            opacity:              logoVisible ? 1 : 0,
            transition:           'opacity 0.5s ease 0.15s',
            flexShrink:           0,
          }}
        >
          Retail
        </div>

        {/* "IQ" — liquid spring slide-out */}
        <div
          style={{
            overflow:   'hidden',
            maxWidth:   textVisible ? '80px' : '0px',
            opacity:    textVisible ? 1 : 0,
            transition: 'max-width 0.7s cubic-bezier(0.34,1.2,0.64,1), opacity 0.4s ease 0.05s',
            whiteSpace: 'nowrap',
          }}
        >
          <div
            style={{
              fontFamily:           '"Inter", "Geist", system-ui, sans-serif',
              fontSize:             '34px',
              fontWeight:           700,
              letterSpacing:        '-0.5px',
              background:           'linear-gradient(135deg, #B8916E 0%, #E8C98A 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor:  'transparent',
              backgroundClip:       'text',
            }}
          >
            IQ
          </div>
        </div>
      </div>

      {/* ── Tagline ──────────────────────────────────────────────────── */}
      <p
        style={{
          marginTop:     '18px',
          fontFamily:    '"Inter", system-ui, sans-serif',
          fontSize:      '10px',
          letterSpacing: '3px',
          textTransform: 'uppercase',
          color:         'rgba(245,236,215,0.35)',
          opacity:       progressVisible ? 1 : 0,
          transition:    'opacity 0.4s ease 0.1s',
          position:      'relative',
          zIndex:        2,
        }}
      >
        Intelligent Retail Expansion
      </p>

      {/* ── Progress bar ─────────────────────────────────────────────── */}
      <div
        style={{
          marginTop:    '32px',
          width:        '160px',
          height:       '2px',
          borderRadius: '2px',
          background:   'rgba(255,255,255,0.07)',
          overflow:     'hidden',
          opacity:      progressVisible ? 1 : 0,
          transition:   'opacity 0.3s ease',
          position:     'relative',
          zIndex:       2,
        }}
      >
        <div
          style={{
            height:     '100%',
            width:      `${progress}%`,
            borderRadius:'2px',
            background: 'linear-gradient(90deg, #7d5a3c, #c8a882, #e8c98a)',
            transition: 'width 0.025s linear',
            boxShadow:  '0 0 10px rgba(200,168,130,0.6)',
          }}
        />
      </div>

      {/* ── Colour-wave sweep overlay ────────────────────────────────── */}
      <div
        style={{
          position:   'absolute',
          inset:      0,
          background: 'linear-gradient(135deg, #7d5a3c 0%, #b8916e 35%, #1a0c06 65%, #0d0704 100%)',
          opacity:    waveVisible ? 0.94 : 0,
          transition: waveVisible ? 'opacity 0.5s cubic-bezier(0.4,0,0.2,1)' : 'none',
          zIndex:     3,
        }}
      />
      {waveVisible && (
        <div
          style={{
            position:   'absolute',
            inset:      0,
            background: 'radial-gradient(ellipse at 30% 60%, rgba(200,168,130,0.22) 0%, transparent 60%), radial-gradient(ellipse at 70% 30%, rgba(125,90,60,0.18) 0%, transparent 55%)',
            zIndex:     4,
            animation:  'rippleIn 0.55s ease forwards',
          }}
        />
      )}

      {/* ── RetailIQ mark re-appears on wave ────────────────────────── */}
      {waveVisible && (
        <div
          style={{
            position:      'absolute',
            zIndex:        5,
            display:       'flex',
            flexDirection: 'column',
            alignItems:    'center',
            gap:           '10px',
            animation:     'fadeInUp 0.4s ease forwards',
          }}
        >
          <div
            style={{
              width:          '68px',
              height:         '68px',
              borderRadius:   '18px',
              background:     'rgba(26,12,6,0.65)',
              border:         '2px solid rgba(245,236,215,0.28)',
              display:        'flex',
              alignItems:     'center',
              justifyContent: 'center',
              backdropFilter: 'blur(10px)',
            }}
          >
            <svg width="36" height="36" viewBox="0 0 46 46" fill="none">
              <path d="M23 8C18.03 8 14 12.03 14 17c0 7 9 21 9 21s9-14 9-21c0-4.97-4.03-9-9-9z"
                stroke="#F5ECD7" strokeWidth="2" fill="none" strokeLinejoin="round" />
              <circle cx="23" cy="17" r="3.5" fill="#F5ECD7" opacity="0.9" />
              <rect x="16" y="30" width="4" height="9" rx="1" fill="#F5ECD7" opacity="0.65" />
              <rect x="22" y="27" width="4" height="12" rx="1" fill="#F5ECD7" opacity="0.8" />
              <rect x="28" y="31" width="4" height="8" rx="1" fill="#F5ECD7" opacity="0.65" />
            </svg>
          </div>
          <div style={{ color: 'rgba(245,236,215,0.8)', fontSize: '10px', letterSpacing: '3.5px', textTransform: 'uppercase', fontFamily: 'Inter, Geist, system-ui' }}>
            RetailIQ
          </div>
        </div>
      )}

      <style>{`
        @keyframes rippleIn {
          from { opacity: 0; transform: scale(1.06); }
          to   { opacity: 1; transform: scale(1); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
};
