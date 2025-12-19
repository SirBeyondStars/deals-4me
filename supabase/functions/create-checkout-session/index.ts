// Minimal create-checkout-session (base plan only)
// FILE: supabase/functions/create-checkout-session/index.ts
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import Stripe from "https://esm.sh/stripe@16.7.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, { apiVersion: "2024-06-20" });
const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);


// TODO: replace these with your real Stripe price IDs later
const PRICE_IDS = {
  gold_monthly: "price_1SLZ3MEpOEtlvGXKVBDzhhIv",
  platinum_monthly: "PRICE_ID_PLATINUM_MONTHLY",
  gold_annual: "PRICE_ID_GOLD_ANNUAL",
  platinum_annual: "PRICE_ID_PLATINUM_ANNUAL",
};

type Body = { planKey: keyof typeof PRICE_IDS; };

Deno.serve(async (req) => {
  try {
    if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

    // Get Supabase user from Authorization: Bearer <sb-access-token>
    const authHeader = req.headers.get("Authorization") ?? "";
    const token = authHeader.replace("Bearer ", "");
    const { data: { user }, error: userErr } = await supabase.auth.getUser(token);
    if (userErr || !user) return new Response("Unauthorized", { status: 401 });

    const { planKey } = await req.json() as Body;
    const priceId = PRICE_IDS[planKey];
    if (!priceId) return new Response("Invalid plan", { status: 400 });

    // Ensure a Stripe customer exists for this user
    const { data: profile } = await supabase
      .from("user_profiles")
      .select("stripe_customer_id, email")
      .eq("user_id", user.id)
      .single();

    let customerId = profile?.stripe_customer_id;
    if (!customerId) {
      const customer = await stripe.customers.create({
        email: user.email ?? undefined,
        metadata: { supabaseUserId: user.id },
      });
      customerId = customer.id;
      await supabase.from("user_profiles").upsert({
        user_id: user.id,
        email: user.email,
        stripe_customer_id: customerId,
      }, { onConflict: "user_id" });
    }

    // Create a subscription Checkout Session
    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      customer: customerId,
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: "https://deals-4me.com/checkout/success.html?session_id={CHECKOUT_SESSION_ID}",
      cancel_url: "https://deals-4me.com/pricing.html",
      allow_promotion_codes: true,
      metadata: { supabaseUserId: user.id },
    });

    return new Response(JSON.stringify({ url: session.url }), {
      headers: { "content-type": "application/json" },
      status: 200,
    });
  } catch (e) {
    console.error(e);
    return new Response("Server error", { status: 500 });
  }
});
