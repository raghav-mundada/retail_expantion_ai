import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, History, Sparkles, ShieldCheck, Loader2 } from "lucide-react";

import { useAuth } from "../lib/auth";

interface Props {
  open: boolean;
  onClose: () => void;
  /** Optional context-aware copy — e.g. "Sign in to view your search history" */
  intent?: "default" | "history" | "save";
}

const INTENT_COPY: Record<string, { eyebrow: string; headline: React.ReactNode; sub: string }> = {
  default: {
    eyebrow: "Sign in",
    headline: <>Save every <em className="italic font-display">scout</em>.</>,
    sub: "Free, no credit card. Your past searches and reports stay one click away.",
  },
  history: {
    eyebrow: "Access history",
    headline: <>Pick up <em className="italic font-display">where you left off</em>.</>,
    sub: "Sign in to revisit every location you've analyzed across sessions.",
  },
  save: {
    eyebrow: "Save this analysis",
    headline: <>Don't lose this <em className="italic font-display">corner</em>.</>,
    sub: "Sign in to attach this search to your account and revisit it later.",
  },
};

const PERKS = [
  { icon: History,      title: "Past searches",   desc: "Every run, indexed by location and date." },
  { icon: Sparkles,     title: "AI reports",      desc: "Re-open agent debates without re-running them." },
  { icon: ShieldCheck,  title: "Private to you",  desc: "Auth via Google. We never see your password." },
];

export function AuthModal({ open, onClose, intent = "default" }: Props) {
  const { signInWithGoogle, user } = useAuth();
  const [busy, setBusy]     = useState(false);
  const [error, setError]   = useState<string | null>(null);

  // Auto-close once the user is authenticated.
  useEffect(() => {
    if (open && user) onClose();
  }, [open, user, onClose]);

  // ESC to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const copy = INTENT_COPY[intent] ?? INTENT_COPY.default;

  async function handleGoogle() {
    setError(null);
    setBusy(true);
    try {
      await signInWithGoogle();
      // The browser navigates away to Google — the modal will be closed by
      // the auto-close effect once the session reappears on return.
    } catch (e: any) {
      setError(e?.message ?? "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="auth-overlay"
          className="fixed inset-0 z-[2000] flex items-center justify-center px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
        >
          {/* Backdrop */}
          <motion.div
            className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          {/* Card */}
          <motion.div
            key="auth-card"
            className="relative w-full max-w-[920px] grid md:grid-cols-[1.15fr_1fr] bg-snow border border-hairline shadow-[0_30px_80px_-20px_rgba(10,10,10,0.25)]"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.99 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* ── LEFT — pitch ─────────────────────────────────────────── */}
            <div className="relative p-10 md:p-12 bg-bone overflow-hidden">
              {/* Decorative grid */}
              <svg
                className="absolute inset-0 w-full h-full text-hairline opacity-60 pointer-events-none"
                aria-hidden
              >
                <defs>
                  <pattern id="auth-grid" width="32" height="32" patternUnits="userSpaceOnUse">
                    <path d="M32 0H0V32" fill="none" stroke="currentColor" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#auth-grid)" />
              </svg>

              {/* Brand mark */}
              <div className="relative flex items-center gap-2 mb-12">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald" />
                <span className="label-xs">ATLAS · RETAIL SITE INTELLIGENCE</span>
              </div>

              <p className="relative label-xs text-emerald mb-4">{copy.eyebrow.toUpperCase()}</p>
              <h2 className="relative font-display text-[clamp(2.5rem,4vw,3.75rem)] leading-[0.95] tracking-tightest text-ink mb-5">
                {copy.headline}
              </h2>
              <p className="relative text-graphite text-sm leading-relaxed max-w-[340px]">
                {copy.sub}
              </p>

              {/* Perks list */}
              <div className="relative mt-10 space-y-4 max-w-[360px]">
                {PERKS.map((p) => (
                  <div key={p.title} className="flex gap-3 items-start">
                    <div className="mt-0.5 h-7 w-7 flex items-center justify-center bg-snow border border-hairline">
                      <p.icon className="w-3.5 h-3.5 text-ink" strokeWidth={1.5} />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-ink">{p.title}</div>
                      <div className="text-xs text-slate leading-snug">{p.desc}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Tiny cite at bottom */}
              <div className="relative absolute-not-needed mt-12 pt-6 border-t border-hairline">
                <p className="label-xs text-slate">
                  Trusted by site-selection teams · Hackathon · 2026
                </p>
              </div>
            </div>

            {/* ── RIGHT — action ───────────────────────────────────────── */}
            <div className="p-10 md:p-12 flex flex-col justify-center relative">
              <button
                onClick={onClose}
                aria-label="Close"
                className="absolute top-4 right-4 h-8 w-8 flex items-center justify-center
                           text-slate hover:text-ink transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.5} />
              </button>

              <p className="label-xs mb-3">Continue with</p>
              <h3 className="font-display text-3xl text-ink leading-tight tracking-tightest mb-8">
                One step. <em className="italic">Then back to the map.</em>
              </h3>

              {/* Google CTA */}
              <button
                onClick={handleGoogle}
                disabled={busy}
                className="group relative w-full flex items-center justify-center gap-3
                           bg-ink text-snow px-6 py-4 text-[15px] font-medium
                           border border-ink hover:bg-graphite transition-colors
                           disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {busy ? (
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2} />
                ) : (
                  <GoogleGlyph />
                )}
                <span>{busy ? "Redirecting to Google…" : "Continue with Google"}</span>
              </button>

              {error && (
                <div className="mt-4 px-3 py-2 bg-red-50 border border-red-200 text-xs text-red-700">
                  {error}
                </div>
              )}

              {/* Divider + privacy note */}
              <div className="mt-6 flex items-center gap-3 text-mist">
                <div className="flex-1 h-px bg-hairline" />
                <span className="font-mono text-[10px] tracking-widest">FREE · NO CREDIT CARD</span>
                <div className="flex-1 h-px bg-hairline" />
              </div>

              <p className="mt-6 text-xs text-slate leading-relaxed">
                By continuing, you agree to let Atlas store your past searches.
                We use Supabase Auth — your Google credentials never touch our servers.
              </p>

              {/* Stay anonymous escape hatch */}
              <button
                onClick={onClose}
                className="mt-8 self-start text-xs text-slate hover:text-ink underline underline-offset-4 decoration-mist hover:decoration-ink transition-colors"
              >
                Continue without an account →
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Inline Google "G" mark — kept here so we don't pull a brand icon dep
// ─────────────────────────────────────────────────────────────────────
function GoogleGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden>
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.49h4.84a4.14 4.14 0 0 1-1.79 2.72v2.26h2.9c1.7-1.56 2.69-3.86 2.69-6.63z"/>
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.9-2.26c-.8.54-1.83.86-3.06.86-2.35 0-4.34-1.59-5.05-3.71H.95v2.34A9 9 0 0 0 9 18z"/>
      <path fill="#FBBC05" d="M3.95 10.71A5.41 5.41 0 0 1 3.66 9c0-.6.1-1.18.29-1.71V4.95H.95A8.99 8.99 0 0 0 0 9c0 1.45.35 2.83.95 4.05l3-2.34z"/>
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.58A8.99 8.99 0 0 0 9 0 9 9 0 0 0 .95 4.95l3 2.34C4.66 5.17 6.65 3.58 9 3.58z"/>
    </svg>
  );
}
