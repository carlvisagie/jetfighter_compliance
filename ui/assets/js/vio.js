/* ══════════════════════════════════════════════════════════════════════════════
   VIO — Visual Intelligence Observatory (Level 1: unified-line view)

   Doctrine (see docs/VIO_DOCTRINE.md):
     · Stillness is the baseline. Motion is only for meaningful deviation.
     · One company = one continuous line, top-down sorted by urgency.
     · The LINE encodes everything: stage position, stage state, attention.
     · No pills, no badges, no decoration. Shape is the language.

   Backbone stages (the 7-stage spine every line traces through):
       intake → classification → validation → evidence_mapping
              → review → approval → conversion

   Branch (off evidence_mapping):
       client_followup  (re-enters evidence_mapping when customer replies)
   ══════════════════════════════════════════════════════════════════════════════ */
'use strict';

const SVG_NS = 'http://www.w3.org/2000/svg';

// ── Backbone (must match services/vio_overview.STAGE_BACKBONE) ────────────────
const BACKBONE = [
  { key: 'intake',           label: 'intake' },
  { key: 'classification',   label: 'class.' },
  { key: 'validation',       label: 'valid.' },
  { key: 'evidence_mapping', label: 'evidence' },
  { key: 'review',           label: 'review' },
  { key: 'approval',         label: 'approval' },
  { key: 'conversion',       label: 'conversion' },
];

// ── Layout constants ──────────────────────────────────────────────────────────
const LAYOUT = {
  rowH:        56,    // px — the calm baseline; every trace is one of these
  orbR:        14,    // px
  orbCx:       28,    // px from row left edge
  nameW:       190,   // px reserved for company name
  spineX0:     240,   // px — where the 7-stage spine begins
  spineCY:     28,    // px — vertical centre of the spine in a row
  stageGap:    110,   // px between stage anchors
  livePointR:  6,     // px
  branchDx:    32,    // px the client-followup branch hangs to the right
  branchDy:    18,    // px the client-followup branch drops below the spine
};

function spineEndX() {
  return LAYOUT.spineX0 + (BACKBONE.length - 1) * LAYOUT.stageGap;
}

// ── Stage-state visual lexicon (see CSS for the actual styling) ───────────────
// Each token must map to a real semantic condition; no decoration ever.
const STATE_TOKENS = new Set([
  'healthy', 'stalled', 'failed', 'waiting_client', 'inconsistent', 'done',
]);

// ── In-memory state ───────────────────────────────────────────────────────────
let _allCompanies = [];
let _searchQuery  = '';

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderBackbone();

  const searchEl = document.getElementById('vio-search');
  if (searchEl) {
    let debounce;
    searchEl.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        _searchQuery = (searchEl.value || '').toLowerCase().trim();
        renderTraces();
      }, 150);
    });
  }

  document.getElementById('vio-refresh-btn')?.addEventListener('click', () => {
    const stage = document.getElementById('vio-stage');
    stage?.querySelectorAll('.vio-trace, .vio-empty, .vio-error-state').forEach(e => e.remove());
    if (!stage?.querySelector('#vio-loading')) {
      const loading = document.createElement('div');
      loading.id = 'vio-loading';
      loading.className = 'vio-loading';
      loading.innerHTML = '<div class="vio-loading-orb"></div><span>Refreshing…</span>';
      stage?.appendChild(loading);
    }
    loadVioData();
  });

  document.addEventListener('keydown', e => { if (e.key === 'Escape') hideHoverCard(); });

  loadVioData();
  startAutoRefresh();
});

// ── Render the static stage backbone header ───────────────────────────────────
function renderBackbone() {
  const root = document.getElementById('vio-backbone');
  if (!root) return;
  root.innerHTML = '';

  const totalW = spineEndX() + 80;
  root.style.minWidth = totalW + 'px';

  // Anchored to the same coordinate system as each trace.
  const labels = document.createElement('div');
  labels.className = 'vio-backbone-labels';
  labels.style.paddingLeft = LAYOUT.spineX0 + 'px';
  labels.style.width = (spineEndX() + 80) + 'px';

  BACKBONE.forEach((s, i) => {
    const lbl = document.createElement('span');
    lbl.className = 'vio-backbone-label';
    lbl.style.left = (i * LAYOUT.stageGap) + 'px';
    lbl.textContent = s.label;
    labels.appendChild(lbl);
  });
  root.appendChild(labels);
}

