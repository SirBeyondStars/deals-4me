// /api/stripe-webhook.js
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

export const config = { api: { bodyParser: false } }; // Vercel needs raw body

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: "2023-10-16" });
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);

export default async function handler(req, res) {
  const sig = req.headers["stripe-signature"];
  let event;

  // Read raw body for signature verification
  const buf = await buffer(req);
  try {
    event = stripe.webhooks.constructEvent(buf, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error("Webhook signature failed", err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  try {
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object;
        const subId = session.subscription;
        const custId = session.customer;

        // fetch subscription to read period end, status, price, etc.
        const sub = await stripe.subscriptions.retrieve(subId);

        const userId = session.metadata?.supabase_user_id;
        await supabase.from("profiles").update({
          stripe_customer_id: custId,
          stripe_subscription_id: subId,
          plan: sub.items.data[0]?.price?.id ?? null,
          current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
          is_active: sub.status === "active" || sub.status === "trialing"
        }).eq("id", userId);
        break;
      }

      case "customer.subscription.updated":
      case "customer.subscription.deleted": {
        const sub = event.data.object;
        // find Supabase user by stripe_customer_id or metadata
        const { data: users } = await supabase
          .from("profiles").select("id").eq("stripe_customer_id", sub.customer).limit(1);
        if (users && users[0]) {
          await supabase.from("profiles").update({
            stripe_subscription_id: sub.id,
            plan: sub.items.data[0]?.price?.id ?? null,
            current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
            is_active: sub.status === "active" || sub.status === "trialing"
          }).eq("id", users[0].id);
        }
        break;
      }
      // Add invoice.paid / invoice.payment_failed if you want
    }
    res.json({ received: true });
  } catch (e) {
    console.error(e);
    res.status(500).send("Webhook handler failed");
  }
}

// helpers
import { Readable } from "stream";
function buffer(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    Readable.from(req).on("data", (c) => chunks.push(c))
      .on("end", () => resolve(Buffer.concat(chunks)))
      .on("error", reject);
  });
}
