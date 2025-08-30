import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";
console.log("[client] supabase-js loaded");

// ⬇️ PASTE YOUR REAL VALUES HERE
const supabaseUrl = "https://acoqndggldnrsjmonlge.supabase.co";
const supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjb3FuZGdnbGRucnNqbW9ubGdlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ3ODk5NjMsImV4cCI6MjA3MDM2NTk2M30.ka4l5Xnwwcl913awGdjyfXY_Y-DE3gyg6Nndg7gih4o";
// ⬆️ EXACTLY as shown in Settings → API

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
console.log("[client] client created", supabaseUrl.slice(0, 40) + "…");