// ── Load data ─────────────────────────────────────────────────────────────────
async function loadVioData() {
  try {
    const resp = await fetch('/api/operator/vio/overview?limit=120', {
      credentials: 'same-origin',
    });
    if (resp.status === 401 || resp.status === 403) {
      window.location.href = '/ui/login.html?next=/ui/vio.html';
      return;
    }
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'API error');

    _allCompanies = data.companies || [];
    renderOrganismStrip(data.organism);
    renderCount(_allCompanies.length);
    renderTraces();

    // First successful render — tear down the defensive boot overlay
    // (see <script> block at the top of ui/vio.html). If we ever
    // forget to call this, the boot watchdog at 10s will paint
    // "VIO did not complete first render" — which is the right
    // failure surface, much better than a silent dark page.
    if (window.VIO_BOOT && typeof window.VIO_BOOT.ready === 'function') {
      window.VIO_BOOT.ready();
    }
  } catch (err) {
    const stage = document.getElementById('vio-stage');
    if (stage) {
      const loading = document.getElementById('vio-loading');
      if (loading) loading.remove();
      const errEl = document.createElement('div');
      errEl.className = 'vio-error-state';
      errEl.innerHTML = `<strong>Field unreadable.</strong><br><span class="vio-error-detail">${err.message}</span>`;
      stage.appendChild(errEl);
    }
    console.error('[VIO]', err);
    if (window.VIO_BOOT && typeof window.VIO_BOOT.fault === 'function') {
      window.VIO_BOOT.fault('loadVioData', err.message || String(err));
    }
  }
}

function renderCount(n) {
  const el = document.getElementById('vio-count');
  if (!el) return;
  el.textContent = `${n} ${n === 1 ? 'company' : 'companies'}`;
}

// ── Auto-refresh (60s, doctrine §5: silent unless something changed) ──────────
function startAutoRefresh() {
  setInterval(async () => {
    try {
      const resp = await fetch('/api/operator/vio/overview?limit=120', { credentials: 'same-origin' });
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data.ok) return;
      _allCompanies = data.companies || [];
      renderOrganismStrip(data.organism);
      renderCount(_allCompanies.length);
      renderTraces();
    } catch (_) { /* silent */ }
  }, 60_000);
}

// ── Render traces ─────────────────────────────────────────────────────────────
function renderTraces() {
  const stage = document.getElementById('vio-stage');
  if (!stage) return;

  document.getElementById('vio-loading')?.remove();
  stage.querySelectorAll('.vio-trace, .vio-empty').forEach(e => e.remove());

  let rows = _allCompanies;
  if (_searchQuery) {
    rows = rows.filter(c =>
      (c.company_name || '').toLowerCase().includes(_searchQuery) ||
      (c.contact_email || '').toLowerCase().includes(_searchQuery)
    );
  }

  if (!rows.length) {
    const empty = document.createElement('div');
    empty.className = 'vio-empty';
    empty.innerHTML = '<div class="vio-empty-mark">◎</div><div>no companies in the field</div>';
    stage.appendChild(empty);
    return;
  }

  // Already urgency-sorted by the backend (descending). Just render.
  rows.forEach((c, idx) => {
    stage.appendChild(buildTrace(c, idx));
  });
}

