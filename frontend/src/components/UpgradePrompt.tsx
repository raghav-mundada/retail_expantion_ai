/**
 * UpgradePrompt — inline gating component.
 * Drop in wherever a Pro feature is restricted:
 *   if (!isPro) return <UpgradePrompt feature="AI Simulation" />;
 */
import { useNavigate } from 'react-router-dom';
import { Lock, Zap } from 'lucide-react';

interface Props {
  feature:     string;
  description?: string;
  compact?:    boolean;
}

export function UpgradePrompt({ feature, description, compact = false }: Props) {
  const navigate = useNavigate();

  if (compact) {
    return (
      <button
        onClick={() => navigate('/pricing')}
        className="inline-flex items-center gap-1.5 text-xs text-mocha hover:text-graphite transition-colors"
      >
        <Lock size={11} strokeWidth={2.5} />
        Upgrade to unlock {feature}
      </button>
    );
  }

  return (
    <div
      className="relative flex flex-col items-center justify-center text-center p-10"
      style={{
        background:  'linear-gradient(160deg, rgba(200,168,130,0.06), rgba(92,61,30,0.04))',
        border:      '1px solid rgba(200,168,130,0.2)',
        minHeight:   '240px',
      }}
    >
      {/* Lock icon */}
      <div
        className="w-14 h-14 flex items-center justify-center mb-5"
        style={{
          background:   'rgba(200,168,130,0.12)',
          border:       '1px solid rgba(200,168,130,0.25)',
        }}
      >
        <Lock size={20} style={{ color: '#C8A882' }} strokeWidth={1.5} />
      </div>

      <div className="label-xs mb-2">PRO FEATURE</div>
      <h3 className="font-display text-xl tracking-tightest mb-2">{feature}</h3>
      <p className="text-xs text-slate max-w-xs leading-relaxed mb-6">
        {description ?? `${feature} is available on the Pro plan. Upgrade to unlock the full RetailIQ agent stack.`}
      </p>

      <button
        onClick={() => navigate('/pricing')}
        className="btn-warm px-6 py-2.5 text-sm flex items-center gap-2"
      >
        <Zap size={13} strokeWidth={2} />
        Upgrade to Pro
      </button>

      <p className="mt-4 text-xs text-mist">
        Includes 7-day free trial · Cancel anytime
      </p>
    </div>
  );
}
