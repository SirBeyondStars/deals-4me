import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: "2023-10-16" });

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();

  const { priceId, userId, userEmail } = req.body || {};
  if (!priceId || !userId || !userEmail) return res.status(400).json({ error: "Missing fields" });

  try {
    // Reuse customer by email
    const existing = await stripe.customers.list({ email: userEmail, limit: 1 });
    const customer = existing.data[0] || await stripe.customers.create({
      email: userEmail,
      metadata: { supabase_user_id: userId }
    });

    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      customer: customer.id,
      line_items: [{ price: priceId, quantity: 1 }],
      allow_promotion_codes: true,
      success_url: "https://deals-4me.com/site/auth/account_settings.html?success=1",
      cancel_url: "https://deals-4me.com/site/auth/pricing.html?canceled=1",
      metadata: { supabase_user_id: userId }
    });

    res.status(200).json({ url: session.url });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "Failed to create checkout session" });
  }
}
