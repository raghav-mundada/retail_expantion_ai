/**
 * SimulationCanvas — Full-screen agentic simulation overlay.
 *
 * Phases:
 *   0  initialize  (0 – 1.8 s)   Agents spawn at random positions, fade in
 *   1  randomize   (1.8 – 4.2 s) Brownian drift — stochastic sampling feel
 *   2  score       (4.2 – 7.0 s) Agents re-colour by visit probability score
 *   3  cluster     (7.0 – 11.0 s) Agents group into 8 typology clusters
 *   4  output      (11.0 – 14.0 s) Agents converge; metrics count up
 *   5  complete    (14 s +)       Canvas dims; results panel slides in
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { X, ChevronRight } from 'lucide-react';
import type { SimulationResult, LocationScore, DemographicsProfile } from '../lib/api';
import { fmtUSD, fmtNum } from '../lib/format';
import { useCountUp } from '../hooks/useCountUp';

/* ── Constants ─────────────────────────────────────────────────────────── */
const N_AGENTS  = 220;
const PHASE_MS  = [0, 1800, 4200, 7000, 11000, 14000] as const;

const TYPOLOGIES = [
  { name: 'Budget Families',    hue: 12,  saturation: 72 },
  { name: 'Mid-Range Families', hue: 33,  saturation: 68 },
  { name: 'Young Professionals',hue: 58,  saturation: 65 },
  { name: 'Affluent Families',  hue: 95,  saturation: 62 },
  { name: 'Senior Households',  hue: 168, saturation: 55 },
  { name: 'Empty Nesters',      hue: 210, saturation: 60 },
  { name: 'Budget Singles',     hue: 265, saturation: 58 },
  { name: 'Transient/Student',  hue: 330, saturation: 64 },
] as const;

const PHASE_LABELS = [
  { label: 'INITIALIZE',  caption: 'Seeding household agent population…'        },
  { label: 'RANDOMIZE',   caption: 'Monte-Carlo sampling — stochastic drift…'   },
  { label: 'SCORE',       caption: 'Computing visit probability per agent…'      },
  { label: 'CLUSTER',     caption: 'Segmenting into behavioural typologies…'    },
  { label: 'OUTPUT',      caption: 'Converging on revenue estimate…'            },
  { label: 'COMPLETE',    caption: 'Simulation converged.'                      },
] as const;

/* ── Types ──────────────────────────────────────────────────────────────── */
interface Agent {
  x: number; y: number;
  vx: number; vy: number;
  tx: number; ty: number;    // cluster target
  cx: number; cy: number;    // canvas centre (for convergence)
  radius: number;
  alpha: number;
  typology: number;          // 0-7
  score: number;             // 0-1 (visit probability)
  hue: number;               // current rendered hue
  targetHue: number;
}

export interface SimulationCanvasProps {
  simulation:   SimulationResult;
  score:        LocationScore;
  demographics: DemographicsProfile;
  brand:        string;
  onClose:      () => void;
}

/* ── Typewriter hook ────────────────────────────────────────────────────── */
function useTypewriter(text: string, active: boolean, speed = 22): string {
  const [displayed, setDisplayed] = useState('');
  useEffect(() => {
    if (!active) { setDisplayed(''); return; }
    setDisplayed('');
    let i = 0;
    const iv = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) clearInterval(iv);
    }, speed);
    return () => clearInterval(iv);
  }, [text, active, speed]);
  return displayed;
}