// ── Build one trace (one company = one continuous line) ───────────────────────
function buildTrace(company, idx) {
  const row = document.createElement('div');
  row.className = 'vio-trace';
  row.setAttribute('data-stage-state', _normalizeState(company.stage_state));
  row.setAttribute('data-stage', company.stage || 'intake');
  row.setAttribute('data-on-branch', String(!!company.on_branch));
  row.style.minWidth = (spineEndX() + 100) + 'px';

  // ── Left: orb + company name (typographic, no badge clutter) ─────────────
  const orbWrap = document.createElement('div');
  orbWrap.className = 'vio-orb-wrap';

  // Doctrine + Carl's sketch: the orb owns the identity. Surface
  // identity facts BOTH on the orb (as a glance-tooltip) and on the
  // adjacent name strip (visible without hover). Operator should know
  // company + email + phone without clicking the row.
  const orb = document.createElement('div');
  orb.className = 'vio-orb';
  orb.setAttribute('data-stage-state', _normalizeState(company.stage_state));
  orb.textContent = company.initials || '?';
  const _identityParts = [
    company.company_name || 'Unknown',
    company.contact_email || '',
    company.contact_phone || '',
  ].filter(Boolean);
  orb.title = _identityParts.join('\n');
  orb.setAttribute('aria-label', _identityParts.join(' · '));
  orbWrap.appendChild(orb);

  const nameWrap = document.createElement('div');
  nameWrap.className = 'vio-name-wrap';

  const nameEl = document.createElement('div');
  nameEl.className = 'vio-name';
  nameEl.textContent = company.company_name || 'Unknown';

  const contactEl = document.createElement('div');
  contactEl.className = 'vio-email';
  const _contactBits = [];
  if (company.contact_email) _contactBits.push(company.contact_email);
  if (company.contact_phone) _contactBits.push(company.contact_phone);
  contactEl.textContent = _contactBits.join(' · ');

  nameWrap.appendChild(nameEl);
  nameWrap.appendChild(contactEl);

  row.appendChild(orbWrap);
  row.appendChild(nameWrap);

  // ── Right: the SVG spine ────────────────────────────────────────────────
  const spine = buildSpine(company);
  row.appendChild(spine);

  // ── Hover / click ───────────────────────────────────────────────────────
  row.addEventListener('mouseenter', e => showHoverCard(e, company));
  row.addEventListener('mousemove',  e => positionHoverCard(e));
  row.addEventListener('mouseleave', hideHoverCard);
  row.addEventListener('click', () => openLevel2(company));

  return row;
}

// ── Build the SVG spine + live point + (optional) client-followup branch ──────
function buildSpine(company) {
  const stageIdx = Math.max(
    0,
    Math.min(BACKBONE.length - 1, company.stage_index ?? 0)
  );
  const liveX = LAYOUT.spineX0 + stageIdx * LAYOUT.stageGap;
  const endX  = spineEndX();

  const svgW = endX + 80;
  const svgH = LAYOUT.rowH;

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'vio-spine');
  svg.setAttribute('width',  svgW);
  svg.setAttribute('height', svgH);
  svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);

  // ── Future segment (faint — what hasn't happened yet) ──
  if (liveX < endX) {
    const futureLine = document.createElementNS(SVG_NS, 'line');
    futureLine.setAttribute('class', 'vio-spine-future');
    futureLine.setAttribute('x1', liveX);
    futureLine.setAttribute('y1', LAYOUT.spineCY);
    futureLine.setAttribute('x2', endX);
    futureLine.setAttribute('y2', LAYOUT.spineCY);
    svg.appendChild(futureLine);
  }

  // ── Past + present segment (the bright, lived part of the trace) ──
  // Doctrine: the line is itself an information surface — thickness and
  // density encode activity intensity, in addition to (not instead of)
  // the shape vocabulary at the live point. `data-activity` is a
  // discrete band (idle | low | normal | high | peak) the CSS reads to
  // pick stroke width and dash density. Stage-age (time since last
  // movement) further dims the line — a quiet line that hasn't been
  // touched in days reads visually as quiet, not just dimmer in colour.
  const pastLine = document.createElementNS(SVG_NS, 'line');
  pastLine.setAttribute('class', 'vio-spine-past');
  pastLine.setAttribute('data-stage-state', _normalizeState(company.stage_state));
  pastLine.setAttribute('data-activity', _activityBand(company));
  pastLine.setAttribute('data-stage-age-band', _stageAgeBand(company));
  pastLine.setAttribute('x1', LAYOUT.spineX0);
  pastLine.setAttribute('y1', LAYOUT.spineCY);
  pastLine.setAttribute('x2', liveX);
  pastLine.setAttribute('y2', LAYOUT.spineCY);
  svg.appendChild(pastLine);

  // ── Stage tick marks (small, faint anchors) ──
  BACKBONE.forEach((_s, i) => {
    const cx = LAYOUT.spineX0 + i * LAYOUT.stageGap;
    const tick = document.createElementNS(SVG_NS, 'circle');
    const past = i <= stageIdx;
    tick.setAttribute('class', past ? 'vio-tick-past' : 'vio-tick-future');
    tick.setAttribute('cx', cx);
    tick.setAttribute('cy', LAYOUT.spineCY);
    tick.setAttribute('r', 2.5);
    svg.appendChild(tick);
  });

  // ── Failed: render a sharp break at the live point (no live circle) ──
  if (company.stage_state === 'failed') {
    drawFailureBreak(svg, liveX, LAYOUT.spineCY);
  } else if (company.stage_state === 'inconsistent') {
    // Small turbulence — three close offset dots at the live point.
    drawTurbulence(svg, liveX, LAYOUT.spineCY);
  } else if (company.on_branch) {
    // Client follow-up branch — gentle perpendicular spur with its own live point.
    drawClientBranch(svg, liveX, LAYOUT.spineCY, company);
  } else {
    // Healthy / stalled / done — single live point, styled via stage_state.
    drawLivePoint(svg, liveX, LAYOUT.spineCY, company);
  }

  return svg;
}

