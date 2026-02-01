(() => {
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  const form = document.getElementById("contactForm");
  const topicEl = document.getElementById("topic");
  const nameEl = document.getElementById("name");
  const emailEl = document.getElementById("email");
  const msgEl = document.getElementById("message");
  const resetBtn = document.getElementById("resetBtn");

  const inboxMap = {
    support: "support@deals-4me.com",
    billing: "billing@deals-4me.com",
    feedback: "feedback@deals-4me.com",
    info: "info@deals-4me.com",
    privacy: "privacy@deals-4me.com",
  };

  function buildSubject(topic) {
    const label = {
      support: "Support Request",
      billing: "Billing Question",
      feedback: "Feedback",
      info: "General Question",
      privacy: "Privacy Request",
    }[topic] || "Message";

    return `Deals-4Me ${label}`;
  }

  function buildBody() {
    const name = (nameEl.value || "").trim();
    const email = (emailEl.value || "").trim();
    const msg = (msgEl.value || "").trim();

    const lines = [];
    lines.push("Hello Deals-4Me,");
    lines.push("");
    if (msg) lines.push(msg);
    lines.push("");
    if (name) lines.push(`Name: ${name}`);
    if (email) lines.push(`Email: ${email}`);
    lines.push("");
    lines.push("— Sent from the Deals-4Me Contact page");

    return lines.join("\n");
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      if (topicEl) topicEl.value = "support";
      if (nameEl) nameEl.value = "";
      if (emailEl) emailEl.value = "";
      if (msgEl) msgEl.value = "";
      msgEl?.focus();
    });
  }

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();

      const topic = topicEl?.value || "support";
      const to = inboxMap[topic] || inboxMap.support;

      const msg = (msgEl.value || "").trim();
      if (!msg) {
        msgEl.focus();
        return;
      }

      const subject = encodeURIComponent(buildSubject(topic));
      const body = encodeURIComponent(buildBody());

      // Open email client
      window.location.href = `mailto:${to}?subject=${subject}&body=${body}`;
    });
  }
})();
