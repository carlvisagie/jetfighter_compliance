/**
 * Cockpit stabilization — safe-mode boot, 2s timeouts, circuit breaker (5 min).
 */
(function (global) {
  'use strict';

  var OPERATOR_TIMEOUT_MS = 15000;  // 15 seconds - acquisition/reddit queries can be slow
  var CIRCUIT_COOLDOWN_MS = 5 * 60 * 1000;
  var HEAVY_PREFIXES = [
    '/api/operator/organism-observability',
    '/api/operator/acquisition-intelligence',
    '/api/operator/reddit-acquisition',
    '/api/operator/knowledge-cockpit/overlay',
    '/api/operator/knowledge-cockpit/telemetry',
    '/api/memory/self-heal',
    '/api/operator/compliance-intelligence',
  ];

  var circuits = Object.create(null);
  var bootStatus = null;

  function isHeavyUrl(url) {
    var path = String(url || '').split('?')[0];
    return HEAVY_PREFIXES.some(function (p) {
      return path.indexOf(p) === 0;
    });
  }

  function circuitOpen(url) {
    var key = String(url || '').split('?')[0];
    var until = circuits[key];
    return until && Date.now() < until;
  }

  function tripCircuit(url) {
    var key = String(url || '').split('?')[0];
    circuits[key] = Date.now() + CIRCUIT_COOLDOWN_MS;
  }

  function pausedPayload() {
    return {
      ok: false,
      safe_mode: true,
      paused: true,
      message: 'Module paused during stabilization',
    };
  }

  async function fetchBootStatus() {
    var ctrl = new AbortController();
    var timer = setTimeout(function () {
      ctrl.abort();
    }, OPERATOR_TIMEOUT_MS);
    try {
      var r = await fetch('/healthz', { credentials: 'same-origin', signal: ctrl.signal });
      if (r.ok) return await r.json();
    } catch (e) {
      /* fall through */
    } finally {
      clearTimeout(timer);
    }
    try {
      var r2 = await fetch('/api/ops/boot-status', {
        credentials: 'same-origin',
        signal: ctrl.signal,
      });
      if (r2.ok) return await r2.json();
    } catch (e2) {
      return { ok: true, safe_mode: true };
    }
    return { ok: true, safe_mode: true };
  }

  async function operatorFetch(url, opts) {
    if (global.COCKPIT_SAFE_MODE && isHeavyUrl(url)) {
      return pausedPayload();
    }
    if (circuitOpen(url)) {
      return Object.assign({ circuit_open: true }, pausedPayload());
    }
    var ctrl = new AbortController();
    var timer = setTimeout(function () {
      ctrl.abort();
    }, OPERATOR_TIMEOUT_MS);
    var merged = Object.assign({ credentials: 'same-origin', signal: ctrl.signal }, opts || {});
    try {
      var r = await fetch(url, merged);
      var j = {};
      try {
        j = await r.json();
      } catch (parseErr) {
        j = {};
      }
      if (!r.ok || (j && j.ok === false && !j.paused)) {
        tripCircuit(url);
      }
      return j;
    } catch (err) {
      tripCircuit(url);
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  function renderSafeShell(root) {
    var health = document.getElementById('health');
    var pulse = document.getElementById('org-pulse-label');
    if (health) {
      health.textContent = 'Safe mode';
      health.className = 'kyc-pill kyc-pill--warn';
    }
    if (pulse) pulse.textContent = 'Intelligence modules paused — upload & intake active';
    var panels = [
      ['organism-observability-insights', 'Organism observability'],
      ['acquisition-intelligence-insights', 'Acquisition intelligence'],
      ['reddit-acquisition-insights', 'Reddit acquisition'],
      ['evidence-intelligence-insights', 'Evidence intelligence'],
      ['customer-friction-insights', 'Customer friction'],
    ];
    panels.forEach(function (pair) {
      var el = document.getElementById(pair[0]);
      if (el) {
        el.innerHTML =
          '<p class="org-metric-foot"><strong>' +
          pair[1] +
          ' paused</strong> — stabilization safe mode. Upload, intake, and project status remain available below.</p>';
      }
    });
    var guidance = root && root.querySelectorAll('[data-guidance]');
    if (guidance) {
      guidance.forEach(function (node) {
        if (node.getAttribute('data-guidance') !== 'priority') {
          node.innerHTML =
            '<p class="org-metric-foot">Guidance paused during stabilization.</p>';
        }
      });
    }
  }

  async function init() {
    bootStatus = await fetchBootStatus();
    global.COCKPIT_SAFE_MODE = !!(
      bootStatus.safe_mode ||
      bootStatus.safe_mode_effective
    );
    global.COCKPIT_BOOT_STATUS = bootStatus;
    return bootStatus;
  }

  global.CockpitStable = {
    init: init,
    operatorFetch: operatorFetch,
    isHeavyUrl: isHeavyUrl,
    pausedPayload: pausedPayload,
    renderSafeShell: renderSafeShell,
    shouldSkip: function (url) {
      return global.COCKPIT_SAFE_MODE && isHeavyUrl(url);
    },
  };
})(typeof window !== 'undefined' ? window : globalThis);
