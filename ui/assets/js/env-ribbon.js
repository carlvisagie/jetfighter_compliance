/*
 * env-ribbon.js — operator UI environment ribbon.
 *
 * Self-installing: every operator page needs ONLY this one script tag —
 *
 *   <script src="/ui/assets/js/env-ribbon.js" defer></script>
 *
 * On load it injects the stylesheet link (if missing) and the #env-ribbon
 * DOM element at the top of <body> (if missing), then reads
 * GET /api/operator/environment-label and paints the ribbon.
 *
 * Contract: docs/PRODUCTION_IS_THE_ONLY_TRUTH.md §2.
 *
 * Two visible states:
 *   - production    → calm green strip, page untouched
 *   - non-production → giant red strip + page dimmed to 55%, so no count
 *                      is screenshottable without the warning visible too.
 *
 * If the endpoint fails or returns anything other than environment=production,
 * we render the alarm state. There is no benefit-of-the-doubt.
 */
(function () {
  "use strict";

  var STYLESHEET_HREF = "/ui/assets/styles/env-ribbon.css";

  function ensureStylesheet() {
    if (document.querySelector('link[data-env-ribbon]')) return;
    var links = document.querySelectorAll('link[rel="stylesheet"]');
    for (var i = 0; i < links.length; i++) {
      if ((links[i].getAttribute("href") || "").indexOf("env-ribbon.css") !== -1) {
        links[i].setAttribute("data-env-ribbon", "1");
        return;
      }
    }
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = STYLESHEET_HREF;
    link.setAttribute("data-env-ribbon", "1");
    document.head.appendChild(link);
  }

  function ensureRibbonElement() {
    if (document.getElementById("env-ribbon")) return;
    var ribbon = document.createElement("div");
    ribbon.id = "env-ribbon";
    ribbon.className = "env-ribbon env-ribbon--unknown";
    ribbon.setAttribute("role", "status");
    ribbon.setAttribute("aria-live", "polite");
    var label = document.createElement("span");
    label.className = "env-ribbon-label";
    label.textContent = "...";
    var meta = document.createElement("span");
    meta.className = "env-ribbon-meta";
    ribbon.appendChild(label);
    ribbon.appendChild(meta);
    if (document.body.firstChild) {
      document.body.insertBefore(ribbon, document.body.firstChild);
    } else {
      document.body.appendChild(ribbon);
    }
  }

  function install() {
    ensureStylesheet();
    if (document.body) ensureRibbonElement();
  }

  function $(id) { return document.getElementById(id); }

  function paint(state, label, headline, env) {
    var ribbon = $("env-ribbon");
    if (!ribbon) return;

    ribbon.classList.remove("env-ribbon--prod", "env-ribbon--noprod", "env-ribbon--unknown");
    document.body.classList.remove("env-production", "env-non-production", "env-unknown");

    var cls, bodyCls;
    if (state === "production") {
      cls = "env-ribbon--prod";
      bodyCls = "env-production";
    } else if (state === "non-production") {
      cls = "env-ribbon--noprod";
      bodyCls = "env-non-production";
    } else {
      cls = "env-ribbon--unknown";
      bodyCls = "env-unknown";
    }
    ribbon.classList.add(cls);
    document.body.classList.add(bodyCls);

    var labelEl = ribbon.querySelector(".env-ribbon-label");
    var metaEl  = ribbon.querySelector(".env-ribbon-meta");
    if (labelEl) labelEl.textContent = headline || label || state;
    if (metaEl) {
      var bits = [];
      if (env && env.data_root) bits.push("data_root=" + env.data_root);
      if (env && env.host)      bits.push("host=" + env.host);
      if (env && env.git_commit && env.git_commit !== "unknown") bits.push("commit=" + env.git_commit.slice(0, 8));
      if (env && env.server_time_utc) bits.push("t=" + env.server_time_utc);
      metaEl.textContent = bits.join("  ·  ");
    }
  }

  function loadRibbon() {
    var url = "/api/operator/environment-label";
    var ctrl = (typeof AbortController === "function") ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, 8000);

    fetch(url, {
      credentials: "include",
      cache: "no-store",
      signal: ctrl ? ctrl.signal : undefined,
      headers: { "Accept": "application/json" }
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        clearTimeout(timer);
        var env = (data && data._env) || {};
        var environment = env.environment || (data && data.label) || "unknown";
        var state = (environment === "production") ? "production"
                  : (environment === "non-production") ? "non-production"
                  : "unknown";
        var headline = (data && data.headline)
          || (state === "production"
                ? "PRODUCTION — live customer data"
                : "NON-PRODUCTION — DO NOT TRUST ANY COUNT ON THIS PAGE");
        paint(state, data && data.label, headline, env);
      })
      .catch(function (err) {
        clearTimeout(timer);
        paint("unknown", "UNKNOWN",
          "ENVIRONMENT UNKNOWN — DO NOT TRUST ANY COUNT (ribbon endpoint failed)",
          { server_time_utc: new Date().toISOString() });
      });
  }

  function boot() {
    install();
    loadRibbon();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  // Re-check every 5 minutes so a deploy that flipped env is noticed.
  setInterval(loadRibbon, 5 * 60 * 1000);
})();
