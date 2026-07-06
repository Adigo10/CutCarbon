import { createClient } from '@supabase/supabase-js'

// The publishable key is safe for the browser (protected by Row-Level Security on
// Supabase). supabase-js persists the session in localStorage and auto-refreshes the
// access token, so the app no longer manages a 'cc_token' itself.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const supabase = createClient(supabaseUrl, supabaseKey)
