/**
 * Upload-first flow: paperwork before name/email.
 * Phases: upload → minimum info → workspace ready.
 */
(function (global) {
  "use strict";

  const STORAGE_KEY = "kyc_pre_contact_session";

  function qrSrc(url) {
    return "/api/customer/qr.svg?data=" + encodeURIComponent(url);
  }

  function saveSession(sessionId, sessionToken) {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ session_id: sessionId, session_token: sessionToken })
      );
    } catch (_) {}
  }

  function loadSession() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function clearSession() {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (_) {}
  }

  async function apiStart() {
    const r = await fetch("/api/customer/session/start", { method: "POST" });
    const j = await r.json();
    if (!r.ok || !j.session_id) throw new Error(j.detail || "Could not start upload session");
    saveSession(j.session_id, j.session_token);
    return j;
  }

  async function ensureSession(existing) {
    if (existing && existing.session_id && existing.session_token) return existing;
    const j = await apiStart();
    return { session_id: j.session_id, session_token: j.session_token };
  }

  async function uploadFile(sessionId, sessionToken, file, onProgress) {
    const fd = new FormData();
    fd.append("session_id", sessionId);
    fd.append("session_token", sessionToken);
    fd.append("file", file, file.name);
    const r = await fetch("/api/customer/session/upload", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || "Upload failed");
    if (onProgress) onProgress(file.name, true);
    return j;
  }

  async function completeWorkspace(sessionId, sessionToken, name, email, note) {
    const fd = new FormData();
    fd.append("session_id", sessionId);
    fd.append("session_token", sessionToken);
    fd.append("name", name);
    fd.append("email", email);
    fd.append("note", note || "");
    const r = await fetch("/api/customer/session/complete", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || "Could not create workspace");
    clearSession();
    return j;
  }

  function telemetry(eventType, metadata) {
    if (global.KYCFriction && global.KYCFriction.telemetry) {
      global.KYCFriction.telemetry(eventType, metadata || {});
    }
  }

  function initUploadFirstFlow(cfg) {
    const phaseUpload = document.getElementById(cfg.phaseUploadId || "phaseUpload");
    const phaseMinInfo = document.getElementById(cfg.phaseMinInfoId || "phaseMinInfo");
    const phaseSuccess = document.getElementById(cfg.phaseSuccessId || "phaseSuccess");
    const fileInput = document.getElementById(cfg.fileInputId || "fileInput");
    const cameraInput = document.getElementById(cfg.cameraInputId || "cameraInput");
    const dropZone = document.getElementById(cfg.dropZoneId || "dropZone");
    const progressList = document.getElementById(cfg.progressListId || "progressList");
    const statusEl = document.getElementById(cfg.statusId || "flowStatus");
    const minInfoForm = document.getElementById(cfg.minInfoFormId || "minInfoForm");
    const successEl = document.getElementById(cfg.successPanelId || "successPanel");
    const askMode = !!cfg.askMode;

    let session = loadSession();
    let uploadCount = 0;
    let busy = false;

    function setStatus(msg, kind) {
      if (!statusEl) return;
      statusEl.textContent = msg || "";
      statusEl.className = "kyc-status" + (kind ? " kyc-status--" + kind : "");
    }

    function showPhase(name) {
      if (phaseUpload) phaseUpload.hidden = name !== "upload";
      if (phaseMinInfo) phaseMinInfo.hidden = name !== "mininfo";
      if (phaseSuccess) phaseSuccess.hidden = name !== "success";
      if (name === "mininfo") telemetry("min_info_requested", {});
    }

    function appendProgress(filename, ok) {
      if (!progressList) return;
      const li = document.createElement("li");
      li.textContent = (ok ? "✓ " : "✗ ") + filename;
      progressList.appendChild(li);
    }

    async function handleFiles(fileList) {
      if (!fileList || !fileList.length || busy) return;
      busy = true;
      setStatus("Uploading…", "");
      try {
        session = await ensureSession(session);
        for (let i = 0; i < fileList.length; i++) {
          const file = fileList[i];
          await uploadFile(session.session_id, session.session_token, file, appendProgress);
          uploadCount += 1;
        }
        setStatus(
          uploadCount === 1
            ? "Received 1 file. Add more or continue below."
            : "Received " + uploadCount + " files. Add more or continue below.",
          "ok"
        );
        if (phaseMinInfo && uploadCount > 0) {
          phaseMinInfo.hidden = false;
          const anchor = phaseMinInfo.querySelector(".kyc-mininfo-anchor");
          if (anchor) anchor.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      } catch (e) {
        setStatus(e.message || "Upload failed", "error");
      } finally {
        busy = false;
      }
    }

    if (dropZone) {
      dropZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        dropZone.classList.add("kyc-drop-active");
      });
      dropZone.addEventListener("dragleave", function () {
        dropZone.classList.remove("kyc-drop-active");
      });
      dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropZone.classList.remove("kyc-drop-active");
        handleFiles(e.dataTransfer.files);
      });
    }
    if (fileInput) {
      fileInput.addEventListener("change", function () {
        handleFiles(fileInput.files);
        fileInput.value = "";
      });
    }
    if (cameraInput) {
      cameraInput.addEventListener("change", function () {
        handleFiles(cameraInput.files);
        cameraInput.value = "";
      });
    }

    if (minInfoForm) {
      minInfoForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        if (!session || !session.session_id) {
          setStatus("Upload at least one file first.", "error");
          return;
        }
        if (uploadCount < 1) {
          setStatus("Upload at least one file first.", "error");
          return;
        }
        const name = (document.getElementById("minName") || {}).value || "";
        const email = (document.getElementById("minEmail") || {}).value || "";
        const note = (document.getElementById("minNote") || {}).value || "";
        setStatus("Creating your secure workspace…", "");
        try {
          const result = await completeWorkspace(
            session.session_id,
            session.session_token,
            name,
            email,
            note
          );
          showPhase("success");
          renderSuccess(successEl || phaseSuccess, result);
          setStatus("", "");
        } catch (err) {
          setStatus(err.message || "Something went wrong", "error");
        }
      });
    }

    function renderSuccess(el, result) {
      if (!el) return;
      const cont = result.continuation_url || "";
      const upload = result.upload_url || "";
      const qr = result.qr_url || qrSrc(cont);
      el.innerHTML =
        '<section class="kyc-hero kyc-hero--success">' +
        "<h2>Your secure workspace is ready.</h2>" +
        "<p>You can come back anytime using this secure link. We are organizing your paperwork in the background.</p>" +
        '<div class="kyc-upload-cta-row">' +
        '<a class="kyc-btn kyc-btn--primary" href="' +
        (cont || upload) +
        '">Continue onboarding</a>' +
        '<a class="kyc-btn kyc-btn--secondary" href="' +
        upload +
        '">Upload more paperwork</a>' +
        "</div>" +
        '<div class="kyc-qr-block kyc-qr-block--prominent">' +
        "<h3>Continue on your phone</h3>" +
        "<p>Scan or copy — no password needed.</p>" +
        '<img src="' +
        qr +
        '" alt="QR code to continue on your phone" width="220" height="220">' +
        '<div class="kyc-copy-link-row">' +
        '<button type="button" class="kyc-btn kyc-btn--secondary" id="copyMagicLink">Copy magic link</button>' +
        "</div></div></section>";
      const copyBtn = document.getElementById("copyMagicLink");
      if (copyBtn && cont) {
        copyBtn.addEventListener("click", function () {
          navigator.clipboard.writeText(cont).then(function () {
            copyBtn.textContent = "Link copied!";
            telemetry("magic_link_copied", { project_id: result.project_id });
          });
        });
      }
      telemetry("qr_shown", { project_id: result.project_id });
      telemetry("workspace_created", { project_id: result.project_id });
    }

    showPhase("upload");
    return { handleFiles, showPhase };
  }

  global.KYCSessionFlow = {
    initUploadFirstFlow,
    loadSession,
    clearSession,
    qrSrc,
  };
})(window);
