/**
 * Contextual Knowledge Overlay — Solo Operator Knowledge Cockpit (embedded in control.html)
 */
(function (global) {
  'use strict';

  var rootEl = null;
  var titleEl = null;
  var bodyEl = null;
  var collapsed = true;
  var autoEnabled = true;

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
    rootEl.querySelector('[data-cko-close]')?.addEventListener('click', collapse);
    rootEl.querySelector('[data-cko-collapse]')?.addEventListener('click', collapse);
  }

  function expand() {
    ensureDom();
    if (!rootEl) return;
    collapsed = false;
    rootEl.classList.remove('cko-overlay--collapsed', 'cko-overlay--peek');
  }

  function collapse() {
    ensureDom();
    if (!rootEl) return;
    collapsed = true;
    rootEl.classList.add('cko-overlay--collapsed');
    rootEl.classList.remove('cko-overlay--peek');
  }

  function peek() {
    ensureDom();
    if (!rootEl) return;
    collapsed = true;
    rootEl.classList.add('cko-overlay--collapsed', 'cko-overlay--peek');
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
    if (titleEl) titleEl.textContent = data.title || 'Contextual Knowledge';
    var html = '';
    html += '<div class="cko-overlay-section"><strong>What am I looking at?</strong><p>' +
      escapeHtml(ov.what_am_i_looking_at || '') + '</p></div>';
    html += '<div class="cko-overlay-section"><strong>Why it matters</strong><p>' +
      escapeHtml(ov.why_it_matters || '') + '</p></div>';
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
    var rel = data.related_concepts || [];
    if (rel.length) {
      html += '<div class="cko-overlay-section"><strong>Related concepts</strong><div class="cko-overlay-terms">';
      rel.slice(0, 6).forEach(function (c) {
        html += '<button type="button" class="cko-term-chip" data-concept-id="' + escapeHtml(c.id || '') + '">' +
          escapeHtml(c.term || c.id) + '</button>';
      });
      html += '</div></div>';
    }
    bodyEl.innerHTML = html;
    bodyEl.querySelectorAll('[data-concept-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cid = btn.getAttribute('data-concept-id');
        if (!cid) return;
        api('/api/operator/knowledge-cockpit/concept/' + encodeURIComponent(cid)).then(function (out) {
          if (!out.ok) return;
          renderOverlay({
            title: out.term || cid,
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
    return api('/api/operator/knowledge-cockpit/overlay', {
      method: 'POST',
      body: JSON.stringify({ view: view, payload: payload || {} }),
    }).then(renderOverlay);
  }

  function showGeneric(text) {
    return show('generic', { text: text || '' });
  }

  function wireRedditQueue(container) {
    if (!container) return;
    var map = global.__redditPendingMap || {};
    container.querySelectorAll('.reddit-approval-card').forEach(function (card) {
      var btn = card.querySelector('.reddit-btn-explain');
      if (!btn) return;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var pid = btn.getAttribute('data-post-id');
        var o = map[pid];
        if (!o) return;
        container.querySelectorAll('.reddit-approval-card').forEach(function (c) {
          c.classList.remove('reddit-approval-card--active');
        });
        card.classList.add('reddit-approval-card--active');
        show('reddit_opportunity', o);
      });
      if (autoEnabled) {
        card.addEventListener('mouseenter', function () {
          if (!collapsed) return;
          peek();
        });
      }
    });
  }

  function wirePanelExplain(panelId, view, payloadFn) {
    var panel = document.getElementById(panelId);
    if (!panel) return;
    panel.addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.classList && t.classList.contains('cko-panel-explain')) {
        e.preventDefault();
        show(view, payloadFn());
      }
    });
  }

  global.KnowledgeOverlay = {
    show: show,
    showGeneric: showGeneric,
    expand: expand,
    collapse: collapse,
    wireRedditQueue: wireRedditQueue,
    setAutoSurface: function (on) { autoEnabled = !!on; },
    render: renderOverlay,
  };

  document.addEventListener('DOMContentLoaded', ensureDom);
})(window);
