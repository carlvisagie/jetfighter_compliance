/**
 * Cockpit founding-pilot visibility — banner, atlas summary, organism pulse.
 */
(function (global) {
  'use strict';

  var state = {
    queue: null,
    pending: 0,
    urgent: 0,
    integrityMismatch: 0,
    latest: null,
    error: null,
    visibility_warning: null,
    retention_critical: null,
    diagnostics: null,
    storage: null,
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

  function updateStorageCriticalBanner() {
    var el = document.getElementById('fb-storage-critical-banner');
    if (!el) return;
    var s = state.storage;
    if (!s || s.intake_uploads_enabled) {
      el.hidden = true;
      el.classList.add('fb-storage-critical-banner--hidden');
      return;
    }
    el.hidden = false;
    el.classList.remove('fb-storage-critical-banner--hidden');
    el.className = 'fb-storage-critical-banner';
    el.innerHTML =
      '<strong>Durable paperwork storage not configured — uploads disabled.</strong>' +
      '<span class="fb-storage-critical-banner__detail">' +
      escapeHtml(s.operator_message || s.upload_block_reason || 'Set KYC_DATA on persistent disk.') +
      '</span>';
  }

  function updateIntegrityBanner() {
    var el = document.getElementById('fb-integrity-banner');
    if (!el) return;
    var n = int(state.integrityMismatch || 0);
    if (n <= 0) {
      el.hidden = true;
      el.classList.add('fb-integrity-banner--hidden');
      return;
    }
    el.hidden = false;
    el.classList.remove('fb-integrity-banner--hidden');
    el.innerHTML =
      '<strong>Upload integrity mismatch detected</strong>' +
      '<span class="fb-integrity-banner__detail">' +
      n +
      ' intake(s) have expected/received/verified file count drift — review immediately.</span>' +
      '<button type="button" class="kyc-btn kyc-btn--secondary fb-paperwork-banner__btn" id="fbIntegrityReview">Review queue</button>';
    document.getElementById('fbIntegrityReview')?.addEventListener('click', scrollToQueue);
  }

  function updateBanner() {
    var banner = document.getElementById('fb-paperwork-banner');
    if (!banner) return;
    if (state.storage && !state.storage.intake_uploads_enabled) {
      setVisible(banner, false);
      return;
    }
    if (state.error) {
      setVisible(banner, true);
      banner.className = 'fb-paperwork-banner fb-paperwork-banner--warn';
      banner.innerHTML =
        '<strong>Founding pilot queue unavailable</strong>' +
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
    state.integrityMismatch = int(q.integrity_mismatch_count || 0);
    state.latest = (q.queue && q.queue[0]) || null;
    state.visibility_warning = q.visibility_warning || null;
    state.diagnostics = q.diagnostics || null;
    updateIntegrityBanner();
    updateBanner();
    updateAtlas();
    updateOrgPulse();
    updateVisibilityWarning();
    document.dispatchEvent(
      new CustomEvent('cockpit-intake-updated', { detail: { state: state } })
    );
  }

  function int(n) {
    return parseInt(n, 10) || 0;
  }

  function applyError(err) {
    state.error = err;
    state.pending = 0;
    state.urgent = 0;
    state.integrityMismatch = 0;
    state.latest = null;
    state.visibility_warning = null;
    updateIntegrityBanner();
    updateBanner();
    updateAtlas();
    updateVisibilityWarning();
  }

  function updateRetentionCriticalBanner() {
    var el = document.getElementById('fb-retention-critical-banner');
    if (!el) return;
    var msg = state.retention_critical;
    if (!msg) {
      el.hidden = true;
      el.classList.add('fb-storage-critical-banner--hidden');
      return;
    }
    el.hidden = false;
    el.classList.remove('fb-storage-critical-banner--hidden');
    el.className = 'fb-storage-critical-banner';
    el.innerHTML =
      '<strong>CRITICAL — intake retention risk</strong>' +
      '<span class="fb-storage-critical-banner__detail">' +
      escapeHtml(msg) +
      '</span>';
  }

  function computeRetentionCritical() {
    var parts = [];
    var d = state.diagnostics || {};
    var scan = d.retention_scan || {};
    if (scan.index_disk_agree === false) {
      var od = (scan.only_on_disk_not_in_index || []).length;
      var oi = (scan.only_in_index_not_on_disk || []).length;
      if (od || oi) {
        parts.push(
          'Index and disk disagree (' +
            od +
            ' on disk only, ' +
            oi +
            ' in index only). Filesystem is source of truth — reconcile immediately.'
        );
      }
    }
    if (d.roots_match === false) {
      parts.push('Write root and read root do not match — uploads and queue may diverge.');
    }
    var dirs = int(d.intake_directories_found || scan.intake_directories || 0);
    var files = int(d.upload_files_on_disk || scan.upload_files || 0);
    if (dirs > 0 && state.pending <= 0 && files > 0) {
      parts.push(
        dirs +
          ' intake(s) and ' +
          files +
          ' file(s) on durable disk but operator queue shows empty.'
      );
    }
    if (
      state.storage &&
      state.storage.intake_uploads_enabled &&
      state.storage.durable_storage_configured &&
      dirs > 0 &&
      state.pending <= 0 &&
      !state.error
    ) {
      var uph = state.queue && state.queue.uploads_per_hour_estimate;
      if (uph > 0 || files > 0) {
        parts.push(
          'Durable storage is configured but no pending paperwork is visible after recent upload activity.'
        );
      }
    }
    state.retention_critical = parts.length ? parts.join(' ') : null;
    updateRetentionCriticalBanner();
  }

  function updateVisibilityWarning() {
    var box = document.getElementById('fb-visibility-warning');
    if (!box) return;
    computeRetentionCritical();
    if (state.retention_critical) {
      box.hidden = false;
      box.className = 'fb-visibility-warning fb-visibility-warning--critical';
      box.innerHTML =
        '<strong>Retention alert</strong><p>' + escapeHtml(state.retention_critical) + '</p>';
      return;
    }
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

  function applyDiagnosticsResponse(d) {
    if (!d) return;
    state.diagnostics = d.diagnostics || d;
    computeRetentionCritical();
    updateVisibilityWarning();
  }

  function updateEvidenceIntegrityPanel(proof) {
    var el = document.getElementById('evidence-integrity-status');
    if (!el) return;
    if (!proof) {
      el.innerHTML = '<p class="fb-queue-atlas__warn">Evidence proof unavailable.</p>';
      return;
    }
    var ok = proof.ok === true;
    el.className = 'fb-queue-atlas' + (ok ? '' : ' fb-queue-atlas--warn');
    var indicator = ok
      ? '<span style="color:#64dc9e">● GREEN</span>'
      : '<span style="color:#ff7864">● NOT OK</span>';
    el.innerHTML =
      '<div class="fb-queue-atlas__grid">' +
      '<div><span class="kyc-metric-label">Status</span><strong>' +
      indicator +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Registered</span><strong>' +
      int(proof.registered_files || proof.total_files || 0) +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Verified</span><strong>' +
      int(proof.verified_files || 0) +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Missing</span><strong>' +
      int(proof.missing_files || 0) +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Recovered</span><strong>' +
      int(proof.recovered_files || 0) +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Corrupted</span><strong>' +
      int(proof.corrupt_files || 0) +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Pending</span><strong>' +
      int(proof.pending_files || 0) +
      '</strong></div>' +
      '<div><span class="kyc-metric-label">Orphaned</span><strong>' +
      int(proof.orphaned_files || 0) +
      '</strong></div>' +
      '</div>' +
      (ok
        ? ''
        : '<p class="fb-queue-atlas__warn">Integrity problems detected — review reconcile and queue.</p>');
  }

  function refreshEvidenceProof(apiFn) {
    return apiFn('/api/operator/integrity/proof')
      .then(function (proof) {
        updateEvidenceIntegrityPanel(proof);
        if (!proof.ok) {
          var banner = document.getElementById('fb-integrity-banner');
          if (banner) {
            banner.hidden = false;
            banner.classList.remove('fb-integrity-banner--hidden');
            banner.innerHTML =
              '<strong>Evidence integrity proof failed</strong>' +
              '<span class="fb-integrity-banner__detail">' +
              'missing=' +
              int(proof.missing_files || 0) +
              ' orphaned=' +
              int(proof.orphaned_files || 0) +
              ' corrupt=' +
              int(proof.corrupt_files || 0) +
              '</span>';
          }
        }
        return proof;
      })
      .catch(function () {
        updateEvidenceIntegrityPanel(null);
      });
  }

  function scrollToQueue() {
    var el = document.getElementById('intake-panel');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.classList.add('fb-queue-panel--highlight');
      window.setTimeout(function () {
        el.classList.remove('fb-queue-panel--highlight');
      }, 2200);
    }
  }

  function refreshStorage(apiFn) {
    return apiFn('/api/operator/storage-status')
      .then(function (s) {
        state.storage = s;
        updateStorageCriticalBanner();
        updateBanner();
        return s;
      })
      .catch(function () {
        state.storage = null;
        updateStorageCriticalBanner();
      });
  }

  function refresh(apiFn) {
    return Promise.all([
      refreshStorage(apiFn),
      apiFn('/api/operator/intake/diagnostics')
        .then(function (d) {
          applyDiagnosticsResponse(d);
          return d;
        })
        .catch(function () {}),
      apiFn('/api/operator/intake/queue')
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
        }),
      refreshEvidenceProof(apiFn),
    ]).then(function (results) {
      return results[2];
    });
  }

  var _evidenceProofTimer = null;
  function startEvidenceProofPolling(apiFn) {
    if (_evidenceProofTimer) return;
    _evidenceProofTimer = window.setInterval(function () {
      refreshEvidenceProof(apiFn);
    }, 30000);
  }

  global.CockpitFoundingPilot = {
    refresh: refresh,
    refreshStorage: refreshStorage,
    refreshEvidenceProof: refreshEvidenceProof,
    startEvidenceProofPolling: startEvidenceProofPolling,
    getState: function () {
      return state;
    },
    applyQueueResponse: applyQueueResponse,
    scrollToQueue: scrollToQueue,
    updateOrgPulse: updateOrgPulse,
  };
})(typeof window !== 'undefined' ? window : globalThis);
