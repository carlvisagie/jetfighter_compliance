/**
 * Cognitive Operational Topology Engine (COTE) — SVG organism field.
 */
(function (global) {
  'use strict';

  var NODES = [
    { id: 'acquisition', label: 'Acquisition', angle: 0 },
    { id: 'knowledge', label: 'Knowledge', angle: 45 },
    { id: 'observability', label: 'Observability', angle: 90 },
    { id: 'upload_pipeline', label: 'Upload', angle: 135 },
    { id: 'evidence_processing', label: 'Evidence', angle: 180 },
    { id: 'learning', label: 'Learning', angle: 225 },
    { id: 'telemetry', label: 'Telemetry', angle: 270 },
    { id: 'alerts', label: 'Alerts', angle: 315 },
  ];

  var CX = 320;
  var CY = 210;
  var RING = 148;
  var NODE_R = 22;
  var state = { data: null, selected: null, timer: null };

  function ns(tag) {
    return document.createElementNS('http://www.w3.org/2000/svg', tag);
  }

  function polar(angleDeg, radius) {
    var a = ((angleDeg - 90) * Math.PI) / 180;
    return { x: CX + radius * Math.cos(a), y: CY + radius * Math.sin(a) };
  }

  function nodeVisualClass(m, nodeId) {
    if (!m) return 'cote-node--paused';
    if (nodeId === 'learning') {
      var ls = m.learning_status;
      if (ls === 'failed') return 'cote-node--failed';
      if (ls === 'degraded') return 'cote-node--unstable';
      if (ls === 'warming_up') return 'cote-node--warming-up';
      if (ls === 'healthy') return 'cote-node--healthy';
    }
    if (nodeId === 'upload_pipeline') {
      if (m.anomaly && m.health < 0.45) return 'cote-node--failed cote-node--upload-fail';
      if (m.pending_review > 0) return 'cote-node--pressure cote-node--upload-pending';
      if (m.flow_active || m.activity > 0.45) return 'cote-node--opportunity cote-node--upload-flow';
    }
    if (m.paused) return 'cote-node--paused';
    if (m.health < 0.35) return 'cote-node--failed';
    if (m.anomaly || m.health < 0.52) return 'cote-node--unstable';
    if (m.pressure > 0.62) return 'cote-node--pressure';
    if (m.confidence < 0.42) return 'cote-node--uncertain';
    if (m.activity > 0.72 && m.health > 0.68 && !m.paused) return 'cote-node--opportunity';
    if (m.health > 0.72 && m.pressure < 0.42) return 'cote-node--healthy';
    return 'cote-node--healthy';
  }

  function coreVisualClass(m, globalPressure) {
    if (!m) return 'cote-node--paused';
    if (m.health < 0.4) return 'cote-node--failed';
    if (m.anomaly || globalPressure > 0.55) return 'cote-node--unstable';
    if (globalPressure > 0.38) return 'cote-node--pressure';
    if (m.health > 0.8) return 'cote-node--healthy';
    return 'cote-node--healthy';
  }

  function ensureSvg() {
    var mount = document.getElementById('cote-topology-mount');
    if (!mount) return null;
    var svg = document.getElementById('cote-topology-svg');
    if (svg) return svg;
    mount.textContent = '';
    svg = ns('svg');
    svg.setAttribute('id', 'cote-topology-svg');
    svg.setAttribute('viewBox', '0 0 640 420');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Operational organism topology');

    var defs = ns('defs');
    var grad = ns('radialGradient');
    grad.setAttribute('id', 'cote-core-gradient');
    var s0 = ns('stop');
    s0.setAttribute('offset', '0%');
    s0.setAttribute('stop-color', 'rgba(90, 180, 255, 0.55)');
    var s1 = ns('stop');
    s1.setAttribute('offset', '100%');
    s1.setAttribute('stop-color', 'rgba(20, 40, 70, 0.15)');
    grad.appendChild(s0);
    grad.appendChild(s1);
    defs.appendChild(grad);

    var filt = ns('filter');
    filt.setAttribute('id', 'cote-soft-glow');
    filt.setAttribute('x', '-40%');
    filt.setAttribute('y', '-40%');
    filt.setAttribute('width', '180%');
    filt.setAttribute('height', '180%');
    var blur = ns('feGaussianBlur');
    blur.setAttribute('stdDeviation', '4');
    blur.setAttribute('result', 'blur');
    filt.appendChild(blur);
    var merge = ns('feMerge');
    var n1 = ns('feMergeNode');
    n1.setAttribute('in', 'blur');
    var n2 = ns('feMergeNode');
    n2.setAttribute('in', 'SourceGraphic');
    merge.appendChild(n1);
    merge.appendChild(n2);
    filt.appendChild(merge);
    defs.appendChild(filt);
    svg.appendChild(defs);

    var field = ns('g');
    field.setAttribute('class', 'cote-field');
    field.setAttribute('id', 'cote-field');
    svg.appendChild(field);
    mount.insertBefore(svg, mount.firstChild);
    return svg;
  }

  function renderTopology(data) {
    var svg = ensureSvg();
    if (!svg) return;
    var field = svg.querySelector('#cote-field');
    if (!field) return;
    while (field.firstChild) field.removeChild(field.firstChild);

    var subs = (data && data.subsystems) || {};
    var gp = data.global_pressure || 0;
    var mount = document.getElementById('cote-topology-mount');
    if (mount) {
      mount.classList.toggle('cote-mount--safe', !!(data && data.safe_mode));
    }

    var links = ns('g');
    links.setAttribute('class', 'cote-links');

    NODES.forEach(function (cfg) {
      var pos = polar(cfg.angle, RING);
      var line = ns('line');
      line.setAttribute('class', 'cote-link');
      line.setAttribute('x1', String(CX));
      line.setAttribute('y1', String(CY));
      line.setAttribute('x2', String(pos.x));
      line.setAttribute('y2', String(pos.y));
      var sm = subs[cfg.id] || {};
      line.style.strokeOpacity = String(0.15 + (sm.activity || 0) * 0.45);
      links.appendChild(line);
    });
    field.appendChild(links);

    var coreG = ns('g');
    coreG.setAttribute('class', 'cote-node cote-core ' + coreVisualClass(subs.system_health, gp));
    coreG.setAttribute('data-node', 'system_health');
    var corePulse = ns('circle');
    corePulse.setAttribute('class', 'cote-node-pulse');
    corePulse.setAttribute('cx', String(CX));
    corePulse.setAttribute('cy', String(CY));
    corePulse.setAttribute('r', '38');
    var coreBody = ns('circle');
    coreBody.setAttribute('class', 'cote-core-glow');
    coreBody.setAttribute('cx', String(CX));
    coreBody.setAttribute('cy', String(CY));
    coreBody.setAttribute('r', '32');
    var coreRing = ns('circle');
    coreRing.setAttribute('class', 'cote-core-ring');
    coreRing.setAttribute('cx', String(CX));
    coreRing.setAttribute('cy', String(CY));
    coreRing.setAttribute('r', '40');
    var coreHit = ns('circle');
    coreHit.setAttribute('class', 'cote-node-hit');
    coreHit.setAttribute('cx', String(CX));
    coreHit.setAttribute('cy', String(CY));
    coreHit.setAttribute('r', '42');
    var coreLabel = ns('text');
    coreLabel.setAttribute('class', 'cote-node-label');
    coreLabel.setAttribute('x', String(CX));
    coreLabel.setAttribute('y', String(CY + 52));
    coreLabel.textContent = 'Organism';
    coreG.appendChild(corePulse);
    coreG.appendChild(coreBody);
    coreG.appendChild(coreRing);
    coreG.appendChild(coreHit);
    coreG.appendChild(coreLabel);
    field.appendChild(coreG);

    var nodesG = ns('g');
    nodesG.setAttribute('class', 'cote-nodes');
    NODES.forEach(function (cfg) {
      var pos = polar(cfg.angle, RING);
      var m = subs[cfg.id] || { paused: true };
      var g = ns('g');
      g.setAttribute('class', 'cote-node ' + nodeVisualClass(m, cfg.id));
      g.setAttribute('data-node', cfg.id);
      var pulse = ns('circle');
      pulse.setAttribute('class', 'cote-node-pulse');
      pulse.setAttribute('cx', String(pos.x));
      pulse.setAttribute('cy', String(pos.y));
      pulse.setAttribute('r', String(NODE_R + 6 + (m.pressure || 0) * 6));
      var body = ns('circle');
      body.setAttribute('class', 'cote-node-body');
      body.setAttribute('cx', String(pos.x));
      body.setAttribute('cy', String(pos.y));
      body.setAttribute('r', String(NODE_R + (m.pressure || 0) * 4));
      var hit = ns('circle');
      hit.setAttribute('class', 'cote-node-hit');
      hit.setAttribute('cx', String(pos.x));
      hit.setAttribute('cy', String(pos.y));
      hit.setAttribute('r', String(NODE_R + 10));
      var label = ns('text');
      label.setAttribute('class', 'cote-node-label');
      label.setAttribute('x', String(pos.x));
      label.setAttribute('y', String(pos.y + NODE_R + 14));
      label.textContent = cfg.label;
      g.appendChild(pulse);
      g.appendChild(body);
      g.appendChild(hit);
      g.appendChild(label);
      nodesG.appendChild(g);
    });
    field.appendChild(nodesG);

    field.querySelectorAll('.cote-node').forEach(function (node) {
      node.addEventListener('click', function () {
        showDetail(node.getAttribute('data-node'));
      });
      node.addEventListener('mouseenter', function () {
        showDetail(node.getAttribute('data-node'), true);
      });
    });

    renderAttention(data);
    updateHeaderPulse(data);
  }

  function renderAttention(data) {
    var box = document.getElementById('cote-attention');
    if (!box) return;
    var items = (data && data.operator_attention_required) || [];
    if (!items.length) {
      box.textContent = '';
      return;
    }
    box.innerHTML = items
      .slice(0, 4)
      .map(function (t) {
        return '<span>• ' + escapeHtml(t) + '</span>';
      })
      .join(' ');
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function showDetail(nodeId, hoverOnly) {
    if (!state.data || !nodeId) return;
    var detail = document.getElementById('cote-topology-detail');
    if (!detail) return;
    var m = (state.data.subsystems && state.data.subsystems[nodeId]) || {};
    var title = nodeId.replace(/_/g, ' ');
    detail.hidden = false;
    var learningBlock = '';
    if (nodeId === 'learning' && m.learning_status) {
      learningBlock =
        '<div class="cote-detail-learning">' +
        '<div><span>Status</span><strong>' +
        escapeHtml(m.learning_status) +
        '</strong></div>' +
        '<div class="cote-detail-learning-reason">' +
        escapeHtml(m.learning_reason || '') +
        '</div>' +
        metric('Last event', m.last_learning_event) +
        metric('Cycles', m.cycles_completed) +
        metric('Approvals', m.approvals_seen) +
        metric('Uploads', m.uploads_seen) +
        '</div>';
    }
    detail.innerHTML =
      '<strong>' +
      escapeHtml(title.charAt(0).toUpperCase() + title.slice(1)) +
      '</strong>' +
      (m.paused ? ' <em>(paused)</em>' : '') +
      learningBlock +
      '<div class="cote-detail-metrics">' +
      metric('Health', m.health) +
      metric('Pressure', m.pressure) +
      metric('Activity', m.activity) +
      metric('Confidence', m.confidence) +
      metric('Latency', m.latency) +
      metric('Alerts', m.alerts) +
      '</div>';
    if (!hoverOnly) state.selected = nodeId;
  }

  function metric(label, val) {
    var v = val == null ? '—' : typeof val === 'number' ? (val * 100).toFixed(0) + '%' : val;
    return '<div><span>' + label + '</span><strong>' + v + '</strong></div>';
  }

  function updateHeaderPulse(data) {
    var pulse = document.getElementById('org-pulse-label');
    var health = document.getElementById('health');
    if (!data) return;
    var sh = data.system_health != null ? data.system_health : 0;
    var gp = data.global_pressure != null ? data.global_pressure : 0;
    if (pulse) {
      if (data.safe_mode) {
        pulse.textContent = 'Topology live · intelligence paused';
      } else if (gp > 0.55) {
        pulse.textContent = 'Elevated operational pressure';
      } else if (sh > 0.78) {
        pulse.textContent = 'Organism stable';
      } else if (sh < 0.5) {
        pulse.textContent = 'Organism stressed — inspect topology';
      } else {
        pulse.textContent = 'Organism monitoring';
      }
    }
    if (health) {
      if (data.safe_mode) {
        health.textContent = 'Safe mode';
        health.className = 'kyc-pill kyc-pill--warn';
      } else if (sh > 0.75) {
        health.textContent = 'Healthy';
        health.className = 'kyc-pill kyc-pill--good';
      } else if (sh > 0.5) {
        health.textContent = 'Strained';
        health.className = 'kyc-pill kyc-pill--warn';
      } else {
        health.textContent = 'Critical';
        health.className = 'kyc-pill kyc-pill--bad';
      }
    }
  }

  function fetchTopology() {
    var ctrl = new AbortController();
    var timer = setTimeout(function () {
      ctrl.abort();
    }, 2500);
    return fetch('/api/cognitive-topology', {
      credentials: 'same-origin',
      signal: ctrl.signal,
    })
      .then(function (r) {
        return r.json();
      })
      .finally(function () {
        clearTimeout(timer);
      });
  }

  function refresh() {
    return fetchTopology()
      .then(function (data) {
        if (!data || data.ok === false) return data;
        state.data = data;
        renderTopology(data);
        return data;
      })
      .catch(function (err) {
        console.warn('COTE topology fetch failed', err);
        var mount = document.getElementById('cote-topology-mount');
        if (mount && !mount.querySelector('#cote-topology-svg')) {
          mount.innerHTML =
            '<p class="org-metric-foot" style="padding:1rem;">Topology unavailable — retry refresh.</p>';
        }
      });
  }

  function init() {
    ensureSvg();
    return refresh();
  }

  function startAutoRefresh(ms) {
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(refresh, ms || 45000);
  }

  global.CoteTopology = {
    init: init,
    refresh: refresh,
    startAutoRefresh: startAutoRefresh,
    render: renderTopology,
  };
})(typeof window !== 'undefined' ? window : globalThis);
