/**
 * Adaptive operator guidance panels — /api/operator/guidance
 */
(function (global) {
  'use strict';

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function sevClass(sev) {
    if (sev === 'green') return 'ok';
    if (sev === 'yellow') return 'info';
    if (sev === 'orange' || sev === 'amber') return 'warn';
    if (sev === 'red' || sev === 'critical') return 'bad';
    return 'info';
  }

  function stateLabel(state) {
    const map = {
      healthy: 'Healthy',
      degraded: 'Degraded',
      blind: 'Blind',
      unstable: 'Unstable',
      learning: 'Learning',
      blocked: 'Blocked',
      recovering: 'Recovering',
    };
    return map[state] || state;
  }

  async function api(path) {
    const r = await fetch(path, { credentials: 'same-origin' });
    if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
    return r.json();
  }

  function renderPriority(root, g) {
    const el = root.querySelector('[data-guidance="priority"]');
    if (!el) return;
    const p = g.priority_command || {};
    el.innerHTML =
      '<div class="guidance-priority">' +
      '<span class="org-card-state ' +
      sevClass(p.severity || g.priority_level) +
      '">' +
      esc((p.severity || g.priority_level || '—').toUpperCase()) +
      '</span>' +
      '<h3 class="guidance-action">' +
      esc(p.most_important_action || '—') +
      '</h3>' +
      '<p class="guidance-why"><strong>Why:</strong> ' +
      esc(p.why || '') +
      '</p>' +
      '<p class="guidance-risk"><strong>If ignored:</strong> ' +
      esc(p.if_ignored || '') +
      '</p>' +
      '<p class="guidance-time"><strong>Timeframe:</strong> ' +
      esc(p.timeframe || 'today') +
      '</p></div>';
  }

  function renderBottlenecks(root, items) {
    const el = root.querySelector('[data-guidance="bottlenecks"]');
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<p class="org-metric-foot">No bottlenecks detected.</p>';
      return;
    }
    el.innerHTML =
      '<ul class="guidance-list">' +
      items
        .map(
          (b) =>
            '<li><span class="org-card-state ' +
            sevClass(b.severity) +
            '">' +
            esc(b.severity) +
            '</span> <strong>' +
            esc(b.title) +
            '</strong><br><span class="org-metric-foot">' +
            esc(b.detail) +
            '</span></li>'
        )
        .join('') +
      '</ul>';
  }

  function renderAttention(root, items) {
    const el = root.querySelector('[data-guidance="attention"]');
    if (!el) return;
    if (!items.length) {
      el.innerHTML = '<p class="org-metric-foot">No attention targets right now.</p>';
      return;
    }
    el.innerHTML =
      '<ul class="guidance-list">' +
      items
        .map(
          (t) =>
            '<li><strong>' +
            esc((t.role || t.type || 'target').replace(/_/g, ' ')) +
            '</strong>: ' +
            esc(t.label || t.id || '—') +
            (t.detail ? '<br><span class="org-metric-foot">' + esc(t.detail) + '</span>' : '') +
            '</li>'
        )
        .join('') +
      '</ul>';
  }

  function renderLearn(root, articles) {
    const el = root.querySelector('[data-guidance="learn"]');
    if (!el) return;
    if (!articles.length) {
      el.innerHTML = '<p class="org-metric-foot">No contextual articles.</p>';
      return;
    }
    el.innerHTML = articles
      .map(
        (a) =>
          '<div class="guidance-learn-item">' +
          '<a href="#" data-learn-topic="' +
          esc(a.id) +
          '">' +
          esc(a.title) +
          '</a>' +
          '<p class="org-metric-foot">' +
          esc(a.why_relevant_now || a.snippet) +
          '</p></div>'
      )
      .join('');
    el.querySelectorAll('[data-learn-topic]').forEach((a) => {
      a.addEventListener('click', (ev) => {
        ev.preventDefault();
        if (global.OperatorCockpit && global.OperatorCockpit.loadTopic) {
          global.OperatorCockpit.loadTopic(
            a.getAttribute('data-learn-topic'),
            root.querySelector('[data-cockpit="topic-body"]'),
            root.querySelector('[data-cockpit="topic-title"]')
          );
        }
      });
    });
  }

  function renderOrganismState(root, g) {
    const el = root.querySelector('[data-guidance="organism-state"]');
    if (!el) return;
    const s = g.organism_summary || {};
    el.innerHTML =
      '<div class="guidance-organism">' +
      '<div class="guidance-organism-state">' +
      stateLabel(g.organism_state) +
      '</div>' +
      '<p>Observability: <strong>' +
      esc(s.verdict || '—') +
      '</strong> · Entities: ' +
      esc(s.entity_count) +
      ' · Orphans: ' +
      esc(s.orphan_count) +
      '</p>' +
      '<p class="org-metric-foot">Confidence ' +
      Math.round((g.confidence || 0) * 100) +
      '% · Telemetry events ' +
      esc(s.telemetry_events) +
      '</p></div>';
    const rec = g.recommendations || {};
    const all = []
      .concat(rec.immediate || [])
      .concat(rec.short_term || [])
      .concat(rec.strategic || []);
    const recEl = root.querySelector('[data-guidance="recommendations"]');
    if (recEl) {
      recEl.innerHTML = all.length
        ? '<ul class="guidance-list">' +
          all
            .slice(0, 8)
            .map((t) => '<li>' + esc(t) + '</li>')
            .join('') +
          '</ul>'
        : '<p class="org-metric-foot">No recommendations.</p>';
    }
  }

  function renderCustomerFriction(root, f) {
    const el = root.querySelector('[data-guidance="customer-friction"]');
    if (!el || !f) return;
    const c = f.continuation || {};
    const help = (f.top_requested_help || [])
      .map((h) => '<li>' + esc(h.item_id) + ' (' + h.count + ')</li>')
      .join('');
    const drop = (f.onboarding_dropoffs || [])
      .map((d) => '<li>' + esc(d.step) + ': ' + d.count + '</li>')
      .join('');
    el.innerHTML =
      '<div class="guidance-grid">' +
      '<p><strong>Continuation:</strong> opened ' +
      (c.opened || 0) +
      ', completed ' +
      (c.completed || 0) +
      ', abandoned ' +
      (c.abandoned || 0) +
      (c.completion_rate != null ? ' · completion ' + Math.round(c.completion_rate * 100) + '%' : '') +
      '</p>' +
      '<p><strong>Mobile vs desktop:</strong> ' +
      (f.mobile_vs_desktop?.mobile || 0) +
      ' / ' +
      (f.mobile_vs_desktop?.desktop || 0) +
      '</p>' +
      '<p><strong>Example views:</strong> ' +
      (f.example_views || 0) +
      ' · <strong>Retrieval help:</strong> ' +
      (f.retrieval_help_views || 0) +
      '</p>' +
      '<p><strong>Top help requests</strong></p><ul class="guidance-list">' +
      (help || '<li>None yet</li>') +
      '</ul>' +
      '<p><strong>Drop-off steps</strong></p><ul class="guidance-list">' +
      (drop || '<li>None yet</li>') +
      '</ul></div>';
  }

  async function refreshGuidance(root, projectId, mode) {
    const params = new URLSearchParams();
    if (projectId) params.set('project_id', projectId);
    if (mode) params.set('mode', mode);
    const data = await api('/api/operator/guidance?' + params.toString());
    const g = data.guidance;
    renderPriority(root, g);
    renderBottlenecks(root, g.bottlenecks || []);
    renderAttention(root, g.attention_targets || []);
    renderLearn(root, g.recommended_learning || []);
    renderOrganismState(root, g);
    try {
      const friction = await api('/api/operator/customer-friction');
      renderCustomerFriction(root, friction);
    } catch (_) {
      const el = root.querySelector('[data-guidance="customer-friction"]');
      if (el) el.innerHTML = '<p class="org-metric-foot">Friction metrics unavailable.</p>';
    }
    const badge = root.querySelector('#guidance-state-badge');
    if (badge) {
      badge.textContent = stateLabel(g.organism_state);
      badge.className = 'kyc-pill kyc-pill--' + (g.organism_state === 'healthy' ? 'ok' : 'warn');
    }
    return g;
  }

  global.OperatorGuidance = { refreshGuidance, api, renderPriority };
})(typeof window !== 'undefined' ? window : globalThis);
