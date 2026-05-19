(async () => {
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  document.getElementById("token").value = token;
  const f = document.getElementById("f");
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(f);
    const res = await fetch("/api/intake/submit", { method:"POST", body: fd });
    const j = await res.json();
    if (j.ok && j.upload_url) {
      if (confirm("Thanks! Continue to upload your documents now?")) {
        location.href = j.upload_url;
        return;
      }
    }
    alert(j.ok ? "Thanks! We received your info." : "Error: " + (j.error || res.status));
  });
})();
