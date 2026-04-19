/**
 * PricingPage — /pricing
 * Full-page pricing with Monthly / Annual toggle and Stripe Checkout redirect.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Check, Cpu, Sparkles, TrendingUp, Zap, ArrowLeft, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { PLANS, createCheckoutSession, type BillingInterval } from '../lib/stripe';
import { AuthModal } from '../components/AuthModal';
import { Brand } from '../components/Brand';

export function PricingPage() {
  const navigate    = useNavigate();
  const { user, isPro, accessToken } = useAuth();

  const [interval,    setInterval]    = useState<BillingInterval>('monthly');
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const [showAuth,    setShowAuth]    = useState(false);

  const price    = interval === 'monthly' ? PLANS.pro.monthlyPrice : Math.round(PLANS.pro.annualPrice / 12);
  const priceId  = interval === 'monthly' ? PLANS.pro.priceIds.monthly : PLANS.pro.priceIds.annual;

  async function handleUpgrade() {
    if (!user) { setShowAuth(true); return; }
    if (isPro)  { navigate('/billing'); return; }

    setLoading(true);
    setError(null);
    try {
      const url = await createCheckoutSession(priceId, interval, accessToken!);
      window.location.href = url;
    } catch (e: any) {
      setError(e.message ?? 'Something went wrong. Please try again.');
      setLoading(false);
    }
  }

  const fadeUp = {
    hidden:  { opacity: 0, y: 16 },
    visible: (i: number) => ({
      opacity: 1, y: 0,
      transition: { duration: 0.45, delay: i * 0.08, ease: 'easeOut' as const },
    }),
  };

  return (
    <div className="min-h-screen bg-paper">
      {/* Nav */}
      <header className="hairline-b bg-paper/90 backdrop-blur-md sticky top-0 z-50">
        <div className="px-6 lg:px-10 h-16 flex items-center justify-between max-w-[1200px] mx-auto">
          <button onClick={() => navigate('/')} className="cursor-pointer">
            <Brand />
          </button>
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-xs text-graphite hover:text-ink transition-colors"
          >
            <ArrowLeft size={14} />
            Back
          </button>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-6 lg:px-10 py-20">
        {/* Hero */}
        <motion.div
          className="text-center mb-16"
          initial="hidden" animate="visible" variants={fadeUp} custom={0}
        >
          <div className="label-xs mb-6">RETAILIQ PRICING</div>
          <h1 className="display-lg mb-5">
            Intelligence that<br />
            <em className="italic">pays for itself.</em>
          </h1>
          <p className="text-graphite max-w-lg mx-auto text-sm leading-relaxed">
            One wrong site decision costs millions. RetailIQ Pro gives you the full
            agent stack — live TinyFish intel, Monte Carlo simulation, and AI debate —
            to get it right before you sign the lease.
          </p>
        </motion.div>

        {/* Billing toggle */}
        <motion.div
          className="flex justify-center mb-12"
          initial="hidden" animate="visible" variants={fadeUp} custom={1}
        >
          <div className="flex items-center bg-bone border border-hairline p-1 gap-1">
            {(['monthly', 'annual'] as BillingInterval[]).map((opt) => (
              <button
                key={opt}
                onClick={() => setInterval(opt)}
                className={`px-5 py-2 text-xs font-medium transition-all duration-[180ms] ${
                  interval === opt
                    ? 'bg-ink text-snow'
                    : 'text-graphite hover:text-ink'
                }`}
              >
                {opt === 'monthly' ? 'Monthly' : 'Annual'}
                {opt === 'annual' && (
                  <span className="ml-2 text-[9px] uppercase tracking-wider text-emerald font-mono">
                    Save ${PLANS.pro.annualSavings}
                  </span>
                )}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Plan cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-3xl mx-auto">

          {/* Free card */}
          <motion.div
            className="card p-8"
            initial="hidden" animate="visible" variants={fadeUp} custom={2}
          >
            <div className="label-xs mb-4">STARTER</div>
            <div className="font-display text-5xl leading-none mb-1 tabular">$0</div>
            <div className="text-xs text-slate mb-8">Free forever</div>

            <ul className="space-y-3 mb-8">
              {[
                '3 analyses per month',
                'Demographics & competition scoring',
                'Basic 8-dimension composite score',
                'Map overlay (Minneapolis Metro)',
              ].map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-graphite">
                  <Check size={13} className="mt-0.5 flex-shrink-0 text-slate" strokeWidth={2.5} />
                  {f}
                </li>
              ))}
              {[
                'AI Simulation canvas',
                'AI Debate (Bull/Bear)',
                'TinyFish live intel',
              ].map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-mist line-through">
                  <span className="w-[13px] h-[13px] mt-0.5 flex-shrink-0" />
                  {f}
                </li>
              ))}
            </ul>

            <button
              onClick={() => user ? navigate('/') : setShowAuth(true)}
              className="w-full btn-secondary py-3"
            >
              {user ? 'Current plan' : 'Get started free'}
            </button>
          </motion.div>

          {/* Pro card */}
          <motion.div
            className="relative p-8"
            style={{
              background:     'linear-gradient(160deg, #2C1810 0%, #5C3D1E 60%, #3B2007 100%)',
              border:         '1px solid rgba(200,168,130,0.25)',
              boxShadow:      '0 20px 60px rgba(44,24,16,0.3)',
            }}
            initial="hidden" animate="visible" variants={fadeUp} custom={3}
          >
            {/* Badge */}
            <div className="absolute -top-3 left-8">
              <span
                className="px-3 py-1 text-[10px] font-mono uppercase tracking-widest"
                style={{ background: '#C8A882', color: '#1A0C06' }}
              >
                Most popular
              </span>
            </div>

            <div className="label-xs mb-4" style={{ color: 'rgba(200,168,130,0.7)' }}>
              PRO PLAN
            </div>
            <div className="flex items-end gap-2 mb-1">
              <div
                className="font-display text-5xl leading-none tabular"
                style={{ color: '#F5EFE6' }}
              >
                ${price}
              </div>
              <div className="text-xs pb-2" style={{ color: 'rgba(200,168,130,0.6)' }}>
                /mo{interval === 'annual' ? ' · billed annually' : ''}
              </div>
            </div>
            <div className="text-xs mb-8" style={{ color: 'rgba(200,168,130,0.5)' }}>
              {interval === 'annual'
                ? `$${PLANS.pro.annualPrice}/year · save $${PLANS.pro.annualSavings}`
                : '7-day free trial included'
              }
            </div>

            <ul className="space-y-3 mb-8">
              {PLANS.pro.features.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm" style={{ color: 'rgba(245,239,230,0.85)' }}>
                  <Check size={13} className="mt-0.5 flex-shrink-0" style={{ color: '#C8A882' }} strokeWidth={2.5} />
                  {f}
                </li>
              ))}
            </ul>

            {error && (
              <p className="text-xs text-red-300 mb-3">{error}</p>
            )}

            <button
              onClick={handleUpgrade}
              disabled={loading || isPro}
              className="w-full py-3 font-medium text-sm flex items-center justify-center gap-2 transition-all duration-[180ms] disabled:opacity-60"
              style={{
                background:    isPro ? 'rgba(200,168,130,0.2)' : 'linear-gradient(135deg, #C8A882, #A07850)',
                color:         isPro ? 'rgba(200,168,130,0.7)' : '#1A0C06',
                border:        '1px solid rgba(200,168,130,0.3)',
              }}
              onMouseEnter={e => { if (!isPro && !loading) (e.currentTarget as HTMLButtonElement).style.filter = 'brightness(1.08)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.filter = ''; }}
            >
              {loading
                ? <><Loader2 size={14} className="animate-spin" /> Redirecting to Stripe…</>
                : isPro ? 'Current plan'
                : !user  ? 'Start free trial'
                : `Upgrade to Pro · $${price}/mo`
              }
            </button>
          </motion.div>
        </div>

        {/* Feature icons strip */}
        <motion.div
          className="grid grid-cols-2 lg:grid-cols-4 gap-0 hairline mt-16 max-w-3xl mx-auto"
          initial="hidden" animate="visible" variants={fadeUp} custom={5}
        >
          {[
            { icon: <Cpu size={18} strokeWidth={1.5} />,       label: 'Agent Simulation', sub: '220 household agents' },
            { icon: <Sparkles size={18} strokeWidth={1.5} />,  label: 'AI Debate',        sub: 'Bull · Bear · Verdict' },
            { icon: <TrendingUp size={18} strokeWidth={1.5} />,label: 'Revenue Forecast', sub: '24-month Monte Carlo' },
            { icon: <Zap size={18} strokeWidth={1.5} />,       label: 'Live Intel',       sub: 'TinyFish web scraping' },
          ].map((item, i) => (
            <div key={i} className={`p-6 bg-snow ${i > 0 ? 'border-l border-hairline' : ''}`}>
              <div className="text-mocha mb-3">{item.icon}</div>
              <div className="text-sm font-medium text-ink mb-1">{item.label}</div>
              <div className="text-xs text-slate">{item.sub}</div>
            </div>
          ))}
        </motion.div>

        {/* FAQ */}
        <motion.div
          className="mt-20 max-w-2xl mx-auto"
          initial="hidden" animate="visible" variants={fadeUp} custom={6}
        >
          <div className="label-xs mb-8 text-center">FREQUENTLY ASKED</div>
          <div className="space-y-0 hairline">
            {[
              {
                q: 'Is there a free trial?',
                a: "Yes \u2014 Pro includes a 7-day free trial for new subscribers. No card required to sign up; you'll be prompted at checkout.",
              },
              {
                q: 'What happens if I cancel?',
                a: 'Access continues until the end of your billing period. After that, your account reverts to the Starter plan (3 analyses/month).',
              },
              {
                q: 'Can I switch between monthly and annual?',
                a: 'Yes — manage your billing interval at any time via the Stripe Customer Portal under /billing.',
              },
              {
                q: 'Is Minneapolis the only supported market?',
                a: 'Currently yes. US-wide market support (any ZIP code or metro) is on our roadmap for later this year.',
              },
            ].map((item) => (
              <details key={item.q} className="group p-5 bg-snow hairline-b last:border-0 cursor-pointer">
                <summary className="text-sm font-medium text-ink list-none flex items-center justify-between">
                  {item.q}
                  <span className="text-mist group-open:rotate-180 transition-transform">▾</span>
                </summary>
                <p className="mt-3 text-sm text-graphite leading-relaxed">{item.a}</p>
              </details>
            ))}
          </div>
        </motion.div>
      </main>

      {showAuth && (
        <AuthModal
          defaultMode="signup"
          prompt="Create a free account to get started"
          onClose={() => setShowAuth(false)}
        />
      )}
    </div>
  );
}
