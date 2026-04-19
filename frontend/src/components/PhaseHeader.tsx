import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, LogOut, CreditCard, ChevronDown, Zap } from 'lucide-react';
import { Brand } from './Brand';
import { useAuth } from '../context/AuthContext';

const PHASES = [
  { id: 1, label: 'Locate' },
  { id: 2, label: 'Ingest' },
  { id: 3, label: 'Inspect' },
  { id: 4, label: 'Decide' },
];

interface Props {
  current:     number;
  onReset?:    () => void;
  onOpenAuth?: () => void;
}

export function PhaseHeader({ current, onReset, onOpenAuth }: Props) {
  const navigate                   = useNavigate();
  const { user, profile, isPro, plan, analysesLeft, signOut } = useAuth();
  const [menuOpen, setMenuOpen]    = useState(false);

  async function handleSignOut() {
    setMenuOpen(false);
    await signOut();
  }

  return (
    <header className="hairline-b bg-paper/90 backdrop-blur-md sticky top-0 z-[1100]">
      <div className="px-6 lg:px-10 h-16 flex items-center justify-between">
        {/* Logo */}
        <button onClick={onReset} className="cursor-pointer flex-shrink-0">
          <Brand />
        </button>

        {/* Phase stepper */}
        <nav className="hidden md:flex items-center gap-1">
          {PHASES.map((p, i) => {
            const active = current === p.id;
            const done   = current > p.id;
            return (
              <div key={p.id} className="flex items-center">
                <div className={`flex items-center gap-2 px-3 py-1 ${active ? 'text-ink' : done ? 'text-graphite' : 'text-mist'}`}>
                  <span className={`font-mono text-[10px] tabular ${active ? 'text-emerald' : ''}`}>
                    {String(p.id).padStart(2, '0')}
                  </span>
                  <span className="text-xs tracking-snug font-medium">{p.label}</span>
                </div>
                {i < PHASES.length - 1 && <span className="text-mist text-xs">·</span>}
              </div>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Pricing link — only shown when not pro */}
          {!isPro && (
            <button
              onClick={() => navigate('/pricing')}
              className="hidden lg:flex items-center gap-1.5 text-xs text-mocha hover:text-graphite transition-colors"
            >
              <Zap size={12} strokeWidth={2.5} />
              Upgrade to Pro
            </button>
          )}

          {/* Plan badge */}
          {isPro && (
            <span
              className="hidden lg:inline px-2 py-1 text-[9px] font-mono uppercase tracking-widest"
              style={{ background: 'rgba(200,168,130,0.12)', border: '1px solid rgba(200,168,130,0.3)', color: '#A07850' }}
            >
              Pro
            </span>
          )}

          {/* Live indicator */}
          <span className="label-xs hidden lg:inline text-slate">MINNEAPOLIS · MN</span>
          <span className="h-2 w-2 rounded-full bg-emerald animate-pulse flex-shrink-0" />

          {/* Auth area */}
          {user ? (
            <div className="relative">
              <button
                onClick={() => setMenuOpen(v => !v)}
                className="flex items-center gap-2 px-3 py-1.5 bg-bone border border-hairline hover:border-mocha transition-all duration-[180ms] text-xs text-graphite"
              >
                <User size={12} strokeWidth={2} />
                <span className="hidden sm:inline max-w-[100px] truncate">
                  {profile?.full_name || user.email?.split('@')[0]}
                </span>
                <ChevronDown size={11} className={`transition-transform duration-150 ${menuOpen ? 'rotate-180' : ''}`} />
              </button>

              {menuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-[10]"
                    onClick={() => setMenuOpen(false)}
                    aria-hidden="true"
                  />
                  <div
                    className="absolute right-0 top-full mt-1 w-52 bg-snow border border-hairline shadow-lg z-[20] py-1"
                    style={{ boxShadow: '0 10px 40px rgba(44,24,16,0.12)' }}
                  >
                    {/* Account info */}
                    <div className="px-4 py-3 hairline-b">
                      <div className="text-xs font-medium text-ink truncate">{user.email}</div>
                      <div className="text-[10px] text-slate mt-0.5 capitalize">{plan} plan</div>
                      {!isPro && analysesLeft !== null && (
                        <div className="text-[10px] text-amber mt-0.5">
                          {analysesLeft} analyse{analysesLeft !== 1 ? 's' : ''} left this month
                        </div>
                      )}
                    </div>

                    {/* Menu items */}
                    <button
                      onClick={() => { setMenuOpen(false); navigate('/billing'); }}
                      className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs text-graphite hover:bg-bone hover:text-ink transition-colors"
                    >
                      <CreditCard size={13} strokeWidth={1.5} />
                      Billing & subscription
                    </button>

                    {!isPro && (
                      <button
                        onClick={() => { setMenuOpen(false); navigate('/pricing'); }}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs text-mocha hover:bg-bone transition-colors font-medium"
                      >
                        <Zap size={13} strokeWidth={2} />
                        Upgrade to Pro →
                      </button>
                    )}

                    <div className="hairline-t mt-1 pt-1">
                      <button
                        onClick={handleSignOut}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-xs text-graphite hover:bg-bone hover:text-ink transition-colors"
                      >
                        <LogOut size={13} strokeWidth={1.5} />
                        Sign out
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="flex items-center gap-2 px-3 py-1.5 text-xs text-graphite border border-hairline hover:border-mocha hover:text-ink bg-snow transition-all duration-[180ms]"
            >
              <User size={12} strokeWidth={2} />
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
