/**
 * KYC Customer Friction Elimination Layer v1
 * Continuation, QR, upload inbox, momentum, post-upload guidance, telemetry.
 */
(function (global) {
  "use strict";

  const STORAGE_PREFIX = "kyc_upload_queue_";

  function clientKind() {
    const w = global.innerWidth || 1024;
    const ua = navigator.userAgent || "";
    if (w < 768 || /Mobi|Android|iPhone/i.test(ua)) return "mobile";
    return "desktop";
  }

  async function telemetry(eventType, payload) {
    payload = payload || {};
    payload.client = payload.client || clientKind();
    try {
      await fetch("/api/customer/continuation/event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: payload.token || "",
          event_type: eventType,
          step: payload.step || "",
          duration_ms: payload.duration_ms,
          metadata: payload.metadata || {},
        }),
      });
    } catch (_) {}
  }

  function qrSrcForUrl(url) {
    return "/api/customer/qr.svg?data=" + encodeURIComponent(url);
  }

  function setMomentum(opts, percent, message) {
    if (opts.bar) opts.bar.hidden = false;
    if (opts.fill) opts.fill.style.width = Math.min(100, percent) + "%";
    if (opts.headline && message) opts.headline.textContent = message;
    if (opts.subline && percent >= 50) {
      opts.subline.textContent = "You are making good progress — take your time.";
    }
  }

  function loadQueue(projectId) {
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + projectId);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function saveQueue(projectId, items) {
    try {
      localStorage.setItem(STORAGE_PREFIX + projectId, JSON.stringify(items));
    } catch (_) {}
  }

  async function resolveToken(token) {
    const r = await fetch("/api/customer/continuation/resolve?token=" + encodeURIComponent(token));
    return r.json();
  }

  async function fetchEvidenceProfile(projectId, token) {
    if (!projectId || !token) return null;
    const url =
      "/api/customer/evidence/profile?project_id=" +
      encodeURIComponent(projectId) +
      "&token=" +
      encodeURIComponent(token);
    try {
      const r = await fetch(url);
      return r.json();
    } catch (_) {
      return null;
    }
  }

  function renderEvidenceProfile(el, data, token) {
    if (!el || !data || !data.ok) return;
    let html =
      '<div class="kyc-evidence-intel">' +
      "<h3>" +
      escapeHtml(data.headline || "We started organizing your paperwork") +
      "</h3>";
    const id = data.identified || {};
    html += "<section><h4>What we found</h4><ul class=\"kyc-guidance-found\">";
    function line(label, items) {
      if (!items || !items.length) return;
      html +=
        "<li><strong>" +
        escapeHtml(label) +
        ":</strong> " +
        items
          .slice(0, 5)
          .map(function (v) {
            return escapeHtml(v);
          })
          .join(", ") +
        "</li>";
    }
    line("Company names we may have identified", id.company_names);
    line("Emails", id.emails);
    line("Domains", id.domains);
    line("Systems / tools", id.technologies);
    line("Vendors", id.vendors);
    line("Compliance references", id.compliance_references);
    if (data.document_types && data.document_types.length) {
      html +=
        "<li><strong>Document types recognized:</strong> " +
        data.document_types
          .slice(-5)
          .map(function (d) {
            return escapeHtml(d.type || "unknown") + " (" + escapeHtml(d.file || "") + ")";
          })
          .join("; ") +
        "</li>";
    }
    html += "</ul></section>";
    if (data.needs_confirmation && data.needs_confirmation.length) {
      html += "<section><h4>Please confirm</h4><ul class=\"kyc-confirm-list\">";
      data.needs_confirmation.slice(0, 5).forEach(function (c) {
        html +=
          "<li data-field=\"" +
          escapeHtml(c.field) +
          "\" data-value=\"" +
          escapeHtml(c.value) +
          "\"><span>" +
          escapeHtml(c.message || "Please confirm this detail.") +
          "</span> " +
          "<div class=\"kyc-help-actions\">" +
          '<button type="button" data-confirm="confirmed">Correct</button>' +
          '<button type="button" data-confirm="rejected">Not correct</button>' +
          '<button type="button" data-confirm="unsure">I\'m not sure</button>' +
          "</div></li>";
      });
      html += "</ul></section>";
    }
    if (data.missing_items && data.missing_items.length) {
      html += "<section><h4>What may still help</h4><ul class=\"kyc-guidance-missing\">";
      data.missing_items.forEach(function (m) {
        const key = m.example_item_id || m.gap_id || "";
        html +=
          "<li><strong>" +
          escapeHtml(m.label) +
          "</strong><br>" +
          escapeHtml(m.plain || "") +
          (m.why ? "<br><em>" + escapeHtml(m.why) + "</em>" : "") +
          '<div class="kyc-help-actions">' +
          (m.example_url
            ? '<a class="kyc-btn kyc-btn--secondary" href="' +
              escapeHtml(m.example_url) +
              '" target="_blank" rel="noopener">Show example</a>'
            : '<button type="button" data-example="' +
              escapeHtml(key) +
              '">Show example</button>') +
          '<button type="button" data-help="' +
          escapeHtml(key) +
          '">Help me get this</button>' +
          '<button type="button" data-skip="' +
          escapeHtml(m.gap_id || key) +
          '">Skip for now</button>' +
          "</div><div class=\"kyc-help-panel\" hidden data-panel=\"" +
          escapeHtml(key) +
          '"></div></li>';
      });
      html += "</ul></section>";
    }
    html += "</div>";
    el.innerHTML = html;
    el.querySelectorAll("button[data-confirm]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const li = btn.closest("li");
        if (!li) return;
        postConfirm(
          token,
          li.getAttribute("data-field"),
          li.getAttribute("data-value"),
          btn.getAttribute("data-confirm")
        );
      });
    });
    el.querySelectorAll("button[data-example]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showExample(btn.getAttribute("data-example"), el, token);
        telemetry("example_clicked_after_gap", { token: token, metadata: { item_id: btn.getAttribute("data-example") } });
      });
    });
    el.querySelectorAll("button[data-help]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showRetrieval(btn.getAttribute("data-help"), el, token);
        telemetry("missing_item_help_clicked", { token: token, metadata: { item_id: btn.getAttribute("data-help") } });
      });
    });
    el.querySelectorAll("button[data-skip]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        telemetry("skipped_missing_item", { token: token, metadata: { gap_id: btn.getAttribute("data-skip") } });
        btn.closest("li").style.opacity = "0.5";
      });
    });
  }

  async function postConfirm(token, field, value, action) {
    const state = window.__kycUploadState || {};
    if (!state.projectId) return;
    try {
      await fetch("/api/customer/evidence/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: state.projectId,
          token: token,
          field: field,
          value: value,
          action: action,
        }),
      });
      telemetry(
        action === "confirmed"
          ? "customer_confirmed_entity"
          : action === "rejected"
            ? "customer_rejected_entity"
            : "customer_unsure_entity",
        { token: token, metadata: { field: field } }
      );
    } catch (_) {}
  }

  function renderGuidance(el, data, token) {
    if (!el || !data || !data.ok) return;
    let html =
      '<div class="kyc-guidance">' +
      "<h3>" +
      escapeHtml(data.headline) +
      "</h3>" +
      "<p>" +
      escapeHtml(data.subline || "") +
      "</p>";
    if (data.classified && data.classified.length) {
      html += "<p><strong>We recognized:</strong> ";
      html += data.classified
        .slice(0, 5)
        .map(function (c) {
          return escapeHtml(c.label || c.name);
        })
        .join(", ");
      html += "</p>";
    }
    if (data.missing_items && data.missing_items.length) {
      html += '<p class="org-metric-foot">Only a few remaining things may help:</p><ul class="kyc-guidance-missing">';
      data.missing_items.forEach(function (m) {
        html +=
          "<li><strong>" +
          escapeHtml(m.title) +
          "</strong><br>" +
          escapeHtml(m.plain) +
          '<div class="kyc-help-actions">' +
          '<button type="button" data-example="' +
          escapeHtml(m.id) +
          '">Show example</button>' +
          '<button type="button" data-what="' +
          escapeHtml(m.id) +
          '">What is this?</button>' +
          '<button type="button" data-help="' +
          escapeHtml(m.id) +
          '">Help me get this</button>' +
          "</div><div class=\"kyc-help-panel\" hidden data-panel=\"" +
          escapeHtml(m.id) +
          '"></div></li>';
      });
      html += "</ul></div>";
    } else {
      html += "</div>";
    }
    el.innerHTML = html;
    el.querySelectorAll("button[data-example]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showExample(btn.getAttribute("data-example"), el, token);
      });
    });
    el.querySelectorAll("button[data-what]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showExample(btn.getAttribute("data-what"), el, token);
      });
    });
    el.querySelectorAll("button[data-help]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showRetrieval(btn.getAttribute("data-help"), el, token);
      });
    });
    if (token) telemetry("guidance_viewed", { token: token, step: "upload" });
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  async function showExample(itemId, root, token) {
    const r = await fetch("/api/customer/evidence/example/" + encodeURIComponent(itemId));
    const j = await r.json();
    const panel = root.querySelector('[data-panel="' + itemId + '"]');
    if (!panel || !j.ok) return;
    panel.hidden = false;
    panel.innerHTML =
      "<strong>Example:</strong> " +
      escapeHtml(j.example_note || j.plain) +
      " <em>(" +
      escapeHtml(j.example_type || "document") +
      ")</em>";
    telemetry("example_viewed", { token: token, metadata: { item_id: itemId } });
  }

  async function showRetrieval(itemId, root, token) {
    const r = await fetch("/api/customer/evidence/retrieval/" + encodeURIComponent(itemId));
    const j = await r.json();
    const panel = root.querySelector('[data-panel="' + itemId + '"]');
    if (!panel || !j.ok) return;
    panel.hidden = false;
    const ret = j.retrieval || {};
    let html = "<strong>Where to find it:</strong><ul>";
    (ret.where || []).forEach(function (w) {
      html += "<li>" + escapeHtml(w) + "</li>";
    });
    html += "</ul><strong>Quick steps:</strong><ol>";
    (ret.steps || []).forEach(function (s) {
      html += "<li>" + escapeHtml(s) + "</li>";
    });
    html += "</ol>";
    if (ret.vendors && ret.vendors.length) {
      html += "<p><em>Often exported from: " + escapeHtml(ret.vendors.join(", ")) + "</em></p>";
    }
    panel.innerHTML = html;
    telemetry("retrieval_help_viewed", { token: token, metadata: { item_id: itemId } });
  }

  async function fetchGuidance(projectId, token) {
    let url = "/api/customer/upload/guidance?project_id=" + encodeURIComponent(projectId);
    if (token) url += "&token=" + encodeURIComponent(token);
    const r = await fetch(url);
    return r.json();
  }

  async function uploadOne(file, projectId, email, token, li) {
    const fd = new FormData();
    fd.append("file", file);
    let url =
      "/api/evidence/register?project_id=" +
      encodeURIComponent(projectId) +
      "&media_type=document&owner=" +
      encodeURIComponent(email || "customer");
    if (token) url += "&token=" + encodeURIComponent(token);
    const started = Date.now();
    telemetry("upload_started", { token: token, step: "upload", metadata: { filename: file.name } });
    const r = await fetch(url, { method: "POST", body: fd });
    const j = await r.json();
    const ms = Date.now() - started;
    if (j.ok) {
      if (li) {
        li.className = "kyc-upload-done";
        li.textContent = "✓ " + file.name;
      }
      telemetry("upload_completed", {
        token: token,
        step: "upload",
        duration_ms: ms,
        metadata: { filename: file.name },
      });
      return true;
    }
    if (li) {
      li.className = "kyc-upload-err";
      li.textContent = "✗ " + file.name + " — try again";
    }
    telemetry("upload_abandoned", { token: token, step: "upload", metadata: { filename: file.name } });
    return false;
  }

  function initUploadPage(cfg) {
    const state = {
      projectId: cfg.projectId || "",
      token: cfg.token || "",
      email: cfg.emailInput ? cfg.emailInput.value : "",
    };
    window.__kycUploadState = state;

    function setProjectId(pid, email) {
      state.projectId = pid;
      if (email && cfg.emailInput) cfg.emailInput.value = email;
      state.email = email || state.email;
      if (cfg.projectIdInput) cfg.projectIdInput.value = pid;
      refreshQr();
      resumeQueue();
    }

    function setToken(t) {
      state.token = t;
      refreshQr();
    }

    function refreshQr() {
      if (!cfg.qrImg || !state.projectId) return;
      let target =
        global.location.origin +
        "/upload?project_id=" +
        encodeURIComponent(state.projectId);
      if (state.token) target += "&token=" + encodeURIComponent(state.token);
      cfg.qrImg.src = qrSrcForUrl(target);
      cfg.qrImg.alt = "QR code to continue upload on your phone";
    }

    async function resumeQueue() {
      if (!state.projectId) return;
      const queue = loadQueue(state.projectId);
      if (!queue.length) return;
      for (const item of queue) {
        if (!item.pending) continue;
        const li = document.createElement("li");
        li.textContent = "Resuming: " + item.name + "…";
        cfg.progressList && cfg.progressList.appendChild(li);
        const blob = await fetch(item.dataUrl).then((r) => r.blob());
        const file = new File([blob], item.name, { type: item.type || "application/octet-stream" });
        const ok = await uploadOne(file, state.projectId, state.email, state.token, li);
        item.pending = !ok;
      }
      saveQueue(
        state.projectId,
        queue.filter(function (q) {
          return q.pending;
        })
      );
      if (state.projectId) {
        const g = await fetchGuidance(state.projectId, state.token);
        renderGuidance(cfg.guidanceEl, g, state.token);
        if (g.progress_percent) setMomentum(cfg, g.progress_percent, g.headline);
      }
    }

    async function uploadFiles(fileList) {
      if (!state.projectId) {
        if (cfg.statusEl) {
          cfg.statusEl.className = "kyc-status kyc-status--error";
          cfg.statusEl.textContent = "Open your secure link first.";
        }
        return;
      }
      const files = Array.from(fileList || []);
      if (!files.length) return;
      if (cfg.statusEl) {
        cfg.statusEl.className = "kyc-status";
        cfg.statusEl.textContent = "Uploading…";
      }
      let okCount = 0;
      for (const file of files) {
        const li = document.createElement("li");
        li.textContent = "↑ " + file.name + "…";
        cfg.progressList && cfg.progressList.appendChild(li);
        const ok = await uploadOne(file, state.projectId, state.email, state.token, li);
        if (ok) okCount++;
      }
      if (cfg.statusEl) {
        cfg.statusEl.className = "kyc-status kyc-status--ok";
        cfg.statusEl.textContent =
          okCount === files.length
            ? "We received your files. We are organizing them now."
            : "Some files need another try — you can re-upload.";
      }
      const g = await fetchGuidance(state.projectId, state.token);
      renderGuidance(cfg.guidanceEl, g, state.token);
      if (cfg.intelligenceEl && state.token) {
        const prof = await fetchEvidenceProfile(state.projectId, state.token);
        renderEvidenceProfile(cfg.intelligenceEl, prof, state.token);
      }
      if (g.progress_percent)
        setMomentum(
          {
            headline: cfg.momentumHeadline,
            subline: cfg.momentumSubline,
            bar: cfg.momentumBar,
            fill: cfg.momentumFill,
          },
          g.progress_percent,
          g.headline
        );
    }

    if (cfg.dropZone) {
      cfg.dropZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        cfg.dropZone.classList.add("kyc-drag-over");
      });
      cfg.dropZone.addEventListener("dragleave", function () {
        cfg.dropZone.classList.remove("kyc-drag-over");
      });
      cfg.dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        cfg.dropZone.classList.remove("kyc-drag-over");
        if (e.dataTransfer && e.dataTransfer.files) uploadFiles(e.dataTransfer.files);
      });
    }
    if (cfg.fileInput) {
      cfg.fileInput.addEventListener("change", function () {
        if (cfg.fileInput.files && cfg.fileInput.files.length) uploadFiles(cfg.fileInput.files);
      });
    }

    global.addEventListener("beforeunload", function () {
      if (!state.projectId) return;
    });

    return { setProjectId, setToken, uploadFiles, refreshQr, resumeQueue };
  }

  async function initIntakePage(token, momentumOpts) {
    if (!token) return;
    let j = { ok: false };
    try {
      const ir = await fetch("/api/intake/resolve?token=" + encodeURIComponent(token)).then(function (r) {
        return r.json();
      });
      if (ir.ok) {
        j = {
          ok: true,
          progress_percent: ir.progress_percent || 25,
          momentum_message: ir.momentum_message || "Good progress — complete intake when ready.",
          continuation_url: ir.continuation_url,
          upload_url: ir.upload_url,
        };
      }
    } catch (_) {}
    if (j.ok && momentumOpts) {
      setMomentum(
        {
          headline: momentumOpts.headline,
          subline: momentumOpts.subline,
          bar: momentumOpts.bar,
          fill: momentumOpts.fill,
        },
        j.progress_percent || 25,
        j.momentum_message || "Good progress — you are almost there."
      );
    }
    const qr = document.getElementById("intakeQr");
    if (qr) {
      const target =
        j.upload_url ||
        j.continuation_url ||
        global.location.origin + "/upload?token=" + encodeURIComponent(token);
      qr.src = qrSrcForUrl(target);
    }
    telemetry("continuation_opened", { token: token, step: "intake" });
  }

  async function initContinuePage(token) {
    const root = document.getElementById("continueRoot");
    if (!token) {
      if (root) root.innerHTML = "<p class=\"kyc-status kyc-status--error\">Missing link. Check your email for the latest message.</p>";
      return;
    }
    const j = await resolveToken(token);
    if (!j.ok) {
      if (root)
        root.innerHTML =
          '<p class="kyc-status kyc-status--error">' + escapeHtml(j.detail || "Link invalid or expired.") + "</p>";
      return;
    }
    const pct = j.progress_percent || 30;
    setMomentum(
      {
        bar: document.getElementById("momentumBar"),
        fill: document.getElementById("momentumFill"),
        headline: document.getElementById("continueHeadline"),
        subline: document.getElementById("continueSubline"),
      },
      pct,
      j.momentum_message
    );
    if (root) {
      let html =
        '<div class="kyc-card kyc-card--flat">' +
        "<p class=\"kyc-reassurance\">You do not need perfect paperwork. Upload whatever you have — we will organize the rest.</p>";
      if (j.recognized && j.recognized.length) {
        html += "<p><strong>We already recognized:</strong> " + escapeHtml(j.recognized.join(", ")) + "</p>";
      }
      if (j.missing_items && j.missing_items.length) {
        html += "<p><strong>May still help (no rush):</strong> ";
        html += j.missing_items
          .slice(0, 3)
          .map(function (m) {
            return escapeHtml(m.title);
          })
          .join(", ");
        html += "</p>";
      }
      html += '<div class="kyc-continue-actions">';
      html +=
        '<a class="kyc-btn kyc-btn--primary kyc-upload-cta-primary" href="' +
        escapeHtml(j.upload_url) +
        '">Upload my paperwork</a>';
      if (!j.intake_complete) {
        html +=
          '<a class="kyc-btn kyc-btn--secondary" href="' +
          escapeHtml(j.intake_url) +
          '">Add quick details</a>';
      }
      html += "</div>";
      html +=
        '<div class="kyc-qr-block kyc-qr-block--prominent"><h3>Continue on your phone</h3>' +
        "<p>Scan or copy your link — no password.</p>" +
        '<img src="' +
        qrSrcForUrl(j.continuation_url) +
        '" alt="QR code" width="220" height="220">' +
        '<div class="kyc-copy-link-row"><button type="button" id="continueCopyLink">Copy my link</button></div></div></div>';
      root.innerHTML = html;
      const copyBtn = document.getElementById("continueCopyLink");
      if (copyBtn && j.continuation_url) {
        copyBtn.addEventListener("click", function () {
          navigator.clipboard.writeText(j.continuation_url).then(function () {
            copyBtn.textContent = "Copied!";
          });
        });
      }
    }
    const qr = document.getElementById("continueQr");
    if (qr && j.continuation_url) qr.src = qrSrcForUrl(j.continuation_url);
    telemetry("continuation_opened", { token: token, step: "continue" });
    global.addEventListener("beforeunload", function () {
      telemetry("step_abandoned", { token: token, step: "continue" });
    });
  }

  global.KYCFriction = {
    initUploadPage,
    initIntakePage,
    initContinuePage,
    telemetry,
    clientKind,
    renderEvidenceProfile,
    fetchEvidenceProfile,
    renderGuidance,
    qrSrcForUrl,
  };
})(typeof window !== "undefined" ? window : globalThis);
