console.log("[login] login.js loaded");

document.addEventListener("DOMContentLoaded", async () => {
  console.log("[login] DOMContentLoaded");

  // --- ELEMENTS ---
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const rememberCheckbox = document.getElementById("remember-device");
  const form = document.getElementById("login-form");

  // --- SAFETY CHECK ---
  if (!window.supabaseClient) {
    alert("Supabase client not ready. Check supabaseClient.js.");
    return;
  }
// If already authenticated, skip login screen and go to PIN screen
(async () => {
  try {
    const { data, error } = await window.supabaseClient.auth.getSession();
    if (error) console.warn("[login] getSession error:", error);

    const session = data?.session;
    if (session?.user) {
      console.log("[login] session found, redirecting to pin.html");
      window.location.replace("pin.html");
    }
  } catch (e) {
    console.warn("[login] session check failed:", e);
  }
})();

  // --- REMEMBERED DEVICE AUTO-SKIP LOGIC ---
  try {
    const remembered = localStorage.getItem("d4m_rememberDevice") === "true";

    if (remembered) {
      const { data: userData, error } = await supabaseClient.auth.getUser();

      if (!error && userData && userData.user) {
        console.log("[login] Remembered device. Skipping email/password → PIN");
        window.location.href = "pin.html";
        return;
      }
    }
  } catch (e) {
    console.warn("[login] Remember check failed:", e);
  }

  // --- FORM SUBMISSION ---
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    console.log("[login] submitting:", emailInput.value);

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    const { data, error } = await supabaseClient.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
  // show error
  messageEl.textContent = error.message;
  messageEl.classList.add('error');
} else {
  // ✅ go to the dashboard after login
  window.location.href = 'dashboard.html';
}


    // --- STORE REMEMBER DEVICE FLAG ---
    if (rememberCheckbox && rememberCheckbox.checked) {
      localStorage.setItem("d4m_rememberDevice", "true");
      console.log("[login] Device remembered");
    } else {
      localStorage.removeItem("d4m_rememberDevice");
    }

    console.log("[login] Login good → redirecting to PIN");
    window.location.href = "pin.html";
  });
});