function drawLivePoint(svg, cx, cy, company) {
  // Doctrine §1.4 + Carl's hand sketch: shape is the language. The live
  // point silhouette IS the state — operator reads it without parsing
  // colour. Falls back to a circle for any unknown state.
  //
  //   healthy   → square      (a clean, definite milestone)
  //   stalled   → ▽ triangle  (the sketch's "slow")
  //   done      → ⬢ hexagon   (a peak, dimmed)
  //   <unknown> → circle      (graceful fallback)
  //
  // failed / inconsistent / waiting_client are drawn by dedicated
  // functions elsewhere; only the non-deviation states arrive here.
  const state = _normalizeState(company.stage_state);
  const r = LAYOUT.livePointR;
  let node;
  if (state === 'healthy') {
    node = document.createElementNS(SVG_NS, 'rect');
    const side = r * 1.7;
    node.setAttribute('x', cx - side / 2);
    node.setAttribute('y', cy - side / 2);
    node.setAttribute('width',  side);
    node.setAttribute('height', side);
  } else if (state === 'stalled') {
    node = document.createElementNS(SVG_NS, 'polygon');
    const s = r * 1.9;
    const h = s * 0.866;
    // downward-pointing triangle, base above
    node.setAttribute('points',
      `${cx - s / 2},${cy - h / 2} ${cx + s / 2},${cy - h / 2} ${cx},${cy + h / 2}`);
  } else if (state === 'done') {
    node = document.createElementNS(SVG_NS, 'polygon');
    const s = r * 1.05;
    // pointy-top hexagon
    const pts = [];
    for (let i = 0; i < 6; i++) {
      const ang = -Math.PI / 2 + i * Math.PI / 3;
      pts.push(`${cx + s * Math.cos(ang)},${cy + s * Math.sin(ang)}`);
    }
    node.setAttribute('points', pts.join(' '));
  } else {
    node = document.createElementNS(SVG_NS, 'circle');
    node.setAttribute('cx', cx);
    node.setAttribute('cy', cy);
    node.setAttribute('r', r);
  }
  node.setAttribute('class', 'vio-live');
  node.setAttribute('data-stage-state', state);
  svg.appendChild(node);
}

function drawClientBranch(svg, cx, cy, company) {
  // The spine continues underneath; the branch is a short perpendicular
  // limb that drops to a live point representing the customer wait.
  const bx = cx + LAYOUT.branchDx;
  const by = cy + LAYOUT.branchDy;

  const limb = document.createElementNS(SVG_NS, 'path');
  limb.setAttribute('class', 'vio-branch-limb');
  limb.setAttribute('d', `M ${cx} ${cy} Q ${cx + 4} ${cy + 4}, ${cx + 14} ${cy + 14} T ${bx} ${by}`);
  limb.setAttribute('fill', 'none');
  svg.appendChild(limb);

  const c = document.createElementNS(SVG_NS, 'circle');
  c.setAttribute('class', 'vio-live vio-live-branch');
  c.setAttribute('data-stage-state', 'waiting_client');
  c.setAttribute('cx', bx);
  c.setAttribute('cy', by);
  c.setAttribute('r', LAYOUT.livePointR);
  svg.appendChild(c);

  // small label "client" under the branch tip
  const lbl = document.createElementNS(SVG_NS, 'text');
  lbl.setAttribute('class', 'vio-branch-label');
  lbl.setAttribute('x', bx + 9);
  lbl.setAttribute('y', by + 3);
  lbl.textContent = company.branch_label || 'client';
  svg.appendChild(lbl);
}

