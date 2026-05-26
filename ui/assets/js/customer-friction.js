/**
 * Customer Friction Elimination Layer v1 — continuation, QR, upload inbox, guidance.
 */
(function (global) {
  "use strict";

  function clientKind() {
    return /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) ? "mobile" : "desktop";
  }

  function encodeUrlParam(url) {
    return encodeURIComponent(url);
  }

  function qrSrcForUrl(url) {
    return "/api/customer/qr.svg?url=" + encodeUrlParam(url);
  }

  async function resolveContinuation(token) {
    const r = await fetch(
      "/api/customer/continuation/resolve?token=" +
        encodeURIComponent(token) +
        "&client=" +
        clientKind()
    );
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.detail || "Could not open link");
    }
    return r.json();
  }

  async function postContinuationEvent(token, event, step) {
    await fetch("/api/customer/continuation/event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, event, step, client: clientKind() }),
    });
  }

  function renderMomentum(elHead, elSub, elBar, elFill, momentum, progress) {
    if (momentum && elHead) elHead.textContent = momentum.headline || "Good progress";
    if (momentum && elSub) elSub.textContent = momentum.subline || "";
    if (elBar && elFill && typeof progress === "number") {
      elBar.hidden = false;
      elFill.style.width = Math.min(100, progress) + "%";
    }
  }

  function initContinuePage() {
    const params = new URLSearchParams(location.search);
    const token = params.get("token") || "";
    const status = document.getElementById("status");
    const btn = document.getElementById("continueBtn");
    const qrBlock = document.getElementById("qrBlock");
    const qrImg = document.getElementById("qrImg");
    const headline = document.getElementById("headline");
    const subline = document.getElementById("subline");
    const momentumBar = document.getElementById("momentumBar");
    const momentumFill = document.getElementById("momentumFill");

    if (!token) {
      status.textContent = "Missing link. Use the URL from your welcome email.";
      status.className = "kyc-status kyc-status--error";
      return;
    }

    resolveContinuation(token)
      .then((j) => {
        renderMomentum(headline, subline, momentumBar, momentumFill, j.momentum, j.resume?.progress_percent);
        status.textContent = "You're all set — tap continue when ready.";
        status.className = "kyc-status kyc-status--ok";
        btn.href = j.primary_url;
        btn.hidden = false;
        btn.textContent = j.next_step === "intake" ? "Continue intake" : "Continue uploading";
        if (qrImg && j.primary_url) {
          qrImg.src = qrSrcForUrl(j.primary_url);
          qrBlock.hidden = false;
        }
        btn.addEventListener("click", () => {
          postContinuationEvent(token, "continuation_completed", j.next_step);
        });
        window.addEventListener("beforeunload", () => {
          if (!sessionStorage.getItem("kyc_cont_done_" + token)) return;
        });
      })
      .catch((e) => {
        status.textContent = e.message || "This link is invalid or expired.";
        status.className = "kyc-status kyc-status--error";
      });
  }

  function initUploadPage(opts) {
    const pidInput = opts.projectIdInput;
    const emailInput = opts.emailInput;
    const status = opts.statusEl;
    const fileInput = opts.fileInput;
    const dropZone = opts.dropZone;
    const guidanceEl = opts.guidanceEl;
    const qrImg = opts.qrImg;
    const progressList = opts.progressList;

    let projectId = opts.projectId || "";
    let intakeToken = opts.token || "";
    let uploadSession = { completed: [], pending: [] };

    function saveSession() {
      if (!projectId) return;
      fetch("/api/customer/upload/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          token: intakeToken,
          session: uploadSession,
        }),
      });
    }

    function loadSession() {
      if (!projectId) return Promise.resolve();
      const q = new URLSearchParams({ project_id: projectId, token: intakeToken });
      return fetch("/api/customer/upload/session?" + q.toString())
        .then((r) => r.json())
        .then((j) => {
          if (j.session) uploadSession = j.session;
        })
        .catch(() => {});
    }

    function refreshGuidance() {
      if (!projectId || !guidanceEl) return;
      const q = new URLSearchParams({ project_id: projectId, token: intakeToken });
      fetch("/api/customer/upload/guidance?" + q.toString())
        .then((r) => r.json())
        .then((g) => {
          if (!g.ok && g.summary === undefined) return;
          const m = g.momentum || {};
          guidanceEl.innerHTML =
            '<div class="kyc-guidance-panel"><h3>' +
            (g.summary || "Good progress") +
            "</h3><p>" +
            (m.subline || "Upload whatever you already have.") +
            "</p>" +
            renderMissing(g.likely_missing || []) +
            "</div>";
          if (opts.momentumHeadline && m.headline) opts.momentumHeadline.textContent = m.headline;
          if (opts.momentumFill && g.progress_percent != null) {
            opts.momentumBar.hidden = false;
            opts.momentumFill.style.width = g.progress_percent + "%";
          }
        });
    }

    function renderMissing(items) {
      if (!items.length) return "<p>Only a few remaining things may help — add more anytime.</p>";
      return items
        .map(function (it) {
          return (
            '<div class="kyc-missing-item"><strong>' +
            it.title +
            "</strong><p>" +
            (it.why || "") +
            '</p><div class="kyc-help-actions">' +
            '<button type="button" class="kyc-btn secondary" data-example="' +
            it.id +
            '">Show example</button>' +
            '<button type="button" class="kyc-btn secondary" data-what="' +
            it.id +
            '">What is this?</button>' +
            '<button type="button" class="kyc-btn secondary" data-help="' +
            it.id +
            '">Help me get this</button>' +
            "</div><div class=\"kyc-help-detail\" id=\"help-" +
            it.id +
            '"></div></div>'
          );
        })
        .join("");
    }

    guidanceEl?.addEventListener("click", function (e) {
      const t = e.target;
      if (!(t instanceof HTMLElement)) return;
      const ex = t.getAttribute("data-example");
      const what = t.getAttribute("data-what");
      const help = t.getAttribute("data-help");
      const id = ex || what || help;
      if (!id) return;
      const box = document.getElementById("help-" + id);
      if (!box) return;
      if (ex || what) {
        fetch("/api/customer/evidence/example/" + id + "?project_id=" + encodeURIComponent(projectId))
          .then((r) => r.json())
          .then((j) => {
            box.innerHTML =
              "<p><strong>" +
              j.title +
              "</strong></p><p>" +
              (what ? j.what_is_this : j.summary) +
              "</p>";
          });
      }
      if (help) {
        fetch("/api/customer/evidence/help/" + id)
          .then((r) => r.json())
          .then((j) => {
            const steps = (j.quick_start || []).map((s, i) => "<li>" + s + "</li>").join("");
            box.innerHTML =
              "<p><strong>Where to find it:</strong> " +
              (j.where_usually || "") +
              "</p><ol class=\"kyc-retrieval-steps\">" +
              steps +
              "</ol>";
          });
      }
    });

    async function uploadFiles(files) {
      if (!projectId) {
        status.className = "kyc-status kyc-status--error";
        status.textContent = "Open your link from email first.";
        return;
      }
      const email = emailInput?.value?.trim() || "client";
      let ok = 0;
      status.textContent = "Uploading…";
      status.className = "kyc-status";
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const q = new URLSearchParams({
          project_id: projectId,
          media_type: "document",
          owner: email,
        });
        try {
          const res = await fetch("/api/evidence/register?" + q.toString(), { method: "POST", body: fd });
          const j = await res.json();
          if (res.ok && j.ok) {
            ok++;
            uploadSession.completed = uploadSession.completed || [];
            uploadSession.completed.push(file.name);
            if (progressList) {
              const li = document.createElement("li");
              li.textContent = "✓ " + file.name;
              progressList.appendChild(li);
            }
          }
        } catch (_) {}
      }
      saveSession();
      refreshGuidance();
      if (ok) {
        status.className = "kyc-status kyc-status--ok";
        status.textContent = "Uploaded " + ok + " file(s). Thank you — good progress.";
      } else {
        status.className = "kyc-status kyc-status--error";
        status.textContent = "Upload did not complete — try again.";
      }
    }

    if (dropZone && fileInput) {
      dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("is-dragover");
      });
      dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragover"));
      dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("is-dragover");
        if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files);
      });
      fileInput.addEventListener("change", () => {
        if (fileInput.files?.length) uploadFiles(fileInput.files);
      });
    }

  return {
      setProjectId: function (pid, email) {
        projectId = pid;
        if (pidInput) pidInput.value = pid;
        if (emailInput && email) emailInput.value = email;
        const pageUrl = location.href.split("?")[0] + "?project_id=" + encodeURIComponent(pid);
        if (intakeToken) {
          const u =
            location.origin +
            "/upload?project_id=" +
            encodeURIComponent(pid) +
            "&token=" +
            encodeURIComponent(intakeToken);
          if (qrImg) qrImg.src = qrSrcForUrl(u);
        }
        loadSession().then(refreshGuidance);
      },
      setToken: function (t) {
        intakeToken = t;
      },
      uploadFiles: uploadFiles,
      refreshGuidance: refreshGuidance,
    };
  }

  function initIntakePage(token, momentumEls) {
    if (!token) return;
    fetch("/api/intake/resolve?token=" + encodeURIComponent(token))
      .then((r) => r.json())
      .then((j) => {
        if (j.momentum && momentumEls) {
          renderMomentum(
            momentumEls.headline,
            momentumEls.subline,
            momentumEls.bar,
            momentumEls.fill,
            j.momentum,
            j.resume?.progress_percent
          );
        }
        if (j.intake_completed && momentumEls?.subline) {
          momentumEls.subline.textContent = "Intake already received — you can go straight to upload.";
        }
        const qr = document.getElementById("intakeQr");
        if (qr && j.continuation_url) {
          qr.src = qrSrcForUrl(j.continuation_url);
        }
      })
      .catch(() => {});
  }

  global.KYCFriction = {
    clientKind: clientKind,
    qrSrcForUrl: qrSrcForUrl,
    initContinuePage: initContinuePage,
    initUploadPage: initUploadPage,
    initIntakePage: initIntakePage,
    resolveContinuation: resolveContinuation,
  };
})(typeof window !== "undefined" ? window : globalThis);
