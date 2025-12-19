// site/supabaseClient.js

// TODO: Replace with your real Supabase URL and anon key
const SUPABASE_URL = "https://acoqndggldnrsjmonlge.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_0spAlB_gWzHk84bklBFdgg_CkJNwUYF";

if (!window.supabase || !window.supabase.createClient) {
  console.error(
    "[supabaseClient] Supabase JS library missing. " +
    "Make sure the CDN script is loaded before this file."
  );
} else {
  console.log("[supabaseClient] creating client");
  window.supabaseClient = window.supabase.createClient(
    SUPABASE_URL,
    SUPABASE_ANON_KEY
  );
}