import { useEffect, useRef, useState } from "react";
import { History, LogOut, User as UserIcon } from "lucide-react";

import { useAuth } from "../context/AuthContext";

interface Props {
  onSignInClick: () => void;
  onHistoryClick: () => void;
}

export function UserMenu({ onSignInClick, onHistoryClick }: Props) {
  const { user, loading, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (loading) {
    return <div className="h-8 w-20 bg-bone animate-pulse" aria-label="loading session" />;
  }

  if (!user) {
    return (
      <button
        onClick={onSignInClick}
        className="group inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium
                   text-ink border border-hairline hover:border-ink transition-colors"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-emerald" />
        Sign in
        <span className="hidden sm:inline text-slate group-hover:text-graphite transition-colors">
          to save progress
        </span>
      </button>
    );
  }

  const meta = (user.user_metadata ?? {}) as Record<string, any>;
  const name   = meta.full_name || meta.name || user.email?.split("@")[0] || "Member";
  const email  = user.email ?? "";
  const avatar = meta.avatar_url || meta.picture || null;
  const initial = (name as string).trim().charAt(0).toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2.5 pl-1.5 pr-3 py-1 hover:bg-bone transition-colors"
      >
        {avatar ? (
          <img
            src={avatar}
            alt=""
            className="h-7 w-7 object-cover border border-hairline"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="h-7 w-7 bg-ink text-snow flex items-center justify-center text-xs font-medium">
            {initial}
          </div>
        )}
        <div className="hidden md:flex flex-col items-start leading-tight">
          <span className="text-xs font-medium text-ink truncate max-w-[140px]">{name}</span>
          <span className="text-[10px] text-slate truncate max-w-[140px]">{email}</span>
        </div>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-72 bg-snow border border-hairline
                     shadow-[0_24px_48px_-12px_rgba(10,10,10,0.18)] z-[1500] animate-fade-in"
        >
          {/* Header */}
          <div className="px-4 py-4 border-b border-hairline flex items-center gap-3">
            {avatar ? (
              <img src={avatar} alt="" className="h-10 w-10 object-cover border border-hairline" referrerPolicy="no-referrer" />
            ) : (
              <div className="h-10 w-10 bg-ink text-snow flex items-center justify-center text-sm">
                {initial}
              </div>
            )}
            <div className="min-w-0">
              <div className="text-sm font-medium text-ink truncate">{name}</div>
              <div className="text-xs text-slate truncate">{email}</div>
            </div>
          </div>

          {/* Actions */}
          <div className="py-1">
            <MenuItem
              icon={History}
              label="My searches"
              onClick={() => { setOpen(false); onHistoryClick(); }}
            />
            <MenuItem
              icon={UserIcon}
              label="Account"
              hint="Manage in Supabase"
              disabled
            />
          </div>

          <div className="border-t border-hairline py-1">
            <MenuItem
              icon={LogOut}
              label="Sign out"
              onClick={async () => { setOpen(false); await signOut(); }}
              destructive
            />
          </div>
        </div>
      )}
    </div>
  );
}

function MenuItem({
  icon: Icon,
  label,
  hint,
  onClick,
  destructive,
  disabled,
}: {
  icon: any;
  label: string;
  hint?: string;
  onClick?: () => void;
  destructive?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors
                  ${disabled ? "text-mist cursor-not-allowed" :
                    destructive ? "text-ink hover:bg-bone hover:text-crimson" :
                    "text-ink hover:bg-bone"}`}
    >
      <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
      <span className="flex-1 text-left">{label}</span>
      {hint && <span className="text-[10px] text-mist">{hint}</span>}
    </button>
  );
}
