// supabase/functions/verify-profile-pin/index.ts
import { serve } from "https://deno.land/std@0.177.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};


serve(async (req: Request) => {
  // Handle preflight OPTIONS request
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Try to read JSON body
  let payload: any = null;
  try {
    payload = await req.json();
  } catch {
    payload = null;
  }

 const profile = (payload?.profile ?? "").toString().toLowerCase();
const pin = (payload?.pin ?? "").toString();

const validPins: Record<string, string> = {
  john: "123456",
  patty: "222222",
  kid: "000000",
};


  // Basic validation
  if (!profile || !pin) {
    return new Response(
      JSON.stringify({
        ok: false,
        valid: false,
        error: "Missing profile or pin",
      }),
      {
        status: 400,
        headers: {
          "Content-Type": "application/json",
          ...corsHeaders,
        },
      },
    );
  }

  const expectedPin = validPins[profile];
  const isValid = expectedPin !== undefined && pin === expectedPin;

return new Response(
  JSON.stringify({
    ok: true,
    valid: isValid,
    profile,
  }),
  {
    status: isValid ? 200 : 401,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders,
    },
  },
);

});