function drawFailureBreak(svg, cx, cy) {
  // Doctrine §3 + Carl's sketch: failed is a "sharp ✕ + line breaks" /
  // starburst. Two strong diagonals plus two shorter spokes make the
  // failure point unmistakable at peripheral-vision distance — read in
  // a glance, no colour decoding required.
  const g = document.createElementNS(SVG_NS, 'g');
  g.setAttribute('class', 'vio-failure');
  const long  = 7;
  const short = 4;
  const segs = [
    [-long, -long,  long,  long],   // ╲
    [-long,  long,  long, -long],   // ╱
    [    0, -short,   0,  short],   // │
    [-short,    0, short,    0],    // ─
  ];
  segs.forEach(([x1, y1, x2, y2]) => {
    const l = document.createElementNS(SVG_NS, 'line');
    l.setAttribute('x1', cx + x1); l.setAttribute('y1', cy + y1);
    l.setAttribute('x2', cx + x2); l.setAttribute('y2', cy + y2);
    g.appendChild(l);
  });
  svg.appendChild(g);
}

function drawTurbulence(svg, cx, cy) {
  const g = document.createElementNS(SVG_NS, 'g');
  g.setAttribute('class', 'vio-turbulence');
  [-5, 0, 5].forEach((dx, i) => {
    const d = document.createElementNS(SVG_NS, 'circle');
    d.setAttribute('cx', cx + dx);
    d.setAttribute('cy', cy + (i === 1 ? 0 : (i === 0 ? -2 : 2)));
    d.setAttribute('r', 2);
    g.appendChild(d);
  });
  svg.appendChild(g);
}

function _normalizeState(s) {
  return STATE_TOKENS.has(s) ? s : 'healthy';
}

// Activity band — drives line stroke width / density. Companies with
// many files OR many recent events read as a "thicker" line; quiet
// intakes read as a thinner line. Pure visual encoding — no badge, no
// number on screen.
function _activityBand(company) {
  const files = Number(company.file_count || (company.quick_stats && company.quick_stats.files_uploaded) || 0);
  const attention = (company.attention || []).length;
  const score = files + attention * 2;
  if (score <= 0)   return 'idle';
  if (score <= 2)   return 'low';
  if (score <= 6)   return 'normal';
  if (score <= 12)  return 'high';
  return 'peak';
}

// Stage-age band — drives line opacity / dash. A trace that hasn't moved
// in days physically fades; one that just moved is fully present.
function _stageAgeBand(company) {
  const d = Number(company.days_in_stage || 0);
  if (d < 1)  return 'fresh';
  if (d < 3)  return 'recent';
  if (d < 7)  return 'aging';
  if (d < 14) return 'old';
  return 'ancient';
}

