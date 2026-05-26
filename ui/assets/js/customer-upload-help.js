/**
 * Lightweight upload guidance — no chat, no alternate onboarding path.
 */
(function (global) {
  "use strict";

  function focusUpload(fileInputId) {
    const input = document.getElementById(fileInputId || "fileInput");
    const zone = document.getElementById("dropZone");
    if (zone) zone.scrollIntoView({ behavior: "smooth", block: "center" });
    if (input) input.click();
  }

  function bindHelpPanelUploadButtons(fileInputId) {
    document.querySelectorAll("[data-kyc-focus-upload]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        focusUpload(fileInputId);
      });
    });
  }

  function openHelpFromHash() {
    if (location.hash !== "#upload-help") return;
    const details = document.getElementById("upload-help");
    if (details && details.tagName === "DETAILS") {
      details.open = true;
      details.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function init(cfg) {
    bindHelpPanelUploadButtons((cfg && cfg.fileInputId) || "fileInput");
    openHelpFromHash();
    window.addEventListener("hashchange", openHelpFromHash);
  }

  global.KYCUploadHelp = { init: init, focusUpload: focusUpload };
})(window);
