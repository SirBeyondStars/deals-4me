// signup.js
// Deals-4Me signup logic (moved out of signup.html for consistency)

function buildAddressLine() {
  const street  = document.getElementById("street").value.trim();
  const street2 = document.getElementById("street2").value.trim();
  const city    = document.getElementById("city").value.trim();
  const state   = document.getElementById("state").value.trim();
  const zip     = document.getElementById("zip").value.trim();

  if (!street && !street2 && !city && !state && !zip) return "";

  const parts = [];
  if (street) parts.push(street);
  if (street2) parts.push(street2);

  const cityStateZip = [city, state, zip].filter(Boolean).join(" ");
  if (cityStateZip) parts.push(cityStateZip);

  return parts.join(", ");
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("signup-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!window.supabaseClient) {
      alert("Supabase client not ready. Check supabaseClient.js.");
      return;
    }

    const ownerName       = document.getElementById("owner-name").value.trim();
    const email           = document.getElementById("email").value.trim();
    const email2          = document.getElementById("email2").value.trim();
    const password        = document.getElementById("password").value;
    const passwordConfirm = document.getElementById("password-confirm").value;

    const ownerPin  = document.getElementById("owner-pin").value.trim();
    const ownerPin2 = document.getElementById("owner-pin2").value.trim();

    const addressLine = buildAddressLine();

    if (!ownerName || !email || !email2 || !password || !ownerPin || !ownerPin2) {
      alert("Please fill in all required fields.");
      return;
    }

    if (email.toLowerCase() !== email2.toLowerCase()) {
      alert("Emails do not match.");
      return;
    }

    if (password !== passwordConfirm) {
      alert("Passwords do not match.");
      return;
    }

    if (!/^[0-9]{6}$/.test(ownerPin)) {
      alert("PIN must be exactly 6 digits.");
      return;
    }

    if (ownerPin !== ownerPin2) {
      alert("PINs do not match.");
      return;
    }

    const zip = document.getElementById("zip").value.trim();
        if (zip && !/^\d{5}(-\d{4})?$/.test(zip)) {
        alert("ZIP Code must be 5 digits or ZIP+4 (12345 or 12345-6789).");
        return;
    }


    console.log("[signup] creating auth user for", email);

    const { data: signupData, error: signupError } =
      await supabaseClient.auth.signUp({
        email,
        password,
        options: {
          data: {
            display_name: ownerName,
            address_line: addressLine || null
          }
        }
      });

    if (signupError) {
      console.error("[signup] auth error", signupError);
      alert("Sign-up failed: " + signupError.message);
      return;
    }

    const newUser = signupData.user;
    if (!newUser) {
      alert(
        "Account created, but no user object returned.\n" +
        "If email confirmation is enabled, please verify your email, then log in."
      );
      window.location.href = "login.html";
      return;
    }

    console.log("[signup] auth user created:", newUser.id);

    console.log("[signup] inserting owner profile row");
    const { error: profileError } = await supabaseClient
      .from("household_profiles")
      .insert([
        {
          owner_user_id: newUser.id,
          display_name: ownerName,
          pin: ownerPin,
          role: "owner",
          is_active: true,
          address_line: addressLine || null
        }
      ]);

    if (profileError) {
      console.error("[signup] profile insert error", profileError);
      alert(
        "Account created in auth, but failed to save profile:\n" +
        profileError.message
      );
      return;
    }

    alert(
      "Account created! You can now log in with your email and password." +
      (signupData.session ? "" : " If email confirmation is enabled, please verify your email first.")
    );

    window.location.href = "login.html";
  });
});
