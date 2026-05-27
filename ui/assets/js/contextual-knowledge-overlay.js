/**
 * Contextual Knowledge Overlay — automatic cockpit-native mentor (control.html).
 */
(function (global) {
  'use strict';

  var rootEl = null;
  var titleEl = null;
  var bodyEl = null;
  var statusEl = null;
  var collapsed = false;
  var userPinned = false;
  var panelSnapshots = {};
  var activePanelId = null;
  var selectedReddit = null;
  var explainTimer = null;
  var lastRequestKey = '';

  var PANEL_VIEWS = {
    priority: 'cockpit_guidance',
    bottlenecks: 'cockpit_guidance',
    attention: 'cockpit_guidance',
    organism: 'cockpit_guidance',
    learn: 'cockpit_guidance',
    friction: 'friction_panel',
    evidence: 'evidence_panel',
    acquisition: 'acquisition_panel',
    reddit: 'reddit_panel',
    alerts: 'alerts_panel',
    compliance: 'compliance_panel',
    knowledge: 'generic',
    telemetry: 'telemetry_panel',
    'command-strip': 'cockpit_guidance',
  };

  function api(path, opts) {
    opts = opts || {};
    opts.credentials = 'same-origin';
    opts.headers = opts.headers || {};
    if (opts.body && !opts.headers['Content-Type']) {
      opts.headers['Content-Type'] = 'application/json';
    }
    return fetch(path, opts).then(function (r) {
      if (!r.ok) throw new Error(r.statusText || String(r.status));
      return r.json();
    });
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function ensureDom() {
    if (rootEl) return;
    rootEl = document.getElementById('contextual-knowledge-overlay');
    if (!rootEl) return;
    titleEl = rootEl.querySelector('[data-cko-title]');
    bodyEl = rootEl.querySelector('[data-cko-body]');
    statusEl = rootEl.querySelector('[data-cko-status]');
    rootEl.querySelector('[data-cko-close]')?.addEventListener('click', function () {
      userPinned = false;
      collapse();
    });
    rootEl.querySelector('[data-cko-collapse]')?.addEventListener('click', function () {
      userPinned = false;
      collapse();
    });
    document.getElementById('ckoToggleBtn')?.addEventListener('click', function () {
      userPinned = true;
      if (collapsed) {
        explainActive(true);
      } else {
        collapse();
      }
    });
  }

  function expand() {
    ensureDom();
    if (!rootEl) return;
    collapsed = false;
    rootEl.classList.remove('cko-overlay--collapsed');
  }

  function collapse() {
    ensureDom();
    if (!rootEl) return;
    collapsed = true;
    rootEl.classList.add('cko-overlay--collapsed');
    postOverlayTelemetry('overlay_collapsed', { view: activePanelId || '' });
  }

  function postOverlayTelemetry(eventType, meta) {
    try {
      fetch('/api/operator/knowledge-cockpit/telemetry', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: eventType,
          view: (meta && meta.view) || activePanelId || '',
          concept_id: (meta && meta.concept_id) || '',
          metadata: meta || {},
        }),
      }).catch(function () {});
    } catch (_) {}
  }

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text || '';
  }

  function renderList(items) {
    if (!items || !items.length) return '<p class="org-metric-foot">—</p>';
    return '<ul class="guidance-list">' + items.map(function (x) {
      return '<li>' + escapeHtml(String(x)) + '</li>';
    }).join('') + '</ul>';
  }

  function renderOverlay(data) {
    ensureDom();
    if (!bodyEl) return;
    var ov = (data && data.overlay) || {};
    if (titleEl) titleEl.textContent = data.title || 'Contextual mentor';
    setStatus(data.view ? data.view.replace(/_/g, ' ') : '');
    var html = '';
    html += '<div class="cko-overlay-section"><strong>What am I looking at?</strong><p>' +
      escapeHtml(ov.what_am_i_looking_at || '') + '</p></div>';
    html += '<div class="cko-overlay-section"><strong>Why it matters</strong><p>' +
      escapeHtml(ov.why_it_matters || '') + '</p></div>';
    var goodBad = ov.what_is_good_or_bad || [];
    if (goodBad.length) {
      html += '<div class="cko-overlay-section"><strong>Good / bad here</strong>' + renderList(goodBad) + '</div>';
    }
    var terms = ov.what_terms_mean || [];
    if (terms.length) {
      html += '<div class="cko-overlay-section"><strong>Terms</strong><div class="cko-overlay-terms">';
      terms.forEach(function (t) {
        var id = t.id || '';
        var label = t.term || t.hint || id;
        if (id) {
          html += '<button type="button" class="cko-term-chip" data-concept-id="' + escapeHtml(id) + '">' +
            escapeHtml(label) + '</button>';
        } else {
          html += '<span class="cko-term-chip">' + escapeHtml(label) + '</span>';
        }
      });
      html += '</div></div>';
    }
    if (data.plain_english) {
      html += '<div class="cko-overlay-section"><strong>Plain English</strong><p>' +
        escapeHtml(data.plain_english) + '</p></div>';
    }
    html += '<div class="cko-overlay-section"><strong>Watch for</strong>' + renderList(ov.what_to_watch_for) + '</div>';
    html += '<div class="cko-overlay-section"><strong>Do next</strong>' + renderList(ov.what_to_do_next) + '</div>';
    bodyEl.innerHTML = html;
    bodyEl.querySelectorAll('[data-concept-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cid = btn.getAttribute('data-concept-id');
        if (!cid) return;
        postOverlayTelemetry('concept_lookup', { concept_id: cid, view: 'concept' });
        postOverlayTelemetry('related_concepts_opened', { concept_id: cid });
        api('/api/operator/knowledge-cockpit/concept/' + encodeURIComponent(cid)).then(function (out) {
          if (!out.ok) return;
          renderOverlay({
            title: out.term || cid,
            view: 'concept',
            overlay: {
              what_am_i_looking_at: out.term,
              why_it_matters: out.why_it_matters || '',
              what_terms_mean: (out.related_concepts || []).map(function (r) {
                return { term: r.term, id: r.id };
              }),
              what_to_watch_for: out.common_mistakes || [],
              what_to_do_next: (out.evidence_examples || []).slice(0, 3),
            },
            related_concepts: out.related_concepts,
          });
        });
      });
    });
    expand();
  }

  function show(view, payload) {
    var key = view + ':' + JSON.stringify(payload || {}).slice(0, 200);
    if (key === lastRequestKey && !userPinned) return Promise.resolve();
    lastRequestKey = key;
    setStatus('Updating…');
    return api('/api/operator/knowledge-cockpit/overlay', {
      method: 'POST',
      body: JSON.stringify({ view: view, payload: payload || {} }),
    }).then(function (data) {
      renderOverlay(data);
      postOverlayTelemetry('overlay_opened', { view: view, panel: (payload && payload.panel) || '' });
      return data;
    }).catch(function () {
      setStatus('Explain unavailable');
      postOverlayTelemetry('overlay_failure', { view: view });
    });
  }

  function buildPayload(panelId) {
    var snap = panelSnapshots[panelId] || {};
    if (panelId === 'reddit' && selectedReddit) {
      return { view: 'reddit_opportunity', payload: selectedReddit };
    }
    if (panelId === 'reddit') {
      return {
        view: 'reddit_panel',
        payload: Object.assign({}, snap, {
          pending_count: (snap.pending_opportunities || []).length,
          selected_opportunity: selectedReddit,
        }),
      };
    }
    var view = PANEL_VIEWS[panelId] || 'generic';
    var payload = Object.assign({ panel: panelId }, snap);
    if (panelId === 'priority' || panelId === 'bottlenecks' || panelId === 'attention' || panelId === 'organism' || panelId === 'learn') {
      payload.panel = panelId;
    }
    return { view: view, payload: payload };
  }

  function explainActive(force) {
    if (!activePanelId && !force) return;
    if (explainTimer) clearTimeout(explainTimer);
    explainTimer = setTimeout(function () {
      var spec = buildPayload(activePanelId || 'priority');
      show(spec.view, spec.payload);
    }, force ? 0 : 350);
  }

  function setActivePanel(panelId, opts) {
    opts = opts || {};
    if (!panelId) return;
    activePanelId = panelId;
    document.querySelectorAll('[data-cko-panel]').forEach(function (el) {
      el.classList.toggle('cko-panel-active', el.getAttribute('data-cko-panel') === panelId);
    });
    if (opts.immediate) explainActive(true);
  }

  function setPanelSnapshot(panelId, data) {
    panelSnapshots[panelId] = data || {};
    if (activePanelId === panelId) explainActive(true);
  }

  function selectRedditOpportunity(o, cardEl) {
    selectedReddit = o || null;
    document.querySelectorAll('.reddit-approval-card').forEach(function (c) {
      c.classList.remove('reddit-approval-card--active');
    });
    if (cardEl) cardEl.classList.add('reddit-approval-card--active');
    if (activePanelId === 'reddit' || !activePanelId) {
      setActivePanel('reddit', { immediate: true });
    } else {
      explainActive(true);
    }
  }

  function wireRedditQueue(container) {
    if (!container) return;
    var map = global.__redditPendingMap || {};
    container.querySelectorAll('.reddit-approval-card').forEach(function (card) {
      var pid = card.getAttribute('data-post-id');
      var o = map[pid];
      if (!o) return;
      function activate() {
        selectRedditOpportunity(o, card);
      }
      card.setAttribute('tabindex', '0');
      card.addEventListener('click', function (e) {
        if (e.target.closest('button, a')) return;
        activate();
      });
      card.addEventListener('focusin', activate);
    });
    if (!selectedReddit && Object.keys(map).length) {
      var first = container.querySelector('.reddit-approval-card');
      if (first) selectRedditOpportunity(map[first.getAttribute('data-post-id')], first);
    }
  }

  function initAuto(opts) {
    ensureDom();
    opts = opts || {};
    var root = document.querySelector(opts.rootSelector || '#guidance-panels');
    var observeRoot = document.querySelector(opts.observeRoot || 'main') || document.body;
    if (!root) return;

    var panels = document.querySelectorAll('[data-cko-panel]');
    if (!panels.length) return;

    var ratios = {};
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          var id = entry.target.getAttribute('data-cko-panel');
          if (!id) return;
          ratios[id] = entry.isIntersecting ? entry.intersectionRatio : 0;
        });
        var bestId = null;
        var bestRatio = 0;
        Object.keys(ratios).forEach(function (id) {
          if (ratios[id] > bestRatio) {
            bestRatio = ratios[id];
            bestId = id;
          }
        });
        if (bestId && bestRatio >= 0.2) {
          setActivePanel(bestId);
          if (!collapsed) explainActive();
        }
      },
      { root: null, rootMargin: '-10% 0px -35% 0px', threshold: [0, 0.15, 0.35, 0.55, 0.75] }
    );

    panels.forEach(function (el) {
      observer.observe(el);
    });

    var health = document.getElementById('organism-health');
    if (health) observer.observe(health);

    setActivePanel('priority', { immediate: true });
    expand();
  }

  global.KnowledgeOverlay = {
    show: show,
    expand: expand,
    collapse: collapse,
    render: renderOverlay,
    setPanelSnapshot: setPanelSnapshot,
    setActivePanel: setActivePanel,
    selectRedditOpportunity: selectRedditOpportunity,
    wireRedditQueue: wireRedditQueue,
    initAuto: initAuto,
    explainActive: explainActive,
  };

  document.addEventListener('DOMContentLoaded', ensureDom);
})(window);
