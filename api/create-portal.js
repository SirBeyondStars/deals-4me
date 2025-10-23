// /api/create-portal.js
import Stripe from "stripe";
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: "2023-10-16" });

export default async function handler(req, res) {
  const { customerId } = req.body; // you can look this up by supabase user
  const session = await stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: "https://deals-4me.com/site/auth/account_settings.html"
  });
  res.status(200).json({ url: session.url });
}
