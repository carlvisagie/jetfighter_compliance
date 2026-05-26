(async () => {
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  document.getElementById("token").value = token;
  let uploadUrl = "";

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

  if (token) {
    try {
      const ir = await fetch("/api/intake/resolve?token=" + encodeURIComponent(token)).then((r) => r.json());
      if (ir.ok && ir.upload_url) {
        uploadUrl = ir.upload_url;
        const skip = document.getElementById("skipToUpload");
        if (skip) skip.href = ir.upload_url;
      }
    } catch (_) {}
  }

  const f = document.getElementById("f");
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(f);
    const res = await fetch("/api/intake/submit", { method: "POST", body: fd });
    const j = await res.json();
    if (j.ok && j.upload_url) {
      location.href = j.upload_url;
      return;
    }
    alert(j.ok ? "Thanks — use your email link to upload when ready." : "Error: " + (j.detail || res.status));
  });
})();
