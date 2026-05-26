(async () => {
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  document.getElementById("token").value = token;

  const script = document.createElement("script");
  script.src = "/ui/assets/js/customer-friction.js";
  script.onload = () => {
    if (window.KYCFriction && token) {
      KYCFriction.initIntakePage(token, {
        headline: document.getElementById("intakeHeadline"),
        subline: document.getElementById("intakeSubline"),
        bar: document.getElementById("momentumBar"),
        fill: document.getElementById("momentumFill"),
      });
    }
  };
  document.head.appendChild(script);

  const f = document.getElementById("f");
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(f);
    const res = await fetch("/api/intake/submit", { method: "POST", body: fd });
    const j = await res.json();
    if (j.ok && j.upload_url) {
      if (confirm("Thanks! Good progress — continue to upload what you already have?")) {
        location.href = j.upload_url;
        return;
      }
    }
    alert(j.ok ? "Thanks! We received your info. Use your email link anytime to continue." : "Error: " + (j.detail || res.status));
  });
})();
