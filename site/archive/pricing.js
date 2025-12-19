window.__PRICING_LOADED__ = true;
console.log("pricing.js loaded");

(() => {
  const logEl = document.getElementById("log");
  const log = (msg) => {
    console.log(msg);
    if (logEl) logEl.textContent += msg + "\n";
  };

  function attach(id, fn) {
    const el = document.getElementById(id);
    if (!el) return log(`Missing ${id}`);
    el.addEventListener("click", async () => {
      try {
        el.disabled = true;
        await fn();
      } catch (e) {
        log(`Error on ${id}: ${e.message || e}`);
        alert(`Error: ${e.message || e}`);
      } finally {
        el.disabled = false;
      }
    });
    log(`Attached -> ${id}`);
  }

  // Hook up buttons
  document.addEventListener("DOMContentLoaded", () => {
  attach("btn-gold",     () => Promise.resolve(log("Clicked: gold_monthly")));
  attach("btn-platinum", () => Promise.resolve(log("Clicked: platinum_monthly")));
  attach("btn-signin",   () => Promise.resolve(log("Clicked: sign in (would go to /login.html)")));
  attach("btn-signout",  () => Promise.resolve(log("Clicked: sign out")));
});
<script>
  console.log("probe: external loaded?", window.__PRICING_LOADED__);
  console.log("probe: btn exists?", !!document.getElementById('btn-gold'));
</script>


})();
