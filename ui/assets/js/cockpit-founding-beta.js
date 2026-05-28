/**
 * Cockpit founding-beta visibility — banner, atlas summary, organism pulse.
 */
(function (global) {
  'use strict';

  var state = {
    queue: null,
    pending: 0,
    urgent: 0,
    latest: null,
    error: null,
    visibility_warning: null,
    diagnostics: null,
  };

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function setVisible(el, on) {
    if (!el) return;
    el.hidden = !on;
    el.classList.toggle('fb-paperwork-banner--hidden', !on);
    el.classList.toggle('fb-queue-atlas--hidden', !on);
  }

  function updateBanner() {
    var banner = document.getElementById('fb-paperwork-banner');
    if (!banner) return;
    if (state.error) {
      setVisible(banner, true);
      banner.className = 'fb-paperwork-banner fb-paperwork-banner--warn';
      banner.innerHTML =
        '<strong>Founding beta queue unavailable</strong>' +
        '<span class="fb-paperwork-banner__detail">' +
        escapeHtml(state.error.message || String(state.error)) +
        '</span>' +
        '<button type="button" class="kyc-btn kyc-btn--secondary fb-paperwork-banner__btn" id="fbBannerRetry">Retry</button>';
      return;
    }
    if (state.pending <= 0) {
      setVisible(banner, false);
      return;
    }
    banner.className =
      'fb-paperwork-banner' + (state.urgent > 0 ? ' fb-paperwork-banner--urgent' : '');
    var latest = state.latest || {};
    var types = (latest.file_types || []).join(', ') || (latest.classified_file_types || []).join(', ') || '—';
    banner.innerHTML =
      '<div class="fb-paperwork-banner__inner">' +
      '<span class="fb-paperwork-banner__tag" aria-hidden="true">●</span>' +
      '<div class="fb-paperwork-banner__copy">' +
      '<strong>NEW PAPERWORK RECEIVED</strong>' +
      '<span class="fb-paperwork-banner__detail">' +
      escapeHtml(latest.intake_id || 'Pending intake') +
      ' · ' +
      (latest.file_count || 0) +
      ' file(s) · ' +
      escapeHtml(types) +
      (state.urgent > 0 ? ' · <em class="fb-paperwork-banner__urgent">urgent</em>' : '') +
      '</span></div>' +
      '<button type="button" class="kyc-btn kyc-btn--primary fb-paperwork-banner__btn" id="fbBannerReview">Review latest paperwork</button>' +
      '</div>';
    setVisible(banner, true);
    document.getElementById('fbBannerReview')?.addEventListener('click', scrollToQueue);
  }

  function updateAtlas() {
    var atlas = document.getElementById('fb-queue-atlas');
    if (!atlas) return;
    if (state.error) {
      setVisible(atlas, true);
      atlas.className = 'fb-queue-atlas fb-queue-atlas--warn';
      atlas.innerHTML =
        '<p class="fb-queue-atlas__warn"><strong>Queue load failed.</strong> ' +
        escapeHtml(state.error.message || 'Check session and retry.') +
        '</p>';
      return;
    }
    if (state.pending <= 0) {
      setVisible(atlas, false);
      return;
    }
    var latest = state.latest || {};
    var types = (latest.file_types || []).join(', ') || '—';
    var clf = (latest.classified_file_types || []).join(', ') || latest.primary_category || '—';
    atlas.className = 'fb-queue-atlas';
    atlas.innerHTML =
      '<div class="fb-queue-atlas__grid">' +
      '<div><span class="kyc-metric-label">Pending reviews</span><strong>' +
      state.pending +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Newest intake</span><code>' +
      escapeHtml(latest.intake_id || '—') +
      '</code></div>' +
      '<div><span class="kyc-metric-label">Files</span><strong>' +
      (latest.file_count || 0) +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Types</span><span>' +
      escapeHtml(types) +
      '</span></div>' +
      '<div><span class="kyc-metric-label">Classified</span><span>' +
      escapeHtml(clf) +
      '</span></div>' +
      '<div><span class="kyc-metric-label">Received</span><span>' +
      escapeHtml(latest.created_utc || '—') +
      '</span></div>' +
      '</div>' +
      '<button type="button" class="kyc-btn kyc-btn--primary" id="fbAtlasReview">Review latest paperwork</button>';
    setVisible(atlas, true);
    document.getElementById('fbAtlasReview')?.addEventListener('click', scrollToQueue);
  }

  function updateOrgPulse() {
    var pulse = document.getElementById('org-pulse-label');
    if (!pulse || state.error) return;
    if (state.pending > 0) {
      pulse.textContent =
        state.pending === 1
          ? '1 paperwork review pending'
          : state.pending + ' paperwork reviews pending';
      if (state.urgent > 0) {
        pulse.textContent += ' (' + state.urgent + ' urgent)';
      }
    }
  }

  function applyQueueResponse(q) {
    state.queue = q;
    state.error = null;
    state.pending = int(q.queue_depth || 0);
    state.urgent = int(q.urgent_count || 0);
    state.latest = (q.queue && q.queue[0]) || null;
    state.visibility_warning = q.visibility_warning || null;
    state.diagnostics = q.diagnostics || null;
    updateBanner();
    updateAtlas();
    updateOrgPulse();
    updateVisibilityWarning();
    document.dispatchEvent(
      new CustomEvent('cockpit-founding-beta-updated', { detail: { state: state } })
    );
  }

  function int(n) {
    return parseInt(n, 10) || 0;
  }

  function applyError(err) {
    state.error = err;
    state.pending = 0;
    state.urgent = 0;
    state.latest = null;
    state.visibility_warning = null;
    updateBanner();
    updateAtlas();
    updateVisibilityWarning();
  }

  function updateVisibilityWarning() {
    var box = document.getElementById('fb-visibility-warning');
    if (!box) return;
    if (state.visibility_warning) {
      box.hidden = false;
      box.className = 'fb-visibility-warning';
      box.innerHTML =
        '<strong>Paperwork visibility mismatch</strong><p>' +
        escapeHtml(state.visibility_warning) +
        '</p>';
      return;
    }
    if (state.diagnostics && state.pending <= 0) {
      var dirs = int(state.diagnostics.intake_directories_found);
      var files = int(state.diagnostics.upload_files_on_disk);
      if (dirs > 0 || files > 0) {
        box.hidden = false;
        box.className = 'fb-visibility-warning';
        box.innerHTML =
          '<strong>Intake data on disk but queue empty</strong><p>' +
          escapeHtml(
            dirs +
              ' intake folder(s), ' +
              files +
              ' file(s) under ' +
              (state.diagnostics.intakes_root || 'data path') +
              ' — reload or check operator session.'
          ) +
          '</p>';
        return;
      }
    }
    box.hidden = true;
    box.textContent = '';
  }

  function scrollToQueue() {
    var el = document.getElementById('founding-beta-intake-panel');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.classList.add('fb-queue-panel--highlight');
      window.setTimeout(function () {
        el.classList.remove('fb-queue-panel--highlight');
      }, 2200);
    }
  }

  function refresh(apiFn) {
    return apiFn('/api/operator/founding-beta/queue')
      .then(function (q) {
        if (!q || q.ok === false) {
          throw new Error((q && q.detail) || 'Queue response not ok');
        }
        applyQueueResponse(q);
        return q;
      })
      .catch(function (err) {
        applyError(err);
        throw err;
      });
  }

  global.CockpitFoundingBeta = {
    refresh: refresh,
    getState: function () {
      return state;
    },
    applyQueueResponse: applyQueueResponse,
    scrollToQueue: scrollToQueue,
    updateOrgPulse: updateOrgPulse,
  };
})(typeof window !== 'undefined' ? window : globalThis);