// ── Hover card (Level 1 information surface; no permanent badges) ─────────────
function showHoverCard(e, company) {
  const card = document.getElementById('vio-hover-card');
  if (!card) return;

  const stage = BACKBONE[company.stage_index ?? 0]?.label || 'intake';
  const state = company.stage_state || 'healthy';
  const attention = (company.attention || []).slice(0, 4);

  card.innerHTML = '';

  const titleRow = document.createElement('div');
  titleRow.className = 'vio-hover-title';
  titleRow.textContent = company.company_name || 'Unknown';
  card.appendChild(titleRow);

  if (company.contact_email) {
    const sub = document.createElement('div');
    sub.className = 'vio-hover-sub';
    sub.textContent = company.contact_email;
    card.appendChild(sub);
  }

  const stateRow = document.createElement('div');
  stateRow.className = 'vio-hover-state';
  stateRow.setAttribute('data-stage-state', _normalizeState(state));
  stateRow.textContent = `${stage.toUpperCase()} · ${state.replace(/_/g, ' ')}`;
  card.appendChild(stateRow);

  if (company.days_in_stage != null) {
    const days = document.createElement('div');
    days.className = 'vio-hover-meta';
    days.textContent = `${company.days_in_stage}d in stage`;
    card.appendChild(days);
  }

  if (attention.length) {
    const ul = document.createElement('ul');
    ul.className = 'vio-hover-attention';
    attention.forEach(a => {
      const li = document.createElement('li');
      li.textContent = a;
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }

  const hint = document.createElement('div');
  hint.className = 'vio-hover-hint';
  hint.textContent = 'click to open';
  card.appendChild(hint);

  card.removeAttribute('hidden');
  positionHoverCard(e);
}

function positionHoverCard(e) {
  const card = document.getElementById('vio-hover-card');
  if (!card || card.hasAttribute('hidden')) return;
  const pad = 14;
  const w = card.offsetWidth || 240;
  const h = card.offsetHeight || 80;
  let x = e.clientX + pad;
  let y = e.clientY + pad;
  if (x + w + pad > window.innerWidth)  x = e.clientX - w - pad;
  if (y + h + pad > window.innerHeight) y = e.clientY - h - pad;
  card.style.left = `${Math.max(pad, x)}px`;
  card.style.top  = `${Math.max(pad, y)}px`;
}

function hideHoverCard() {
  document.getElementById('vio-hover-card')?.setAttribute('hidden', '');
}

// ── Level 2 hand-off (the visual landscape lives in vio-level2.js) ───────────
function openLevel2(company) {
  hideHoverCard();
  if (window.VioLevel2 && typeof window.VioLevel2.open === 'function') {
    window.VioLevel2.open(company);
  } else {
    // Defensive fallback if vio-level2.js failed to load — never silently
    // break the click.
    console.error('[VIO] Level 2 module not available');
  }
}

// ── Organism awareness strip (calm baseline; only speaks on deviation) ────────
const ORG_COLORS = { GREEN: 'green', AMBER: 'amber', RED: 'red', UNKNOWN: 'unknown' };

function renderOrganismStrip(org) {
  const pill   = document.getElementById('vio-org-pill');
  const bottle = document.getElementById('vio-org-bottleneck');
  const action = document.getElementById('vio-org-action');
  const meta   = document.getElementById('vio-org-meta');
  const strip  = document.getElementById('vio-organism-strip');
  if (!pill || !bottle || !action || !meta) return;

  if (!org || !org.available) {
    pill.textContent = '?';
    pill.setAttribute('data-state', 'unknown');
    bottle.textContent = org?.error ? `organism layer: ${org.error}` : 'organism state unavailable';
    action.textContent = '';
    meta.textContent = '';
    if (strip) { strip.style.cursor = 'default'; strip.onclick = null; }
    return;
  }

  const health = (org.health_state || 'UNKNOWN').toUpperCase();
  pill.textContent = health[0]; // single letter — minimum noise
  pill.setAttribute('data-state', (ORG_COLORS[health] || 'unknown'));
  pill.title = health;

  bottle.textContent = org.current_bottleneck || 'no active bottleneck';
  action.textContent = org.next_recommended_action ? `→ ${org.next_recommended_action}` : '';

  const metaParts = [
    `q=${org.queue_depth}`,
    `intakes=${org.intake_count_active}/${org.intake_count_total}`,
    `files=${org.uploaded_file_count}`,
    org.mismatch_count ? `mismatches=${org.mismatch_count}` : '',
    org.environment || '',
    org.git_commit ? `git=${org.git_commit}` : '',
  ].filter(Boolean);
  meta.textContent = metaParts.join(' · ');
  meta.title = org.timestamp_utc ? `snapshot: ${org.timestamp_utc}` : '';

  // Strip is clickable only when there's something to show.
  if (strip) {
    if ((org.mismatch_count || 0) > 0) {
      strip.style.cursor = 'pointer';
      strip.onclick = () => alert(
        (org.mismatches || [])
          .map(m => `[${m.severity?.toUpperCase() || 'AMBER'}] ${m.name}\n${m.detail || ''}`)
          .join('\n\n')
      );
    } else {
      strip.style.cursor = 'default';
      strip.onclick = null;
    }
  }
}
