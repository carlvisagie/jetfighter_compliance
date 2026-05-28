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
  var state = {
    data: null,
    lastGood: null,
    selected: null,
    timer: null,
    refreshGen: 0,
    refreshing: false,
  };

  function logCoteRenderError(nodeId, reason, detail) {
    var payload = { nodeId: nodeId, reason: reason, detail: detail || {} };
    console.error('COTE_RENDER_ERROR', payload);
    return payload;
  }

  function numMetric(v, fallback) {
    if (v === null || v === undefined || v === '') return fallback;
    var n = Number(v);
    return isFinite(n) ? n : fallback;
  }

  function clamp01(n) {
    return Math.max(0, Math.min(1, n));
  }

  function uncertainSubsystem(nodeId, reason) {
    return {
      health: 0.48,
      pressure: 0.25,
      activity: 0.15,
      confidence: 0.35,
      latency: 0.1,
      alerts: 0,
      paused: false,
      anomaly: true,
      _cote_uncertain: true,
      _cote_reason: reason || 'uncertain',
    };
  }

  function normalizeSubsystem(raw, nodeId) {
    try {
      if (raw === null || raw === undefined) {
        logCoteRenderError(nodeId, 'null_subsystem');
        return uncertainSubsystem(nodeId, 'null_subsystem');
      }
      if (typeof raw !== 'object' || Array.isArray(raw)) {
        logCoteRenderError(nodeId, 'malformed_subsystem', { type: typeof raw });
        return uncertainSubsystem(nodeId, 'malformed_subsystem');
      }
      var m = {
        health: clamp01(numMetric(raw.health, 0.5)),
        pressure: clamp01(numMetric(raw.pressure, 0.2)),
        activity: clamp01(numMetric(raw.activity, 0.2)),
        confidence: clamp01(numMetric(raw.confidence, 0.5)),
        latency: clamp01(numMetric(raw.latency, 0.05)),
        alerts: Math.max(0, intMetric(raw.alerts)),
        paused: !!raw.paused,
        anomaly: !!raw.anomaly,
        _cote_uncertain: false,
      };
      var numericFields = ['health', 'pressure', 'activity', 'confidence', 'latency'];
      numericFields.forEach(function (field) {
        if (raw[field] != null && raw[field] !== '' && !isFinite(Number(raw[field]))) {
          m._cote_uncertain = true;
          logCoteRenderError(nodeId, 'malformed_metric', { field: field, value: raw[field] });
        }
      });
      Object.keys(raw).forEach(function (k) {
        if (Object.prototype.hasOwnProperty.call(m, k)) return;
        var v = raw[k];
        if (v !== null && typeof v !== 'function') m[k] = v;
      });
      return m;
    } catch (e) {
      logCoteRenderError(nodeId, 'normalize_exception', { message: e.message });
      return uncertainSubsystem(nodeId, 'normalize_exception');
    }
  }

  function normalizeTopologyPayload(data) {
    var base = data && typeof data === 'object' && !Array.isArray(data) ? data : {};
    var subsIn = base.subsystems;
    if (subsIn === null || typeof subsIn !== 'object' || Array.isArray(subsIn)) {
      if (subsIn != null) logCoteRenderError('topology', 'invalid_subsystems_container', { type: typeof subsIn });
      subsIn = {};
    }
    var subs = {};
    NODES.forEach(function (cfg) {
      subs[cfg.id] = normalizeSubsystem(subsIn[cfg.id], cfg.id);
    });
    subs.system_health = normalizeSubsystem(subsIn.system_health, 'system_health');
    return Object.assign({}, base, {
      ok: base.ok !== false,
      subsystems: subs,
      global_pressure: numMetric(base.global_pressure, 0),
      system_health: numMetric(base.system_health, subs.system_health.health),
    });
  }

  function validateTopologyPayload(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      return { valid: false, reason: 'not_object' };
    }
    if (data.ok === false) return { valid: false, reason: 'ok_false' };
    if (!data.subsystems || typeof data.subsystems !== 'object' || Array.isArray(data.subsystems)) {
      return { valid: false, reason: 'missing_subsystems' };
    }
    var missing = [];
    NODES.forEach(function (cfg) {
      var row = data.subsystems[cfg.id];
      if (row === null || row === undefined) missing.push(cfg.id);
    });
    if (missing.length) return { valid: false, reason: 'missing_nodes', missing: missing };
    return { valid: true };
  }

  function mergeTopologyPayload(incoming, lastGood) {
    var normalized = normalizeTopologyPayload(incoming || {});
    var check = validateTopologyPayload(normalized);
    if (check.valid) {
      return { data: normalized, valid: true, usedFallback: false };
    }
    if (lastGood) {
      var goodNorm = normalizeTopologyPayload(lastGood);
      var goodCheck = validateTopologyPayload(goodNorm);
      if (goodCheck.valid) {
        logCoteRenderError('topology', 'using_last_known_good', {
          reason: check.reason,
          missing: check.missing || [],
        });
        return {
          data: goodNorm,
          valid: true,
          usedFallback: true,
          fallbackReason: check.reason,
        };
      }
    }
    return { data: normalized, valid: true, usedFallback: false, partial: true, reason: check.reason };
  }

  function ns(tag) {
    return document.createElementNS('http://www.w3.org/2000/svg', tag);
  }

  function polar(angleDeg, radius) {
    var a = ((angleDeg - 90) * Math.PI) / 180;
    return { x: CX + radius * Math.cos(a), y: CY + radius * Math.sin(a) };
  }

  /** Visual state only (colour / shape) — motion comes from vioMotionClasses. */
  function nodeStateClasses(m, nodeId) {
    if (!m) return 'cote-node--uncertain';
    if (m._cote_uncertain) return 'cote-node--uncertain';
    if (nodeId === 'learning') {
      var ls = m.learning_status;
      if (ls === 'failed') return 'cote-node--failed';
      if (ls === 'degraded') return 'cote-node--unstable';
      if (ls === 'warming_up') return 'cote-node--warming-up';
      if (ls === 'healthy') return 'cote-node--healthy';
    }
    if (nodeId === 'telemetry') {
      var tp = m.telemetry_pulse || '';
      if (tp === 'write_failure' || m.telemetry_status === 'failed') {
        return 'cote-node--telemetry-write-fail';
      }
      if (tp === 'backlog' || intMetric(m.queue_depth) >= 50) {
        return 'cote-node--telemetry-backlog';
      }
      if (tp === 'stale' || m.stale_threshold_exceeded || m.telemetry_status === 'degraded') {
        return 'cote-node--telemetry-stale';
      }
      if (tp === 'healthy_flow' || m.telemetry_status === 'healthy') {
        return 'cote-node--healthy';
      }
    }
    if (nodeId === 'upload_pipeline') {
      var pending = intMetric(m.pending_review || m.queue_depth) > 0;
      var urgent = intMetric(m.urgent_count) > 0;
      var h = numMetric(m.health, 0.5);
      var sev = String(m.upload_node_severity || '').toLowerCase();
      if (sev === 'red' || (m.anomaly && h < 0.45)) {
        return 'cote-node--failed cote-node--upload-fail';
      }
      if (sev === 'amber' || intMetric(m.integrity_mismatch_count) > 0) {
        return 'cote-node--upload-pending cote-node--upload-urgent';
      }
      if (sev === 'green' && !m.anomaly && intMetric(m.integrity_mismatch_count) === 0) {
        return 'cote-node--healthy';
      }
      if (m.anomaly && h < 0.45) return 'cote-node--failed cote-node--upload-fail';
      if (urgent && pending) return 'cote-node--upload-urgent cote-node--upload-pending';
      if (pending) return 'cote-node--upload-pending';
      if (m.backlog_pressure || intMetric(m.queue_depth) >= 5) {
        return 'cote-node--pressure cote-node--upload-backlog';
      }
      if (m.flow_active || numMetric(m.activity, 0) > 0.45) {
        return 'cote-node--opportunity';
      }
    }
    if (m.paused) return 'cote-node--paused';
    var health = numMetric(m.health, 0.5);
    var pressure = numMetric(m.pressure, 0);
    var activity = numMetric(m.activity, 0);
    var confidence = numMetric(m.confidence, 0.5);
    if (health < 0.35) return 'cote-node--failed';
    if (m.anomaly || health < 0.52) return 'cote-node--unstable';
    if (pressure > 0.62) return 'cote-node--pressure';
    if (confidence < 0.42) return 'cote-node--uncertain';
    if (activity > 0.72 && health > 0.68 && !m.paused) return 'cote-node--opportunity';
    if (health > 0.72 && pressure < 0.42) return 'cote-node--healthy';
    return 'cote-node--healthy';
  }

  /**
   * VIO motion doctrine: no movement unless it demands attention.
   * Returns motion modifier classes (stable | attention | flow).
   */
  function vioMotionClasses(state, m, nodeId) {
    if (!state) return 'cote-vio-stable';
    if (state.indexOf('cote-node--failed') >= 0 || state.indexOf('cote-node--upload-fail') >= 0) {
      return 'cote-vio-attention cote-vio-attention--failed';
    }
    if (state.indexOf('cote-node--upload-urgent') >= 0) {
      return 'cote-vio-attention cote-vio-attention--urgent';
    }
    if (state.indexOf('cote-node--unstable') >= 0 || state.indexOf('cote-node--telemetry-write-fail') >= 0) {
      return 'cote-vio-attention cote-vio-attention--urgent';
    }
    if (state.indexOf('cote-node--telemetry-stale') >= 0) {
      return 'cote-vio-attention cote-vio-attention--pressure';
    }
    if (state.indexOf('cote-node--pressure') >= 0 || state.indexOf('cote-node--upload-pending') >= 0) {
      return 'cote-vio-attention cote-vio-attention--pressure';
    }
    if (state.indexOf('cote-node--uncertain') >= 0) {
      return 'cote-vio-attention cote-vio-attention--pressure';
    }
    if (state.indexOf('cote-node--telemetry-backlog') >= 0 || state.indexOf('cote-node--upload-backlog') >= 0) {
      return 'cote-vio-flow cote-vio-attention cote-vio-attention--pressure';
    }
    if (state.indexOf('cote-node--opportunity') >= 0 && (m.flow_active || numMetric(m.activity, 0) > 0.45)) {
      return 'cote-vio-flow';
    }
    if (state.indexOf('cote-node--warming-up') >= 0 || state.indexOf('cote-node--paused') >= 0) {
      return 'cote-vio-stable';
    }
    if (state.indexOf('cote-node--healthy') >= 0) {
      return 'cote-vio-stable';
    }
    if (state.indexOf('cote-node--opportunity') >= 0) {
      return 'cote-vio-stable';
    }
    return 'cote-vio-stable';
  }

  function nodeVisualClass(m, nodeId) {
    var state = nodeStateClasses(m, nodeId);
    return state + ' ' + vioMotionClasses(state, m, nodeId);
  }

  function organismHeartbeatEligible(data) {
    if (!data || data.safe_mode) return false;
    var subs = data.subsystems || {};
    var core = subs.system_health || {};
    if (numMetric(core.health, 0) < 0.72) return false;
    if (numMetric(data.global_pressure, 0) > 0.38) return false;
    for (var i = 0; i < NODES.length; i++) {
      var id = NODES[i].id;
      var state = nodeStateClasses(subs[id], id);
      if (state.indexOf('cote-node--healthy') < 0) return false;
    }
    return true;
  }

  function nodeNeedsAttentionRing(state, nodeId, m) {
    if (state.indexOf('cote-node--upload-urgent') >= 0) return true;
    if (nodeId === 'telemetry' && state.indexOf('cote-node--telemetry-backlog') >= 0) return true;
    return false;
  }

  function nodeNeedsFlowParticle(state) {
    return state.indexOf('cote-vio-flow') >= 0;
  }

  function coreVisualClass(m, globalPressure) {
    if (!m) return 'cote-node--uncertain';
    if (m._cote_uncertain) return 'cote-node--uncertain';
    var health = numMetric(m.health, 0.5);
    var gp = numMetric(globalPressure, 0);
    if (health < 0.4) return 'cote-node--failed';
    if (m.anomaly || gp > 0.55) return 'cote-node--unstable';
    if (gp > 0.38) return 'cote-node--pressure';
    if (health > 0.8) return 'cote-node--healthy';
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

  function buildRingNodeGroup(cfg, m) {
    var pos = polar(cfg.angle, RING);
    var pressure = numMetric(m.pressure, 0);
    var state = nodeStateClasses(m, cfg.id);
    var motion = vioMotionClasses(state, m, cfg.id);
    var g = ns('g');
    g.setAttribute('class', 'cote-node ' + state + ' ' + motion);
    g.setAttribute('data-node', cfg.id);
    if (m._cote_uncertain) g.setAttribute('data-cote-uncertain', 'true');

    var pulse = ns('circle');
    pulse.setAttribute('class', 'cote-node-pulse');
    pulse.setAttribute('cx', String(pos.x));
    pulse.setAttribute('cy', String(pos.y));
    pulse.setAttribute('r', String(NODE_R + 6 + pressure * 6));

    var body = ns('circle');
    body.setAttribute('class', 'cote-node-body');
    body.setAttribute('cx', String(pos.x));
    body.setAttribute('cy', String(pos.y));
    body.setAttribute('r', String(NODE_R + pressure * 4));

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

    if (nodeNeedsAttentionRing(state, cfg.id, m)) {
      var alertRing = ns('circle');
      alertRing.setAttribute('class', 'cote-node-alert-ring');
      alertRing.setAttribute('cx', String(pos.x));
      alertRing.setAttribute('cy', String(pos.y));
      alertRing.setAttribute('r', String(NODE_R + 14));
      g.insertBefore(alertRing, pulse);
    }

    if (cfg.id === 'upload_pipeline') {
      var pendingN = intMetric(m.pending_review || m.queue_depth);
      var urgentN = intMetric(m.urgent_count);
      if (pendingN > 0) {
        var badgeBg = ns('circle');
        badgeBg.setAttribute('class', 'cote-node-badge-bg');
        badgeBg.setAttribute('cx', String(pos.x + 16));
        badgeBg.setAttribute('cy', String(pos.y - 16));
        badgeBg.setAttribute('r', '11');
        var badge = ns('text');
        badge.setAttribute('class', 'cote-node-badge');
        badge.setAttribute('x', String(pos.x + 16));
        badge.setAttribute('y', String(pos.y - 12));
        badge.setAttribute('text-anchor', 'middle');
        badge.textContent = urgentN > 0 ? pendingN + '!' : String(pendingN);
        g.appendChild(badgeBg);
        g.appendChild(badge);
      }
    }

    g.appendChild(body);
    g.appendChild(hit);
    g.appendChild(label);

    if (nodeNeedsFlowParticle(motion)) {
      var particle = ns('circle');
      particle.setAttribute('class', 'cote-vio-particle');
      particle.setAttribute('cx', String(pos.x + NODE_R + 10));
      particle.setAttribute('cy', String(pos.y));
      particle.setAttribute('r', '3');
      g.appendChild(particle);
    }

    return g;
  }

  function bindNodeInteractions(field) {
    field.querySelectorAll('.cote-node').forEach(function (node) {
      node.addEventListener('click', function () {
        var nid = node.getAttribute('data-node');
        if (nid === 'upload_pipeline' && global.CockpitFoundingBeta) {
          global.CockpitFoundingBeta.scrollToQueue();
        }
        showDetail(nid, false, nid === 'telemetry');
      });
      node.addEventListener('mouseenter', function () {
        showDetail(node.getAttribute('data-node'), true);
      });
    });
  }

  function renderTopology(data, opts) {
    opts = opts || {};
    var svg = ensureSvg();
    if (!svg) return;
    var field = svg.querySelector('#cote-field');
    if (!field) return;

    var normalized = normalizeTopologyPayload(data || {});
    var subs = normalized.subsystems || {};

    while (field.firstChild) field.removeChild(field.firstChild);

    var gp = numMetric(normalized.global_pressure, 0);
    var mount = document.getElementById('cote-topology-mount');
    if (mount) {
      mount.classList.toggle('cote-mount--safe', !!normalized.safe_mode);
      mount.classList.toggle('cote-mount--refreshing', !!state.refreshing);
      mount.classList.toggle('cote-mount--fallback', !!opts.usedFallback);
      mount.classList.toggle('cote-mount--organism-heartbeat', organismHeartbeatEligible(normalized));
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
      var sm = subs[cfg.id] || uncertainSubsystem(cfg.id, 'missing_at_render');
      line.style.strokeOpacity = String(0.15 + numMetric(sm.activity, 0) * 0.45);
      links.appendChild(line);
    });
    field.appendChild(links);

    var coreG = ns('g');
    var coreMetrics = subs.system_health || uncertainSubsystem('system_health', 'missing_core');
    var coreState = coreVisualClass(coreMetrics, gp);
    var coreMotion = organismHeartbeatEligible(normalized) ? ' cote-vio-organism-heartbeat' : ' cote-vio-core-stable';
    coreG.setAttribute('class', 'cote-node cote-core ' + coreState + coreMotion);
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
      try {
        var m = subs[cfg.id] || uncertainSubsystem(cfg.id, 'missing_at_render');
        var g = buildRingNodeGroup(cfg, m);
        nodesG.appendChild(g);
      } catch (e) {
        logCoteRenderError(cfg.id, 'node_render_failed', { message: e.message });
        try {
          nodesG.appendChild(buildRingNodeGroup(cfg, uncertainSubsystem(cfg.id, 'node_render_failed')));
        } catch (e2) {
          logCoteRenderError(cfg.id, 'fallback_node_render_failed', { message: e2.message });
        }
      }
    });
    field.appendChild(nodesG);

    bindNodeInteractions(field);
    renderAttention(normalized);
    updateHeaderPulse(normalized);
  }

  function safeRenderTopology(data, opts) {
    try {
      renderTopology(data, opts);
    } catch (e) {
      logCoteRenderError('topology', 'render_collapse', { message: e.message });
      if (state.lastGood && data !== state.lastGood) {
        safeRenderTopology(state.lastGood, { usedFallback: true });
      }
    }
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

  function showDetail(nodeId, hoverOnly, loadTelemetryDiag) {
    if (!state.data || !nodeId) return;
    var detail = document.getElementById('cote-topology-detail');
    if (!detail) return;
    var raw = (state.data.subsystems && state.data.subsystems[nodeId]) || null;
    var m = normalizeSubsystem(raw, nodeId);
    detail.hidden = false;
    if (loadTelemetryDiag && nodeId === 'telemetry') {
      detail.innerHTML =
        '<strong>Telemetry diagnostics</strong><p class="kyc-loading">Loading telemetry status…</p>';
      fetchTelemetryDiagnostics(m, hoverOnly);
      return;
    }
    renderDetailPanel(nodeId, m, hoverOnly);
  }

  function fetchTelemetryDiagnostics(m, hoverOnly) {
    fetch('/api/operator/telemetry-status', { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error('telemetry-status ' + r.status);
        return r.json();
      })
      .then(function (diag) {
        renderTelemetryDetailPanel(m, diag, hoverOnly);
      })
      .catch(function (err) {
        var detail = document.getElementById('cote-topology-detail');
        if (!detail) return;
        detail.innerHTML =
          '<strong>Telemetry diagnostics</strong>' +
          '<p class="org-metric-foot cote-telemetry-warn">Could not load diagnostics: ' +
          escapeHtml(err.message || String(err)) +
          '</p>' +
          renderTelemetryMetricsOnly(m);
      });
  }

  function renderTelemetryMetricsOnly(m) {
    return (
      '<div class="cote-detail-metrics">' +
      metric('Health', m.health) +
      metric('Status', m.telemetry_status) +
      metric('Pulse', m.telemetry_pulse) +
      '</div>'
    );
  }

  function renderTelemetryDetailPanel(m, diag, hoverOnly) {
    var detail = document.getElementById('cote-topology-detail');
    if (!detail) return;
    var reasons = diag.degraded_reasons || [];
    var reasonsHtml = '';
    if (reasons.length) {
      reasonsHtml =
        '<ul class="cote-telemetry-reasons">' +
        reasons
          .map(function (r) {
            return (
              '<li><strong>' +
              escapeHtml(r.code || 'issue') +
              '</strong> · ' +
              escapeHtml(r.subsystem || 'telemetry') +
              '<p>' +
              escapeHtml(r.message || '') +
              '</p><p class="cote-telemetry-action"><em>Action:</em> ' +
              escapeHtml(r.recommended_action || '') +
              '</p></li>'
            );
          })
          .join('') +
        '</ul>';
    } else {
      reasonsHtml = '<p class="org-metric-foot">Telemetry flow healthy — recent events ingesting normally.</p>';
    }
    detail.innerHTML =
      '<strong>Telemetry diagnostics</strong>' +
      '<div class="cote-detail-telemetry-summary">' +
      '<div><span>Health</span><strong class="cote-telemetry-health--' +
      escapeHtml(diag.telemetry_health || 'unknown') +
      '">' +
      escapeHtml(diag.telemetry_health || '—') +
      '</strong></div>' +
      '<div><span>Pulse</span><strong>' +
      escapeHtml(diag.telemetry_pulse || '—') +
      '</strong></div>' +
      '<div><span>Stale threshold</span><strong>' +
      (diag.stale_threshold_exceeded ? 'Exceeded' : 'OK') +
      '</strong></div>' +
      '</div>' +
      '<div class="cote-detail-metrics">' +
      metric('Sample count', diag.telemetry_sample_count) +
      metric('Ingest / hr', diag.telemetry_ingest_rate_per_hour) +
      metric('Last write', diag.last_telemetry_write_utc) +
      metric('Queue depth', diag.queue_depth) +
      metric('Parse errors', diag.parse_error_count) +
      metric('Dropped', diag.dropped_event_count) +
      metric('High latency', diag.high_latency_event_count) +
      '</div>' +
      '<p class="org-metric-foot"><strong>Storage:</strong> <code>' +
      escapeHtml(diag.telemetry_storage_path || '') +
      '</code></p>' +
      (diag.failing_subsystems && diag.failing_subsystems.length
        ? '<p class="org-metric-foot"><strong>Failing subsystems:</strong> ' +
          escapeHtml(diag.failing_subsystems.join(', ')) +
          '</p>'
        : '') +
      '<div class="cote-telemetry-reasons-wrap"><span class="kyc-metric-label">Degraded reasons</span>' +
      reasonsHtml +
      '</div>' +
      (diag.last_telemetry_errors && diag.last_telemetry_errors.length
        ? '<div class="cote-telemetry-errors"><span class="kyc-metric-label">Recent errors</span><ul>' +
          diag.last_telemetry_errors
            .map(function (e) {
              return (
                '<li><code>' +
                escapeHtml(e.subsystem + '/' + e.event_type) +
                '</code> ' +
                escapeHtml(e.message || '') +
                '</li>'
              );
            })
            .join('') +
          '</ul></div>'
        : '') +
      renderTelemetryMetricsOnly(m);
    if (!hoverOnly) state.selected = 'telemetry';
  }

  function renderDetailPanel(nodeId, m, hoverOnly) {
    var detail = document.getElementById('cote-topology-detail');
    if (!detail) return;
    var title = nodeId.replace(/_/g, ' ');
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
    var uncertainNote = m._cote_uncertain
      ? ' <em class="cote-uncertain-tag">(uncertain — payload incomplete)</em>'
      : '';
    detail.innerHTML =
      '<strong>' +
      escapeHtml(title.charAt(0).toUpperCase() + title.slice(1)) +
      '</strong>' +
      uncertainNote +
      (m.paused ? ' <em>(paused)</em>' : '') +
      learningBlock +
      '<div class="cote-detail-metrics">' +
      metric('Health', m.health) +
      metric('Pressure', m.pressure) +
      metric('Activity', m.activity) +
      metric('Confidence', m.confidence) +
      metric('Latency', m.latency) +
      metric('Alerts', m.alerts) +
      metric('Pending', m.pending_review) +
      metric('Urgent', m.urgent_count) +
      '</div>';
    if (nodeId === 'upload_pipeline' && global.CockpitFoundingBeta) {
      detail.innerHTML +=
        '<p class="org-metric-foot"><button type="button" class="kyc-btn kyc-btn--secondary" id="coteUploadScrollQueue">Jump to Founding Beta Queue</button></p>';
      document.getElementById('coteUploadScrollQueue')?.addEventListener('click', function () {
        global.CockpitFoundingBeta.scrollToQueue();
      });
    }
    if (!hoverOnly) state.selected = nodeId;
  }

  function metric(label, val) {
    var v = '—';
    if (val != null) {
      if (typeof val === 'number' && val >= 0 && val <= 1) {
        v = (val * 100).toFixed(0) + '%';
      } else if (typeof val === 'number') {
        v = String(val);
      } else {
        v = val;
      }
    }
    return '<div><span>' + label + '</span><strong>' + v + '</strong></div>';
  }

  function intMetric(v) {
    var n = parseInt(v, 10);
    return isNaN(n) ? 0 : n;
  }

  function paperworkPendingLabel(data) {
    var up = (data && data.subsystems && data.subsystems.upload_pipeline) || {};
    var pending = intMetric(up.pending_review || up.queue_depth);
    var urgent = intMetric(up.urgent_count);
    var fb = global.CockpitFoundingBeta && global.CockpitFoundingBeta.getState();
    if (fb && !fb.error) {
      pending = Math.max(pending, fb.pending || 0);
      urgent = Math.max(urgent, fb.urgent || 0);
    }
    if (pending <= 0) return '';
    var label =
      pending === 1 ? '1 paperwork review pending' : pending + ' paperwork reviews pending';
    if (urgent > 0) label += ' (' + urgent + ' urgent)';
    return label;
  }

  function updateHeaderPulse(data) {
    var pulse = document.getElementById('org-pulse-label');
    var health = document.getElementById('health');
    if (!data) return;
    var sh = numMetric(data.system_health, numMetric(data.subsystems && data.subsystems.system_health && data.subsystems.system_health.health, 0));
    var gp = numMetric(data.global_pressure, 0);
    var paperwork = paperworkPendingLabel(data);
    if (pulse) {
      if (paperwork) {
        pulse.textContent = paperwork;
      } else if (data.safe_mode) {
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

  function applyTopologyResponse(data, gen) {
    if (gen !== state.refreshGen) return null;
    var merged = mergeTopologyPayload(data, state.lastGood);
    if (!merged.data) return null;
    state.data = merged.data;
    if (!merged.usedFallback) state.lastGood = merged.data;
    safeRenderTopology(merged.data, { usedFallback: merged.usedFallback });
    return merged;
  }

  function refresh() {
    var gen = ++state.refreshGen;
    state.refreshing = true;
    var mount = document.getElementById('cote-topology-mount');
    if (mount) mount.classList.add('cote-mount--refreshing');
    return fetchTopology()
      .then(function (data) {
        state.refreshing = false;
        if (mount) mount.classList.remove('cote-mount--refreshing');
        if (data && data.ok === false) {
          logCoteRenderError('topology', 'api_ok_false', {});
          if (state.lastGood) {
            safeRenderTopology(state.lastGood, { usedFallback: true });
          }
          return data;
        }
        return applyTopologyResponse(data, gen);
      })
      .catch(function (err) {
        state.refreshing = false;
        if (mount) mount.classList.remove('cote-mount--refreshing');
        logCoteRenderError('topology', 'fetch_failed', { message: err.message || String(err) });
        if (state.lastGood) {
          safeRenderTopology(state.lastGood, { usedFallback: true });
        } else {
          console.warn('COTE topology fetch failed', err);
          if (mount && !mount.querySelector('#cote-topology-svg')) {
            mount.innerHTML =
              '<p class="org-metric-foot" style="padding:1rem;">Topology unavailable — retry refresh.</p>';
          }
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
    render: safeRenderTopology,
    normalizeSubsystem: normalizeSubsystem,
    normalizeTopologyPayload: normalizeTopologyPayload,
    validateTopologyPayload: validateTopologyPayload,
    mergeTopologyPayload: mergeTopologyPayload,
    buildRingNodeGroup: buildRingNodeGroup,
    nodeStateClasses: nodeStateClasses,
    vioMotionClasses: vioMotionClasses,
    nodeVisualClass: nodeVisualClass,
    organismHeartbeatEligible: organismHeartbeatEligible,
    NODES: NODES,
    logCoteRenderError: logCoteRenderError,
  };
})(typeof window !== 'undefined' ? window : globalThis);
