/**
 * BillingPage — /billing
 * Shows current plan, subscription dates, cancellation state,
 * and a "Manage Billing" button that opens the Stripe Customer Portal.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft, CreditCard, CheckCircle, Clock, AlertTriangle,
  Loader2, ExternalLink, Shield, Zap,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { createPortalSession } from '../lib/stripe';
import { Brand } from '../components/Brand';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(iso));
}

function daysSince(iso: string | null): number {
  if (!iso) return 999;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

export function BillingPage() {
  const navigate  = useNavigate();
  const [params]  = useSearchParams();
  const { user, profile, plan, isPro, accessToken, loading, refreshProfile } = useAuth();

  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError,   setPortalError]   = useState<string | null>(null);
  const [justUpgraded,  setJustUpgraded]  = useState(false);

  // After a successful Checkout redirect, refresh the profile
  useEffect(() => {
    if (params.get('checkout') === 'success') {
      setJustUpgraded(true);
      const t = setTimeout(() => refreshProfile(), 1500); // wait for webhook to process
      return () => clearTimeout(t);
    }
  }, [params, refreshProfile]);

  // Redirect to signin if not authenticated
  useEffect(() => {
    if (!loading && !user) navigate('/pricing');
  }, [loading, user, navigate]);

  async function handleManageBilling() {
    setPortalLoading(true);
    setPortalError(null);
    try {
      const url = await createPortalSession(accessToken!);
      window.location.href = url;
    } catch (e: any) {
      setPortalError(e.message ?? 'Could not open billing portal.');
      setPortalLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-mocha" />
      </div>
    );
  }

  const cancelAtEnd    = profile?.subscription_cancel_at_period_end ?? false;
  const periodEnd      = profile?.subscription_period_end ?? null;
  const startDate      = profile?.subscription_start_date ?? null;
  const daysSubscribed = daysSince(startDate);
  const inFirstMonth   = daysSubscribed < 31;

  // Cancellation messaging per spec
  const cancellationMessage = cancelAtEnd
    ? inFirstMonth
      ? `Trial ends on ${fmtDate(periodEnd)}`
      : `Subscription ends on ${fmtDate(periodEnd)}`
    : null;

  const fadeUp = {
    hidden:  { opacity: 0, y: 12 },
    visible: (i: number) => ({
      opacity: 1, y: 0,
      transition: { duration: 0.4, delay: i * 0.06, ease: 'easeOut' as const },
    }),
  };

  return (
    <div className="min-h-screen bg-paper">
      {/* Nav */}
      <header className="hairline-b bg-paper/90 backdrop-blur-md sticky top-0 z-50">
        <div className="px-6 lg:px-10 h-16 flex items-center justify-between max-w-[900px] mx-auto">
          <button onClick={() => navigate('/')} className="cursor-pointer">
            <Brand />
          </button>
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-xs text-graphite hover:text-ink transition-colors"
          >
            <ArrowLeft size={14} />
            Back to app
          </button>
        </div>
      </header>

      <main className="max-w-[900px] mx-auto px-6 lg:px-10 py-16">
        <motion.div initial="hidden" animate="visible" variants={fadeUp} custom={0}>
          <div className="label-xs mb-4">BILLING & SUBSCRIPTION</div>
          <h1 className="display-md mb-2">Account overview</h1>
          <p className="text-sm text-slate">
            {user?.email}
          </p>
        </motion.div>

        {/* Success flash */}
        {justUpgraded && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            className="mt-8 flex items-center gap-3 p-4 bg-[#EBF5EE] border border-[#9ED0B0] text-emerald text-sm"
          >
            <CheckCircle size={16} />
            Payment successful — your Pro access is now active. Welcome aboard!
          </motion.div>
        )}

        <div className="mt-10 grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Plan status card */}
          <motion.div
            className="lg:col-span-2 card p-8"
            initial="hidden" animate="visible" variants={fadeUp} custom={1}
          >
            <div className="flex items-start justify-between mb-6">
              <div>
                <div className="label-xs mb-2">CURRENT PLAN</div>
                <div className="flex items-center gap-3">
                  <span className="font-display text-3xl tracking-tightest">
                    {plan === 'free' ? 'Starter' : plan === 'team' ? 'Team' : 'Pro'}
                  </span>
                  <span
                    className="px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest"
                    style={{
                      background: isPro ? 'rgba(200,168,130,0.15)' : 'rgba(92,61,30,0.08)',
                      border:     `1px solid ${isPro ? 'rgba(200,168,130,0.4)' : 'rgba(200,168,130,0.2)'}`,
                      color:      isPro ? '#A07850' : '#8B6F4E',
                    }}
                  >
                    {isPro ? 'Active' : 'Free'}
                  </span>
                </div>
              </div>

              {!isPro && (
                <button
                  onClick={() => navigate('/pricing')}
                  className="btn-warm px-5 py-2.5 text-xs"
                >
                  Upgrade to Pro
                </button>
              )}
            </div>

            {/* Cancellation warning */}
            {cancellationMessage && (
              <div className="flex items-center gap-3 p-3 mb-6 bg-[#FBF3E6] border border-[#E8C98A] text-amber text-xs">
                <AlertTriangle size={14} className="flex-shrink-0" />
                {cancellationMessage}
              </div>
            )}

            {/* Subscription details */}
            <div className="grid grid-cols-2 gap-4">
              {[
                {
                  label: 'Plan start',
                  value: fmtDate(startDate),
                  icon:  <Clock size={13} />,
                },
                {
                  label: isPro ? (cancelAtEnd ? 'Access until' : 'Next renewal') : 'Resets',
                  value: isPro ? fmtDate(periodEnd) : '1st of next month',
                  icon:  <CreditCard size={13} />,
                },
              ].map((item) => (
                <div key={item.label} className="bg-paper p-4">
                  <div className="flex items-center gap-1.5 mb-2 text-slate">
                    {item.icon}
                    <span className="label-xs">{item.label}</span>
                  </div>
                  <div className="text-sm font-medium text-ink">{item.value}</div>
                </div>
              ))}
            </div>

            {/* Manage billing */}
            {isPro && (
              <div className="mt-6 pt-6 hairline-t">
                {portalError && (
                  <p className="text-xs text-crimson mb-3">{portalError}</p>
                )}
                <button
                  onClick={handleManageBilling}
                  disabled={portalLoading}
                  className="btn-secondary flex items-center gap-2 text-sm"
                >
                  {portalLoading
                    ? <Loader2 size={14} className="animate-spin" />
                    : <ExternalLink size={14} />
                  }
                  Manage Billing
                </button>
                <p className="text-xs text-slate mt-2">
                  Update payment method, download invoices, or cancel your subscription via Stripe.
                </p>
              </div>
            )}
          </motion.div>

          {/* Usage + feature list */}
          <motion.div
            className="space-y-4"
            initial="hidden" animate="visible" variants={fadeUp} custom={2}
          >
            {/* Usage meter */}
            <div className="card p-6">
              <div className="label-xs mb-4">USAGE THIS MONTH</div>
              {isPro ? (
                <div className="flex items-center gap-2">
                  <Zap size={14} className="text-mocha" />
                  <span className="text-sm text-ink font-medium">Unlimited</span>
                </div>
              ) : (
                <>
                  <div className="text-3xl font-display tabular mb-1">
                    {profile?.analyses_used_this_month ?? 0}
                    <span className="text-lg text-slate"> / 3</span>
                  </div>
                  <div className="text-xs text-slate mb-3">analyses run</div>
                  <div className="h-1.5 bg-bone overflow-hidden">
                    <div
                      className="h-full bg-mocha transition-all duration-500"
                      style={{ width: `${Math.min(((profile?.analyses_used_this_month ?? 0) / 3) * 100, 100)}%` }}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Pro features */}
            <div className="card p-6">
              <div className="label-xs mb-4">
                {isPro ? 'YOUR FEATURES' : 'UNLOCK WITH PRO'}
              </div>
              <ul className="space-y-2.5">
                {[
                  { label: 'AI Simulation',     pro: true },
                  { label: 'AI Debate',          pro: true },
                  { label: 'TinyFish intel',     pro: true },
                  { label: 'Unlimited analyses', pro: true },
                  { label: 'Basic scoring',      pro: false },
                ].map((f) => (
                  <li key={f.label} className={`flex items-center gap-2 text-xs ${f.pro && !isPro ? 'text-mist' : 'text-graphite'}`}>
                    {f.pro && isPro
                      ? <CheckCircle size={12} className="text-emerald flex-shrink-0" strokeWidth={2.5} />
                      : !f.pro
                      ? <Shield size={12} className="text-slate flex-shrink-0" strokeWidth={2} />
                      : <span className="w-3 h-3 flex-shrink-0" />
                    }
                    {f.label}
                  </li>
                ))}
              </ul>
              {!isPro && (
                <button
                  onClick={() => navigate('/pricing')}
                  className="mt-4 w-full btn-warm text-xs py-2"
                >
                  Upgrade to Pro →
                </button>
              )}
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  );
}
