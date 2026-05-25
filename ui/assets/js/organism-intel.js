/**
 * Organism intelligence — live API aggregation for control + memory surfaces.
 * Canonical truth remains server-side central memory; this layer only visualizes.
 */
(function (global) {
  'use strict';

  async function api(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
    return r.json();
  }

  function stateClass(level) {
    if (level === 'ok') return 'ok';
    if (level === 'warn') return 'warn';
    if (level === 'bad') return 'bad';
    return 'info';
  }

  function fmtTime(iso) {
    if (!iso) return '—';
    const d = iso.replace('T', ' ').replace('Z', '');
    return d.length > 16 ? d.slice(5, 16) : d;
  }

  function countLearningSignals(learning) {
    const eff = learning?.signal_effectiveness || {};
    return Object.keys(eff).length;
  }

  function conversionTotal(learning) {
    const c = learning?.conversion_counts || {};
    return (c.inquiry_to_intake || 0) + (c.lead_to_inquiry || 0) + (c.intake_to_evidence || 0);
  }

  function observabilityLabel(verdict) {
    if (verdict === 'organism_observable') return { text: 'Observable', level: 'ok' };
    if (verdict === 'partially_observable') return { text: 'Partial', level: 'warn' };
    if (verdict === 'not_observable') return { text: 'Warming up', level: 'info' };
    return { text: verdict || 'Unknown', level: 'info' };
  }

  function memoryIntegrity(heal) {
    const orphans = (heal?.orphan_projects || []).length;
    const missingTl = (heal?.missing_timeline_entities || []).length;
    const entities = heal?.entity_count || 0;
    let level = 'ok';
    if (orphans > 10 || missingTl > 5) level = 'bad';
    else if (orphans > 0 || missingTl > 0) level = 'warn';
    const timelineOk = entities > 0 && missingTl === 0;
    const entityOk = entities > 0;
    return {
      level,
      summary: timelineOk && entityOk ? 'Continuity intact' : 'Gaps detected',
      lines: [
        'Entities tracked: ' + entities,
        'Timeline gaps: ' + missingTl,
        'Orphan projects: ' + orphans,
        'Entity continuity: ' + (entityOk ? 'active' : 'empty'),
      ],
      orphans,
      entities,
    };
  }

  async function fetchOrganismSnapshot() {
    const [healthz, ready, heal, obs, learning, adaptive, telemetry, events, projects] =
      await Promise.all([
        api('/healthz').catch(() => ({ ok: false })),
        api('/health/ready').catch(() => ({ ok: false, checks: {} })),
        api('/api/memory/self-heal').catch(() => ({ ok: false, report: {} })),
        api('/api/memory/observability?limit=80').catch(() => ({ ok: false })),
        api('/api/memory/learning').catch(() => ({ ok: false, learning: {} })),
        api('/api/memory/adaptive-signals?limit=50').catch(() => ({ ok: false, signals: [] })),
        api('/api/memory/telemetry?limit=40').catch(() => ({ ok: false, telemetry: [] })),
        api('/api/events/recent?limit=15').catch(() => ({ ok: false, events: [] })),
        api('/api/projects').catch(() => ({ ok: false, projects: [] })),
      ]);

    const report = heal.report || {};
    const mem = memoryIntegrity(report);
    const obsVerdict = observabilityLabel(obs.verdict);
    const subsystems = obs.subsystem_health || {};
    const subsystemCount = Object.keys(subsystems).length;
    const repeated = obs.repeated_failures || [];
    const tel = telemetry.telemetry || [];
    const emailFails = tel.filter(
      (t) => t.subsystem === 'email' && !t.success
    ).length;
    const acqTel = tel.filter((t) => t.subsystem === 'acquisition');
    const highPriority = acqTel.filter(
      (t) => t.event_type === 'high_priority_lead_found'
    ).length;
    const leadScored = acqTel.filter((t) => t.event_type === 'lead_scored').length;
    const discovery = acqTel.filter((t) =>
      ['discovery_started', 'discovery_completed'].includes(t.event_type)
    ).length;
    const learn = learning.learning || {};
    const adaptiveN = (adaptive.signals || []).length;
    const smtpOk = !!ready.checks?.smtp_configured;
    const suggestions = report.suggestions_written || 0;
    const telFails = tel.filter((t) => !t.success).length;

    const recommendations = [
      ...(obs.recommended_improvements || []),
    ];
    if (!smtpOk) recommendations.push('SMTP not configured — onboarding emails will not send.');
    if (mem.orphans > 5) recommendations.push('Orphan project spike — run entity linking on historical projects.');
    if (repeated.length) {
      recommendations.push(
        'Repeated failure: ' + (repeated[0].key || repeated[0].suggestion || 'see telemetry')
      );
    }
    if (emailFails) recommendations.push('Email delivery failures in recent telemetry.');
    if (obsVerdict.level === 'warn') recommendations.push('Observability partial — more subsystem traffic needed.');

    const activity = [];
    tel.slice(-20).reverse().forEach((t) => {
      activity.push({
        time: t.observed_at_utc,
        source: 'telemetry',
        label: t.subsystem + '/' + t.event_type,
        detail: t.message || (t.success ? 'ok' : 'failed'),
        ok: t.success,
      });
    });
    (events.events || []).slice(0, 8).forEach((e) => {
      activity.push({
        time: e.when_utc,
        source: 'ledger',
        label: e.event_type || 'event',
        detail: (e.why || e.project_id || '').slice(0, 60),
        ok: true,
      });
    });
    activity.sort((a, b) => (a.time < b.time ? 1 : -1));

    return {
      fetchedAt: new Date().toISOString(),
      healthz,
      ready,
      heal: report,
      obs,
      learning: learn,
      adaptive: adaptive.signals || [],
      telemetry: tel,
      events: events.events || [],
      projects: projects.projects || [],
      mem,
      obsVerdict,
      subsystemCount,
      repeated,
      emailFails,
      acqTel,
      highPriority,
      leadScored,
      discovery,
      adaptiveN,
      smtpOk,
      suggestions,
      telFails,
      recommendations: [...new Set(recommendations)].slice(0, 8),
      activity: activity.slice(0, 18),
      conversionTotal: conversionTotal(learn),
      learningSignals: countLearningSignals(learn),
    };
  }

  function renderCard(root, id, title, stateText, level, lines, wide) {
    const el = root.querySelector('[data-org-card="' + id + '"]');
    if (!el) return;
    const st = el.querySelector('.org-card-state');
    const body = el.querySelector('.org-card-body');
    if (st) {
      st.textContent = stateText;
      st.className = 'org-card-state ' + stateClass(level);
    }
    if (body) {
      body.innerHTML =
        '<ul>' + lines.map((l) => '<li>' + escapeHtml(l) + '</li>').join('') + '</ul>';
    }
    if (wide) el.classList.add('org-card--wide');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function renderFeed(container, rows) {
    if (!container) return;
    if (!rows.length) {
      container.innerHTML = '<div class="org-feed-row"><span class="org-feed-msg">No recent activity yet.</span></div>';
      return;
    }
    container.innerHTML = rows
      .map(
        (r) =>
          '<div class="org-feed-row">' +
          '<span class="org-feed-time">' +
          escapeHtml(fmtTime(r.time)) +
          '</span>' +
          '<span class="org-feed-msg"><strong>' +
          escapeHtml(r.source) +
          '</strong> ' +
          escapeHtml(r.label) +
          '<br><span class="org-feed-time">' +
          escapeHtml(r.detail) +
          '</span></span>' +
          '<span class="org-feed-tag' +
          (r.ok ? '' : ' fail') +
          '">' +
          (r.ok ? 'ok' : 'fail') +
          '</span></div>'
      )
      .join('');
  }

  function renderRecommendations(container, items) {
    if (!container) return;
    if (!items.length) {
      container.innerHTML = '<p class="org-card-body">No adaptive recommendations at this time.</p>';
      return;
    }
    container.innerHTML =
      '<div class="org-rec-list">' +
      items.map((t) => '<div class="org-rec-item">' + escapeHtml(t) + '</div>').join('') +
      '</div>';
  }

  function renderControl(root, snap) {
    const set = (id, val) => {
      const n = root.querySelector('[data-org-metric="' + id + '"]');
      if (n) n.textContent = val;
    };
    set('entities', snap.mem.entities);
    set('orphans', snap.mem.orphans);
    set('observability', snap.obsVerdict.text);
    set('telemetry', snap.telemetry.length);

    renderCard(
      root,
      'memory',
      'Memory integrity',
      snap.mem.summary,
      snap.mem.level,
      snap.mem.lines
    );
    renderCard(
      root,
      'observability',
      'Observability',
      snap.obsVerdict.text,
      snap.obsVerdict.level,
      [
        'Verdict: ' + (snap.obs.verdict || '—'),
        'Subsystems seen: ' + snap.subsystemCount,
        'Repeated failures: ' + snap.repeated.length,
        'Telemetry events loaded: ' + snap.telemetry.length,
      ]
    );
    renderCard(
      root,
      'learning',
      'Learning',
      snap.learningSignals ? 'Active' : 'Idle',
      snap.learningSignals ? 'ok' : 'info',
      [
        'Active signals: ' + snap.learningSignals,
        'Conversion events: ' + snap.conversionTotal,
        'Adaptive signals: ' + snap.adaptiveN,
        'Inquiry→intake: ' + (snap.learning.conversion_counts?.inquiry_to_intake ?? 0),
      ]
    );
    renderCard(
      root,
      'acquisition',
      'Acquisition radar',
      snap.highPriority ? 'Hot leads' : 'Monitoring',
      snap.highPriority ? 'warn' : 'ok',
      [
        'High-priority leads: ' + snap.highPriority,
        'Leads scored (telemetry): ' + snap.leadScored,
        'Discovery events: ' + snap.discovery,
        'Acquisition telemetry rows: ' + snap.acqTel.length,
      ]
    );
    renderCard(
      root,
      'selfheal',
      'Self-heal',
      snap.mem.orphans ? 'Warnings open' : 'Clear',
      snap.mem.orphans ? 'warn' : 'ok',
      [
        'Orphan warnings: ' + snap.mem.orphans,
        'Suggestions written: ' + snap.suggestions,
        'Telemetry failures tracked: ' + (snap.heal.telemetry_failure_count || 0),
        'Duplicate companies: ' + (snap.heal.duplicate_companies || []).length,
      ]
    );
    renderCard(
      root,
      'email',
      'Email transport',
      snap.smtpOk ? 'Configured' : 'Unconfigured',
      snap.smtpOk ? (snap.emailFails ? 'warn' : 'ok') : 'bad',
      [
        'SMTP: ' + (snap.smtpOk ? 'configured' : 'not configured'),
        'Recent send failures: ' + snap.emailFails,
        'Readiness: ' + (snap.ready.status || '—'),
      ]
    );
    renderCard(
      root,
      'telemetry',
      'Telemetry',
      snap.telFails ? 'Failures present' : 'Flowing',
      snap.telFails ? 'warn' : 'ok',
      [
        'Events in window: ' + snap.telemetry.length,
        'Failed events: ' + snap.telFails,
        'Subsystems: ' + snap.subsystemCount,
      ]
    );
    renderFeed(root.querySelector('[data-org-feed="activity"]'), snap.activity);
    renderRecommendations(
      root.querySelector('[data-org-recs="list"]'),
      snap.recommendations
    );

    const pill = root.querySelector('#health');
    if (pill) {
      pill.textContent = snap.healthz.ok ? 'Organism live' : 'Degraded';
      pill.className = snap.healthz.ok
        ? 'kyc-pill kyc-pill--ok'
        : 'kyc-pill kyc-pill--warn';
    }
    const pulse = root.querySelector('#org-pulse-label');
    if (pulse) pulse.textContent = 'Refreshed ' + fmtTime(snap.fetchedAt);
  }

  function renderLearningBars(container, learning) {
    if (!container) return;
    const eff = learning?.signal_effectiveness || {};
    const keys = Object.keys(eff).slice(0, 8);
    if (!keys.length) {
      container.innerHTML = '<p class="org-card-body">No learning signals yet.</p>';
      return;
    }
    const max = Math.max(...keys.map((k) => (eff[k].success || 0) + (eff[k].fail || 0)), 1);
    container.innerHTML =
      '<div class="org-bar">' +
      keys
        .map((k) => {
          const h = Math.round((((eff[k].success || 0) + (eff[k].fail || 0)) / max) * 100));
          return (
            '<span title="' +
            escapeHtml(k) +
            '" style="height:' +
            Math.max(8, h) +
            '%"></span>'
          );
        })
        .join('') +
      '</div><p class="org-metric-foot">' +
      keys.length +
      ' signal keys</p>';
  }

  function renderSubsystemTiles(container, health) {
    if (!container) return;
    const entries = Object.entries(health || {});
    if (!entries.length) {
      container.innerHTML =
        '<p class="org-card-body">No subsystem health data yet — telemetry will populate as engines run.</p>';
      return;
    }
    container.innerHTML = entries
      .map(([name, h]) => {
        const lvl = h.status === 'healthy' ? 'ok' : h.status === 'degraded' ? 'warn' : 'bad';
        return (
          '<div class="kyc-status-tile status-' +
          (lvl === 'ok' ? 'ok' : lvl === 'warn' ? 'warn' : lvl === 'bad' ? 'bad' : 'info') +
          '"><h4>' +
          escapeHtml(name) +
          '</h4><div class="small">Success ' +
          Math.round((h.success_rate || 0) * 100) +
          '% · ' +
          (h.events || 0) +
          ' events · ' +
          (h.failures || 0) +
          ' fails</div></div>'
        );
      })
      .join('');
  }

  function renderMemoryPage(root, snap) {
    renderControl(root, snap);
    renderSubsystemTiles(root.querySelector('[data-org-subsystems]'), snap.obs.subsystem_health);
    renderLearningBars(root.querySelector('[data-org-learning-bars]'), snap.learning);
    const raw = root.querySelector('[data-org-raw-json]');
    if (raw) {
      raw.textContent = JSON.stringify(
        {
          observability: snap.obs.verdict,
          learning: snap.learning,
          self_heal: {
            orphan_projects: (snap.heal.orphan_projects || []).length,
            entity_count: snap.mem.entities,
          },
        },
        null,
        2
      );
    }
  }

  async function refreshControl(root) {
    const snap = await fetchOrganismSnapshot();
    renderControl(root, snap);
    return snap;
  }

  async function refreshMemory(root) {
    const snap = await fetchOrganismSnapshot();
    renderMemoryPage(root, snap);
    return snap;
  }

  global.OrgIntel = {
    api,
    fetchOrganismSnapshot,
    refreshControl,
    refreshMemory,
    renderControl,
    renderMemoryPage,
    observabilityLabel,
    memoryIntegrity,
  };
})(typeof window !== 'undefined' ? window : globalThis);
