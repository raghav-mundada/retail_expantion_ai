import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL  as string;
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!SUPABASE_URL || !SUPABASE_ANON) {
  console.warn('[RetailIQ] VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY not set — auth disabled.');
}

export const supabase = createClient(SUPABASE_URL ?? '', SUPABASE_ANON ?? '', {
  auth: {
    persistSession:     true,
    autoRefreshToken:   true,
    detectSessionInUrl: true,  // picks up #access_token=... after Google redirect
    flowType:           'implicit', // required for Google OAuth hash-based redirect
  },
});

// ── Typed profile row ────────────────────────────────────────────────────────
export type Plan = 'free' | 'pro' | 'team';

export interface Profile {
  id:                               string;
  email:                            string | null;
  full_name:                        string | null;
  plan:                             Plan;
  analyses_used_this_month:         number;
  analyses_reset_at:                string | null;
  stripe_customer_id:               string | null;
  stripe_subscription_id:          string | null;
  subscription_start_date:         string | null;
  subscription_period_end:         string | null;
  subscription_cancel_at_period_end: boolean;
  created_at:                       string;
  updated_at:                       string;
}

export async function fetchProfile(userId: string): Promise<Profile | null> {
  const { data, error } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', userId)
    .single();

  if (error) {
    console.error('[supabase] fetchProfile error:', error.message);
    return null;
  }
  return data as Profile;
}
