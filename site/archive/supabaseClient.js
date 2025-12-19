// site/supabaseClient.js

// TODO: Replace with your real Supabase URL and anon key
const SUPABASE_URL = "https://acoqndggldnrsjmonlge.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_0spAlB_gWzHk84bklBFdgg_CkJNwUYF";

if (!window.supabase) {
  console.error("Supabase library not found. Make sure the CDN script is loaded in your HTML.");
}

const supabaseClient = window.supabase
  ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  : null;

window.supabaseClient = supabaseClient;
