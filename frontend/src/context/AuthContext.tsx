/**
 * AuthContext — Supabase Auth + Subscription state.
 *
 * Provides:
 *   user          — Supabase Auth user (null = signed out)
 *   profile       — Supabase profiles row (plan, stripe fields, usage)
 *   plan          — shorthand: 'free' | 'pro' | 'team'
 *   isPro         — true when plan !== 'free'
 *   analysesLeft  — how many analyses remain this month (null = unlimited)
 *   signIn()      — email+password sign-in
 *   signUp()      — email+password sign-up
 *   signInWithGoogle() — OAuth sign-in
 *   signOut()
 *   refreshProfile()   — re-fetch profile from Supabase (after checkout)
 *   accessToken   — current JWT for authenticated backend requests
 */
import {
  createContext, useContext, useEffect, useState,
  useCallback, type ReactNode,
} from 'react';
import type { User, AuthError } from '@supabase/supabase-js';
import { supabase, fetchProfile, type Profile, type Plan } from '../lib/supabase';

// ── Plan limits ──────────────────────────────────────────────────────────────
const FREE_ANALYSES_PER_MONTH = 3;

// ── Context shape ────────────────────────────────────────────────────────────
interface AuthContextValue {
  user:             User | null;
  profile:          Profile | null;
  plan:             Plan;
  isPro:            boolean;
  analysesLeft:     number | null;    // null = unlimited (pro/team)
  loading:          boolean;
  accessToken:      string | null;
  signIn:           (email: string, password: string) => Promise<AuthError | null>;
  signUp:           (email: string, password: string, fullName?: string) => Promise<AuthError | null>;
  signInWithGoogle: () => Promise<AuthError | null>;
  signOut:          () => Promise<void>;
  refreshProfile:   () => Promise<void>;
  /** Call after a successful analysis run to decrement the counter */
  incrementUsage:   () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ─────────────────────────────────────────────────────────────────
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,         setUser]         = useState<User | null>(null);
  const [profile,      setProfile]      = useState<Profile | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [accessToken,  setAccessToken]  = useState<string | null>(null);

  const plan:      Plan    = profile?.plan ?? 'free';
  const isPro:     boolean = plan !== 'free';
  const analysesLeft: number | null = isPro
    ? null
    : Math.max(0, FREE_ANALYSES_PER_MONTH - (profile?.analyses_used_this_month ?? 0));

  // ── Strip #access_token hash once Supabase has captured the session ─────────
  // Must happen AFTER detectSessionInUrl processes it — otherwise we race and
  // erase the token before the SDK can parse it.
  const [sessionReady, setSessionReady] = useState(false);
  useEffect(() => {
    if (!sessionReady) return;
    if (typeof window === 'undefined') return;
    if (window.location.hash.includes('access_token=')) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  }, [sessionReady]);

  // ── Load initial session ───────────────────────────────────────────────────
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setAccessToken(session?.access_token ?? null);
      if (session?.user) {
        fetchProfile(session.user.id).then(setProfile);
      }
      setLoading(false);
      setSessionReady(true);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        setUser(session?.user ?? null);
        setAccessToken(session?.access_token ?? null);
        if (session?.user) {
          const p = await fetchProfile(session.user.id);
          setProfile(p);
        } else {
          setProfile(null);
        }
      }
    );
    return () => subscription.unsubscribe();
  }, []);

  // ── Actions ────────────────────────────────────────────────────────────────
  const signIn = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return error;
  }, []);

  const signUp = useCallback(async (email: string, password: string, fullName?: string) => {
    const { error } = await supabase.auth.signUp({
      email, password,
      options: { data: { full_name: fullName ?? '' } },
    });
    return error;
  }, []);

  const signInWithGoogle = useCallback(async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    });
    return error;
  }, []);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setProfile(null);
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!user) return;
    const p = await fetchProfile(user.id);
    setProfile(p);
  }, [user]);

  const incrementUsage = useCallback(async () => {
    if (!user || isPro) return;
    await supabase
      .from('profiles')
      .update({ analyses_used_this_month: (profile?.analyses_used_this_month ?? 0) + 1 })
      .eq('id', user.id);
    await refreshProfile();
  }, [user, isPro, profile, refreshProfile]);

  return (
    <AuthContext.Provider value={{
      user, profile, plan, isPro, analysesLeft, loading, accessToken,
      signIn, signUp, signInWithGoogle, signOut, refreshProfile, incrementUsage,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