/* ── MetricRow — typewriter + count-up ─────────────────────────────────── */
interface MetricRowProps {
  label:     string;
  value:     number;
  formatted: string;
  unit?:     string;
  active:    boolean;
  delay:     number;   // ms delay before animation starts
  highlight?: boolean;
}
function MetricRow({ label, value, formatted, unit = '', active, delay, highlight }: MetricRowProps) {
  const [localActive, setLocalActive] = useState(false);
  useEffect(() => {
    if (!active) { setLocalActive(false); return; }
    const t = setTimeout(() => setLocalActive(true), delay);
    return () => clearTimeout(t);
  }, [active, delay]);

  // value is used to trigger count-up animation; formatted is the display string
  useCountUp({ to: value, duration: 900, active: localActive });

  return (
    <div
      style={{
        display:        'flex',
        justifyContent: 'space-between',
        alignItems:     'center',
        padding:        '10px 0',
        borderBottom:   '1px solid rgba(200,168,130,0.12)',
        opacity:        localActive ? 1 : 0,
        transform:      localActive ? 'translateY(0)' : 'translateY(8px)',
        transition:     'opacity 0.45s ease, transform 0.45s ease',
      }}
    >
      <span style={{ fontSize: '11px', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(200,168,130,0.7)', fontFamily: 'Geist Mono, monospace' }}>
        {label}
      </span>
      <span
        style={{
          fontFamily:  'Geist Mono, monospace',
          fontSize:    highlight ? '20px' : '15px',
          fontWeight:  highlight ? 700 : 500,
          color:       highlight ? '#E8C98A' : 'rgba(245,236,215,0.9)',
          textShadow:  highlight ? '0 0 18px rgba(232,201,138,0.4)' : 'none',
          transition:  'text-shadow 0.3s ease',
        }}
      >
        {formatted}{unit}
      </span>
    </div>
  );
}

/* ── Logic breakdown bullet ──────────────────────────────────────────────── */
interface BulletProps {
  symbol: string;
  label: string;
  detail: string;
  active: boolean;
  delay: number;
}
function LogicBullet({ symbol, label, detail, active, delay }: BulletProps) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!active) { setShow(false); return; }
    const t = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(t);
  }, [active, delay]);
  return (
    <div style={{ display: 'flex', gap: '10px', marginBottom: '12px', opacity: show ? 1 : 0, transform: show ? 'none' : 'translateY(6px)', transition: 'opacity 0.4s ease, transform 0.4s ease' }}>
      <div style={{ width: '22px', height: '22px', borderRadius: '4px', background: 'rgba(200,168,130,0.15)', border: '1px solid rgba(200,168,130,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '11px', color: '#C8A882' }}>
        {symbol}
      </div>
      <div>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'rgba(245,236,215,0.9)', marginBottom: '2px' }}>{label}</div>
        <div style={{ fontSize: '11px', color: 'rgba(200,168,130,0.7)', lineHeight: 1.5 }}>{detail}</div>
      </div>
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────────── */
export function SimulationCanvas({ simulation, score, demographics, brand, onClose }: SimulationCanvasProps) {
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const agentsRef   = useRef<Agent[]>([]);
  const phaseRef    = useRef(0);
  const rafRef      = useRef<number>(0);
  const startRef    = useRef<number | null>(null);

  const [phase, setPhase]               = useState(0);
  const [agentsSpawned, setAgentsSpawned] = useState(0);
  const [resultsVisible, setResultsVisible] = useState(false);
  const [logicVisible, setLogicVisible]     = useState(false);
  const canvasW = useRef(0);
  const canvasH = useRef(0);

  /* ── Build cluster centres (8-point ring) ─────────────────────────── */
  const buildClusterCentres = useCallback((W: number, H: number) => {
    const cx = W / 2, cy = H * 0.46;
    const rX = Math.min(W, H) * 0.28;
    const rY = Math.min(W, H) * 0.20;
    return TYPOLOGIES.map((_, i) => {
      const angle = (i / TYPOLOGIES.length) * Math.PI * 2 - Math.PI / 2;
      return { x: cx + Math.cos(angle) * rX, y: cy + Math.sin(angle) * rY };
    });
  }, []);

  /* ── Seed agents ───────────────────────────────────────────────────── */
  const seedAgents = useCallback((W: number, H: number) => {
    const clusters = buildClusterCentres(W, H);
    const cx = W / 2, cy = H * 0.46;
    agentsRef.current = Array.from({ length: N_AGENTS }, (_, i) => {
      const typology = i % TYPOLOGIES.length;
      const t        = TYPOLOGIES[typology];
      const score_v  = 0.1 + Math.random() * 0.85;
      return {
        x:         Math.random() * W,
        y:         Math.random() * H * 0.85,
        vx:        (Math.random() - 0.5) * 1.2,
        vy:        (Math.random() - 0.5) * 1.2,
        tx:        clusters[typology].x + (Math.random() - 0.5) * 50,
        ty:        clusters[typology].y + (Math.random() - 0.5) * 50,
        cx,
        cy,
        radius:    2 + Math.random() * 2.5,
        alpha:     0,
        typology,
        score:     score_v,
        hue:       200 + Math.random() * 60,   // start blue-gray
        targetHue: t.hue,
      } satisfies Agent;
    });
  }, [buildClusterCentres]);

  /* ── Canvas setup ──────────────────────────────────────────────────── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const W = window.innerWidth;
      const H = window.innerHeight;
      canvas.width  = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width  = `${W}px`;
      canvas.style.height = `${H}px`;
      canvasW.current = W;
      canvasH.current = H;
      const ctx = canvas.getContext('2d')!;
      ctx.scale(dpr, dpr);
      seedAgents(W, H);
    };

    resize();
    window.addEventListener('resize', resize, { passive: true });
    return () => window.removeEventListener('resize', resize);
  }, [seedAgents]);

  /* ── Animation loop ────────────────────────────────────────────────── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const animate = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const elapsed = ts - startRef.current;

      // Determine phase
      let p = 0;
      for (let i = PHASE_MS.length - 1; i >= 0; i--) {
        if (elapsed >= PHASE_MS[i]) { p = i; break; }
      }
      if (p !== phaseRef.current) {
        phaseRef.current = p;
        setPhase(p);
        if (p === 5) {
          setTimeout(() => setResultsVisible(true),  200);
          setTimeout(() => setLogicVisible(true),   600);
        }
      }

      const W = canvasW.current;
      const H = canvasH.current;
      const ctx = canvas.getContext('2d')!;
      ctx.clearRect(0, 0, W, H);

      const agents   = agentsRef.current;
      let spawned    = 0;

      for (let i = 0; i < agents.length; i++) {
        const a = agents[i];
        const spawnDelay = (i / agents.length) * 1500;

        /* ─ Phase 0: initialize — staggered spawn ─ */
        if (p === 0) {
          if (elapsed > spawnDelay) {
            a.alpha = Math.min(a.alpha + 0.04, 0.85);
          }
        }

        /* ─ Phase 1: randomize — Brownian motion ─ */
        if (p === 1) {
          a.alpha = Math.min(a.alpha + 0.02, 0.85);
          a.vx += (Math.random() - 0.5) * 0.35;
          a.vy += (Math.random() - 0.5) * 0.35;
          a.vx *= 0.96; a.vy *= 0.96;
          a.x += a.vx; a.y += a.vy;
          // bounce off canvas edges
          if (a.x < a.radius || a.x > W - a.radius) a.vx *= -0.8;
          if (a.y < a.radius || a.y > H * 0.85)     a.vy *= -0.8;
          a.x = Math.max(a.radius, Math.min(W - a.radius, a.x));
          a.y = Math.max(a.radius, Math.min(H * 0.85, a.y));
        }

        /* ─ Phase 2: score — colour transition ─ */
        if (p === 2) {
          a.vx *= 0.97; a.vy *= 0.97;
          a.x += a.vx; a.y += a.vy;
          // Lerp hue toward target
          a.hue += (a.targetHue - a.hue) * 0.04;
          // Agents that will_visit grow slightly
          if (a.score > 0.45) a.radius = Math.min(a.radius + 0.01, 4.5);
        }

        /* ─ Phase 3: cluster — spring toward cluster center ─ */
        if (p === 3) {
          const k = 0.04 + Math.random() * 0.01;
          a.vx += (a.tx - a.x) * k;
          a.vy += (a.ty - a.y) * k;
          a.vx += (Math.random() - 0.5) * 0.25;
          a.vy += (Math.random() - 0.5) * 0.25;
          a.vx *= 0.88; a.vy *= 0.88;
          a.x += a.vx; a.y += a.vy;
          a.hue += (a.targetHue - a.hue) * 0.08;
        }

        /* ─ Phase 4: output — converge to canvas center ─ */
        if (p === 4) {
          const phaseT = (elapsed - PHASE_MS[4]) / (PHASE_MS[5] - PHASE_MS[4]);
          const spring = 0.06 + phaseT * 0.06;
          a.vx += (a.cx - a.x) * spring;
          a.vy += (a.cy - a.y) * spring;
          a.vx *= 0.82; a.vy *= 0.82;
          a.x += a.vx; a.y += a.vy;
          a.alpha = Math.max(0, a.alpha - 0.004);
          a.radius *= 0.992;
        }

        /* ─ Phase 5: fade out ─ */
        if (p >= 5) {
          a.alpha = Math.max(0, a.alpha - 0.018);
        }

        if (a.alpha > 0.01) spawned++;

        /* ─ Draw agent ─ */
        if (a.alpha < 0.01) continue;
        const sat = TYPOLOGIES[a.typology].saturation;
        const lit = 55 + a.score * 18;
        ctx.beginPath();
        ctx.arc(a.x, a.y, a.radius, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${a.hue | 0}, ${sat}%, ${lit}%, ${a.alpha})`;
        ctx.fill();

        // Glow for high-score agents
        if (a.score > 0.6 && p >= 2) {
          ctx.beginPath();
          ctx.arc(a.x, a.y, a.radius * 2.2, 0, Math.PI * 2);
          ctx.fillStyle = `hsla(${a.hue | 0}, ${sat}%, ${lit + 10}%, ${a.alpha * 0.18})`;
          ctx.fill();
        }
      }

      setAgentsSpawned(spawned);

      // Cluster label halos (phase 3+)
      if (p >= 3 && p < 5) {
        const centres = buildClusterCentres(W, H);
        const phaseT  = Math.min(1, (elapsed - PHASE_MS[3]) / 1200);
        ctx.save();
        ctx.globalAlpha = phaseT * 0.55;
        TYPOLOGIES.forEach((t, i) => {
          const c = centres[i];
          const grad = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, 55);
          grad.addColorStop(0, `hsla(${t.hue}, ${t.saturation}%, 65%, 0.10)`);
          grad.addColorStop(1, `hsla(${t.hue}, ${t.saturation}%, 65%, 0)`);
          ctx.beginPath();
          ctx.arc(c.x, c.y, 55, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();
        });
        ctx.restore();
      }

      if (p < 6) rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [buildClusterCentres]);

  /* ── Derived display values ───────────────────────────────────────── */
  const annualRev  = simulation.predicted_annual_revenue_usd;
  const ciLow      = simulation.confidence_interval_low;
  const ciHigh     = simulation.confidence_interval_high;
  const visitPct   = simulation.pct_will_visit * 100;
  const monthlyRev = annualRev / 12;
  const wom        = simulation.word_of_mouth_score;
  const cannib     = simulation.cannibalization_risk;

  /* ── Typewriter headline ─────────────────────────────────────────── */
  const headline  = `${brand} — Year 1 Revenue Estimate: ${fmtUSD(annualRev)}`;
  const displayed = useTypewriter(headline, resultsVisible, 18);

  /* ── Count-up metric values ───────────────────────────────────────── */
  const visitPctDisplay   = `${visitPct.toFixed(1)}%`;
  const monthlyVisitsDisp = fmtNum(simulation.predicted_monthly_visits, true);
  const annualRevDisp     = fmtUSD(annualRev);
  const ciLowDisp         = fmtUSD(ciLow);
  const ciHighDisp        = fmtUSD(ciHigh);
  const share6Disp        = `${(simulation.market_share_6mo * 100).toFixed(1)}%`;
  const share24Disp       = `${(simulation.market_share_24mo * 100).toFixed(1)}%`;

  return (
    <div
      style={{
        position:  'fixed',
        inset:     0,
        zIndex:    9999,
        background:'#1A0C06',
        overflow:  'hidden',
        display:   'flex',
        flexDirection: 'column',
      }}
    >
      {/* ── Canvas ────────────────────────────────────────────────────── */}
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
        aria-hidden="true"
      />

      {/* ── Subtle dot grid ─────────────────────────────────────────── */}
      <div
        style={{
          position:        'absolute',
          inset:           0,
          opacity:         0.04,
          backgroundImage: 'radial-gradient(circle, #C8A882 1px, transparent 1px)',
          backgroundSize:  '28px 28px',
          pointerEvents:   'none',
        }}
      />

      {/* ── Top bar ──────────────────────────────────────────────────── */}
      <div
        style={{
          position:    'relative',
          zIndex:      10,
          display:     'flex',
          alignItems:  'center',
          justifyContent: 'space-between',
          padding:     '16px 24px',
          borderBottom:'1px solid rgba(200,168,130,0.12)',
          background:  'rgba(26,12,6,0.7)',
          backdropFilter: 'blur(10px)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#C8A882', animation: 'glowPulse 2s ease-in-out infinite' }} />
          <span style={{ fontSize: '10px', letterSpacing: '0.22em', textTransform: 'uppercase', color: 'rgba(200,168,130,0.7)', fontFamily: 'Geist Mono, monospace' }}>
            RetailIQ Simulation Engine
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          {/* Phase progress pills */}
          <div style={{ display: 'flex', gap: '6px' }}>
            {PHASE_LABELS.slice(0, 5).map((pl, i) => (
              <div
                key={i}
                style={{
                  padding:      '3px 8px',
                  fontSize:     '9px',
                  letterSpacing:'0.14em',
                  fontFamily:   'Geist Mono, monospace',
                  textTransform:'uppercase',
                  borderRadius: '2px',
                  background:   phase === i ? 'rgba(200,168,130,0.22)' : 'transparent',
                  border:       `1px solid ${phase === i ? 'rgba(200,168,130,0.5)' : 'rgba(200,168,130,0.12)'}`,
                  color:        phase === i ? '#E8C98A' : 'rgba(200,168,130,0.35)',
                  transition:   'all 0.3s ease',
                }}
              >
                {i < phase ? '✓ ' : ''}{pl.label}
              </div>
            ))}
          </div>

          <button
            onClick={onClose}
            style={{
              width:          '32px',
              height:         '32px',
              borderRadius:   '4px',
              background:     'rgba(200,168,130,0.08)',
              border:         '1px solid rgba(200,168,130,0.2)',
              color:          'rgba(200,168,130,0.7)',
              display:        'flex',
              alignItems:     'center',
              justifyContent: 'center',
              cursor:         'pointer',
              transition:     'all 0.18s ease',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(200,168,130,0.18)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(200,168,130,0.08)'; }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* ── Phase label + counter ────────────────────────────────────── */}
      <div
        style={{
          position:  'absolute',
          bottom:    resultsVisible ? '55%' : '8%',
          left:      '50%',
          transform: 'translateX(-50%)',
          zIndex:    10,
          textAlign: 'center',
          transition:'bottom 0.6s cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        {phase < 5 && (
          <>
            <div
              style={{
                fontSize:     '11px',
                letterSpacing:'0.24em',
                textTransform:'uppercase',
                color:        '#E8C98A',
                marginBottom: '8px',
                fontFamily:   'Geist Mono, monospace',
                animation:    'phasePulse 1.4s ease-in-out infinite',
              }}
            >
              Phase {phase + 1} / 5 — {PHASE_LABELS[phase].label}
            </div>
            <div
              style={{
                fontSize:  '13px',
                color:     'rgba(200,168,130,0.65)',
                fontFamily:'Geist, system-ui',
                marginBottom: '14px',
              }}
            >
              {PHASE_LABELS[phase].caption}
            </div>
            <div
              style={{
                fontFamily:  'Geist Mono, monospace',
                fontSize:    '12px',
                color:       'rgba(200,168,130,0.5)',
              }}
            >
              {agentsSpawned.toLocaleString()} / {N_AGENTS.toLocaleString()} agents active
            </div>
          </>
        )}
      </div>

      {/* ── Results panel ───────────────────────────────────────────── */}
      <div
        style={{
          position:     'absolute',
          bottom:       0,
          left:         0,
          right:        0,
          height:       '54%',
          background:   'linear-gradient(180deg, rgba(26,12,6,0) 0%, rgba(26,12,6,0.97) 8%, rgba(20,10,4,1) 100%)',
          transform:    resultsVisible ? 'translateY(0)' : 'translateY(100%)',
          transition:   'transform 0.65s cubic-bezier(0.4,0,0.2,1)',
          zIndex:       20,
          overflowY:    'auto',
          padding:      '28px 28px 32px',
          display:      'flex',
          gap:          '32px',
        }}
      >
        {/* Left — typewriter headline + logic breakdown */}
        <div style={{ flex: '1 1 0', minWidth: 0 }}>
          {/* Typewriter headline */}
          <div
            style={{
              fontFamily:  'Geist, system-ui',
              fontSize:    '15px',
              color:       'rgba(245,236,215,0.9)',
              marginBottom:'20px',
              lineHeight:  1.5,
              minHeight:   '44px',
            }}
          >
            {displayed}
            {resultsVisible && displayed.length < headline.length && (
              <span className="cursor-blink" style={{ color: '#C8A882', marginLeft: '1px' }}>|</span>
            )}
          </div>

          {/* Logic breakdown */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(200,168,130,0.5)', marginBottom: '14px', fontFamily: 'Geist Mono, monospace' }}>
              Model Logic
            </div>

            <LogicBullet symbol="P" label="Visit Probability"
              detail={`P(visit) = brand_pref × distance_decay × competitor_pull × novelty_bonus → ${visitPct.toFixed(1)}% of trade-area households`}
              active={logicVisible} delay={0} />
            <LogicBullet symbol="$" label="Revenue Estimation"
              detail={`Monthly Rev = ${fmtNum(demographics.household_count)} HHs × ${(visitPct/100).toFixed(3)} × avg_spend ($${Math.round(monthlyRev / simulation.predicted_monthly_visits)}/visit)`}
              active={logicVisible} delay={180} />
            <LogicBullet symbol="±" label="Confidence Interval"
              detail={`Low = revenue × 0.75 (conservative ramp); High = revenue × 1.30 (word-of-mouth acceleration). WoM score: ${(wom * 100).toFixed(0)}`}
              active={logicVisible} delay={360} />
            <LogicBullet symbol="∩" label="Market Share & Cannibalization"
              detail={`6-mo share ${share6Disp} → 24-mo share ${share24Disp}. Cannibalization risk: ${(cannib * 100).toFixed(1)}% (own-brand overlap within radius)`}
              active={logicVisible} delay={540} />
            <LogicBullet symbol="⚖" label="Score Weighting"
              detail={`Composite score ${score.total_score.toFixed(0)}/100 — Demand 20%, Competition 18%, Hotspot 15%, Neighborhood+BrandFit 24%, Accessibility 12%, Risk+Amenity 11%`}
              active={logicVisible} delay={720} />
          </div>
        </div>

        {/* Right — metric rows with count-up */}
        <div
          style={{
            width:         '280px',
            flexShrink:    0,
            borderLeft:    '1px solid rgba(200,168,130,0.12)',
            paddingLeft:   '28px',
          }}
        >
          <div style={{ fontSize: '10px', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(200,168,130,0.5)', marginBottom: '14px', fontFamily: 'Geist Mono, monospace' }}>
            Simulation Outputs
          </div>

          <MetricRow label="Annual Revenue" value={annualRev} formatted={annualRevDisp} active={resultsVisible} delay={200} highlight />
          <MetricRow label="CI Low"         value={ciLow}     formatted={ciLowDisp}   active={resultsVisible} delay={400} />
          <MetricRow label="CI High"        value={ciHigh}    formatted={ciHighDisp}  active={resultsVisible} delay={500} />
          <MetricRow label="Visit Propensity" value={visitPct} formatted={visitPctDisplay} active={resultsVisible} delay={620} />
          <MetricRow label="Monthly Visits" value={simulation.predicted_monthly_visits} formatted={monthlyVisitsDisp} active={resultsVisible} delay={720} />
          <MetricRow label="Market Share 6-mo"  value={simulation.market_share_6mo * 100} formatted={share6Disp}  active={resultsVisible} delay={820} />
          <MetricRow label="Market Share 24-mo" value={simulation.market_share_24mo * 100} formatted={share24Disp} active={resultsVisible} delay={900} />

          {/* Composite score badge */}
          {resultsVisible && (
            <div
              style={{
                marginTop:  '20px',
                padding:    '12px',
                border:     '1px solid rgba(200,168,130,0.25)',
                background: 'rgba(200,168,130,0.06)',
                display:    'flex',
                alignItems: 'center',
                gap:        '12px',
              }}
            >
              <div
                style={{
                  fontSize:   '28px',
                  fontFamily: 'Geist Mono, monospace',
                  fontWeight: 700,
                  color:      score.total_score >= 75 ? '#6fba7a' : score.total_score >= 55 ? '#C8A882' : '#e07070',
                  lineHeight: 1,
                }}
              >
                {score.total_score.toFixed(0)}
              </div>
              <div>
                <div style={{ fontSize: '10px', color: 'rgba(200,168,130,0.6)', letterSpacing: '0.16em', textTransform: 'uppercase', fontFamily: 'Geist Mono, monospace' }}>
                  Composite Score
                </div>
                <div style={{ fontSize: '12px', color: 'rgba(245,236,215,0.85)', marginTop: '2px' }}>
                  {score.rank_label}
                </div>
              </div>
            </div>
          )}

          {/* Close / view full report */}
          {resultsVisible && (
            <button
              onClick={onClose}
              style={{
                marginTop:      '16px',
                width:          '100%',
                padding:        '11px',
                background:     'linear-gradient(135deg, #A07850, #C8A882)',
                border:         'none',
                color:          '#1A0C06',
                fontFamily:     'Geist, system-ui',
                fontSize:       '13px',
                fontWeight:     600,
                letterSpacing:  '0.04em',
                cursor:         'pointer',
                display:        'flex',
                alignItems:     'center',
                justifyContent: 'center',
                gap:            '6px',
                transition:     'filter 0.18s ease, transform 0.18s ease',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.filter = 'brightness(1.08)'; (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.filter = 'none'; (e.currentTarget as HTMLButtonElement).style.transform = 'none'; }}
            >
              View Full Report <ChevronRight size={14} />
            </button>
          )}
        </div>
      </div>

      <style>{`
        @keyframes glowPulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(200,168,130,0); }
          50%       { box-shadow: 0 0 10px 3px rgba(200,168,130,0.3); }
        }
        @keyframes phasePulse {
          0%, 100% { opacity: 0.65; }
          50%       { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
