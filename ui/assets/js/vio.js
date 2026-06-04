/* ══════════════════════════════════════════════════════════════════════════════
   VIO — Visual Intelligence Observatory (Level 1: sketch-faithful spine)

   Source of truth: docs/VIO_SOURCE_BRIEF.md  +  docs/assets/vio_sketch.jpeg
                    docs/VIO_CONSTITUTION.md  +  docs/VIO_DOCTRINE.md

   The core model (Carl Visagie's hand sketch):

       ●━━━□━━━━━⬢━━━━━○━━━━━○━━━━━✱
       ↑    ↑       ↑       ↑       ↑
       │  intake   phase  milestone broken
     identity     complete
       orb
                 (▲ issues / pace markers hang BELOW the spine)

   · The company IS the interface object — one company = one row, one spine.
   · The spine is a TIMELINE (not a fixed stage bar). Events hang on it at
     the temporal position they happened.
   · Shape vocabulary (brief §5):
       □ square     = intake / a document arrived
       ⬢ hexagon    = phase completion
       ○ circle     = milestone reached  (or waiting/confirmation)
       ▲ triangle   = an issue
       ◇ diamond    = a decision (payment, approval)
       ✱ starburst  = broken / blocker
   · Color (brief §5):
       green = healthy/complete  ·  amber = attention  ·  red = blocked
       blue  = information       ·  grey  = inactive/not started
   · Motion: pulse/glow only when actively waiting/urgent. Stillness is calm.

   Data source: backend `services/vio_overview.py:_build_timeline` already
   produces the per-company event list. This renderer maps event types to
   sketch shapes and hangs them on each company's spine.
   ══════════════════════════════════════════════════════════════════════════════ */
'use strict';

const SVG_NS = 'http://www.w3.org/2000/svg';

// ── Sketch geometry ───────────────────────────────────────────────────────────
// The spine is a continuous timeline. The identity orb sits on the LEFT and
// IS the start of the spine (the sketch shows it integrated, not in a
// sidebar). The spine extends to the right; events hang on it at evenly-
// spaced positions per index (first iteration — we'll layer real timestamps
// in a follow-up). A short faint future-segment trails after the last event
// to suggest "more to come".
const LAYOUT = {
  rowH:           96,   // px — generous because the spine carries shapes, not just a line
  rowPadX:        20,   // px — horizontal breathing room
  orbR:           28,   // px — BIG identity orb (the sketch's left circle)
  orbCx:          48,   // px — orb centre from row left edge
  nameX:          92,   // px — where name strip starts
  nameW:          240,  // px reserved for name + contact
  spineX0:        340,  // px — where the timeline spine starts
  spineCY:        48,   // px — vertical centre of the spine in a row
  spineEventGap:  64,   // px between events on the spine
  spineMinTail:   80,   // px of faint future segment after the last event
  eventR:         11,   // px — half-width of each event shape
  liveR:          7,    // px — live point at the current frontier
};

// Allowed timeline event types — keep in sync with services/vio_overview.py
// _build_timeline. Anything we don't recognise renders as a neutral circle.
const EVENT_TOKENS = new Set([
  'intake', 'upload', 'analysis', 'gap', 'confirmation',
  'payment', 'error', 'complete',
]);

// Event status → semantic color token (see vio.css :root for hex values).
const STATUS_COLOR = {
  complete: 'green',
  active:   'blue',
  waiting:  'amber',
  error:    'red',
  resolved: 'grey',
};

// Event-type → human label for hover detail (no permanent text on the spine).
const EVENT_LABEL = {
  intake:       'intake',
  upload:       'document uploaded',
  analysis:     'evidence analysed',
  gap:          'evidence gap',
  confirmation: 'awaiting confirmation',
  payment:      'payment',
  error:        'extraction failure',
  complete:     'engagement complete',
};

// ── In-memory state ───────────────────────────────────────────────────────────
let _allCompanies = [];
let _searchQuery  = '';

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // No fixed stage-bar legend any more — the spine IS the timeline per the
  // sketch. We hide the legacy `vio-backbone` section in CSS rather than
  // touching the HTML, so the markup stays stable.

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

// (Legacy renderBackbone removed — the sketch has no fixed stage bar.
//  The vio-backbone section is hidden via CSS so the markup stays stable
//  for any caller that depends on its id.)

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

    // ── Visibility safeguard ──────────────────────────────────────────
    // We were burned by calling VIO_BOOT.ready() blind: a renderer that
    // appended invisible / zero-sized nodes would tear the boot overlay
    // down and leave a dark page with nothing for the operator to see.
    //
    // The contract now: we ONLY dismiss the boot overlay if there is at
    // least one .vio-trace OR a .vio-empty in the DOM. If neither is
    // present after a render attempt, that's a real failure — we route
    // it to the boot's diagnostic surface instead of going silently dark.
    const stage = document.getElementById('vio-stage');
    const painted = stage && stage.querySelectorAll('.vio-trace, .vio-empty').length > 0;
    if (window.VIO_BOOT) {
      if (painted) {
        window.VIO_BOOT.ready();
      } else if (typeof window.VIO_BOOT.fault === 'function') {
        window.VIO_BOOT.fault(
          'render-empty',
          `loadVioData succeeded with ${_allCompanies.length} ` +
          `company${_allCompanies.length === 1 ? '' : 's'} but the ` +
          'renderer produced zero visible nodes. Check vio.js renderTraces.'
        );
      }
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

// ══════════════════════════════════════════════════════════════════════════════
//  RENDER  (sketch-faithful spine — see docs/VIO_SOURCE_BRIEF.md)
// ══════════════════════════════════════════════════════════════════════════════

function renderTraces() {
  const stage = document.getElementById('vio-stage');
  if (!stage) return;

  document.getElementById('vio-loading')?.remove();
  stage.querySelectorAll('.vio-trace, .vio-empty, .vio-error-state').forEach(e => e.remove());

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
    empty.innerHTML =
      '<div class="vio-empty-mark">◎</div>' +
      '<div>no companies in the field</div>';
    stage.appendChild(empty);
    return;
  }

  // Already urgency-sorted by the backend (descending). Render top-to-bottom.
  rows.forEach((c, idx) => stage.appendChild(buildTrace(c, idx)));
}

// ── One trace per company ─────────────────────────────────────────────────────
function buildTrace(company, idx) {
  const events = _normaliseEvents(company.timeline || []);
  const stateToken = _normaliseStateToken(company.stage_state);

  // Spine length depends on how many events we have to hang on it. We pad
  // the right side with `spineMinTail` so the operator can see there's a
  // future ahead of the last event.
  const lastEventX = LAYOUT.spineX0 + Math.max(0, events.length - 1) * LAYOUT.spineEventGap;
  const spineEndX  = lastEventX + LAYOUT.spineMinTail;
  const rowW       = spineEndX + LAYOUT.rowPadX;

  const row = document.createElement('div');
  row.className = 'vio-trace';
  row.setAttribute('data-stage-state', stateToken);
  row.setAttribute('data-state',       company.state || '');
  row.setAttribute('data-on-branch',   String(!!company.on_branch));
  row.setAttribute('data-intake-id',   company.intake_id || '');
  row.style.minWidth = rowW + 'px';

  // ── Identity orb ──────────────────────────────────────────────────────
  // The sketch's BIG left circle. Holds the initial and pulses if the
  // company is in a state that requires operator/customer attention.
  // Tooltip carries name + email + phone so the operator can read
  // identity without opening the row.
  const orb = document.createElement('div');
  orb.className = 'vio-id-orb';
  orb.setAttribute('data-stage-state', stateToken);
  orb.style.left = (LAYOUT.orbCx - LAYOUT.orbR) + 'px';
  orb.style.width  = (LAYOUT.orbR * 2) + 'px';
  orb.style.height = (LAYOUT.orbR * 2) + 'px';
  orb.textContent = company.initials || '?';
  const identityParts = [
    company.company_name || 'Unknown',
    company.contact_email || '',
    company.contact_phone || '',
  ].filter(Boolean);
  orb.title = identityParts.join('\n');
  orb.setAttribute('aria-label', identityParts.join(' · '));
  row.appendChild(orb);

  // ── Name + contact strip ──────────────────────────────────────────────
  const nameWrap = document.createElement('div');
  nameWrap.className = 'vio-name-wrap';
  nameWrap.style.left  = LAYOUT.nameX + 'px';
  nameWrap.style.width = LAYOUT.nameW + 'px';

  const nameEl = document.createElement('div');
  nameEl.className = 'vio-name';
  nameEl.textContent = company.company_name || 'Unknown';
  nameWrap.appendChild(nameEl);

  const contactBits = [];
  if (company.contact_email) contactBits.push(company.contact_email);
  if (company.contact_phone) contactBits.push(company.contact_phone);
  if (contactBits.length) {
    const contactEl = document.createElement('div');
    contactEl.className = 'vio-contact';
    contactEl.textContent = contactBits.join(' · ');
    nameWrap.appendChild(contactEl);
  }
  // Attention summary (terse) — surfaces "4 evidence gaps · awaiting reply"
  // without making the operator hover.
  const attention = (company.attention || []).slice(0, 2);
  if (attention.length) {
    const attEl = document.createElement('div');
    attEl.className = 'vio-attn';
    attEl.setAttribute('data-stage-state', stateToken);
    attEl.textContent = attention.join(' · ');
    nameWrap.appendChild(attEl);
  }
  row.appendChild(nameWrap);

  // ── The spine SVG ─────────────────────────────────────────────────────
  const svg = buildSpine(company, events, spineEndX);
  row.appendChild(svg);

  // ── Hover / click ─────────────────────────────────────────────────────
  row.addEventListener('mouseenter', e => showHoverCard(e, company));
  row.addEventListener('mousemove',  e => positionHoverCard(e));
  row.addEventListener('mouseleave', hideHoverCard);
  row.addEventListener('click',      () => openLevel2(company));

  return row;
}

// ── The spine — continuous line + event shapes at temporal positions ─────────
function buildSpine(company, events, spineEndPxX) {
  const stateToken = _normaliseStateToken(company.stage_state);

  const svgW = spineEndPxX + LAYOUT.rowPadX;
  const svgH = LAYOUT.rowH;

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'vio-spine');
  svg.setAttribute('width',  svgW);
  svg.setAttribute('height', svgH);
  svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);

  // ── 1. The base spine line ──────────────────────────────────────────
  // Carries colour by state and activity-band thickness. The portion
  // past the last event fades to a "future ghost" so the operator can
  // see there's more to come.
  const lastEventX = events.length
    ? LAYOUT.spineX0 + (events.length - 1) * LAYOUT.spineEventGap
    : LAYOUT.spineX0;

  const past = document.createElementNS(SVG_NS, 'line');
  past.setAttribute('class', 'vio-spine-past');
  past.setAttribute('data-stage-state', stateToken);
  past.setAttribute('data-activity', _activityBand(company));
  past.setAttribute('data-stage-age-band', _stageAgeBand(company));
  past.setAttribute('x1', LAYOUT.spineX0);
  past.setAttribute('y1', LAYOUT.spineCY);
  past.setAttribute('x2', lastEventX);
  past.setAttribute('y2', LAYOUT.spineCY);
  svg.appendChild(past);

  if (spineEndPxX > lastEventX) {
    const future = document.createElementNS(SVG_NS, 'line');
    future.setAttribute('class', 'vio-spine-future');
    future.setAttribute('x1', lastEventX);
    future.setAttribute('y1', LAYOUT.spineCY);
    future.setAttribute('x2', spineEndPxX);
    future.setAttribute('y2', LAYOUT.spineCY);
    svg.appendChild(future);
  }

  // ── 2. Event shapes at temporal positions ───────────────────────────
  events.forEach((ev, i) => {
    const cx = LAYOUT.spineX0 + i * LAYOUT.spineEventGap;
    drawEvent(svg, cx, LAYOUT.spineCY, ev);
  });

  // ── 3. Live point at the frontier ───────────────────────────────────
  // A small pulsing/static disc at the last event, telling the operator
  // "this is the now". Pulses if the company is waiting on something.
  if (events.length) {
    drawLivePoint(svg, lastEventX, LAYOUT.spineCY, stateToken);
  }

  return svg;
}

// ── Event shapes (the sketch's vocabulary) ───────────────────────────────────
function drawEvent(svg, cx, cy, ev) {
  const type   = EVENT_TOKENS.has(ev.type) ? ev.type : 'unknown';
  const color  = STATUS_COLOR[ev.status] || 'blue';
  const r      = LAYOUT.eventR;
  const label  = EVENT_LABEL[type] || type;

  let node;
  switch (type) {
    case 'intake':
    case 'upload':
      node = _svgSquare(cx, cy, r);
      break;
    case 'analysis':
    case 'complete':
      node = _svgHexagon(cx, cy, r);
      break;
    case 'gap':
      node = _svgTriangle(cx, cy, r, /* down= */ false);
      break;
    case 'confirmation':
      node = _svgCircle(cx, cy, r * 0.85);
      break;
    case 'payment':
      node = _svgDiamond(cx, cy, r);
      break;
    case 'error':
      node = _svgStarburst(cx, cy, r);
      break;
    default:
      node = _svgCircle(cx, cy, r * 0.85);
  }
  node.setAttribute('class', 'vio-event');
  node.setAttribute('data-event-type',  type);
  node.setAttribute('data-event-status', ev.status || '');
  node.setAttribute('data-color',        color);

  const title = document.createElementNS(SVG_NS, 'title');
  title.textContent = `${label} — ${ev.label || ev.status || ''}`;
  node.appendChild(title);

  svg.appendChild(node);
}

function drawLivePoint(svg, cx, cy, stateToken) {
  const c = document.createElementNS(SVG_NS, 'circle');
  c.setAttribute('class', 'vio-live');
  c.setAttribute('data-stage-state', stateToken);
  c.setAttribute('cx', cx);
  c.setAttribute('cy', cy);
  c.setAttribute('r', LAYOUT.liveR);
  svg.appendChild(c);
}

// ── SVG primitives ────────────────────────────────────────────────────────────
function _svgCircle(cx, cy, r) {
  const n = document.createElementNS(SVG_NS, 'circle');
  n.setAttribute('cx', cx);
  n.setAttribute('cy', cy);
  n.setAttribute('r',  r);
  return n;
}
function _svgSquare(cx, cy, r) {
  const n = document.createElementNS(SVG_NS, 'rect');
  const side = r * 1.7;
  n.setAttribute('x', cx - side / 2);
  n.setAttribute('y', cy - side / 2);
  n.setAttribute('width',  side);
  n.setAttribute('height', side);
  n.setAttribute('rx', 1);
  return n;
}
function _svgTriangle(cx, cy, r, down) {
  const n = document.createElementNS(SVG_NS, 'polygon');
  const s = r * 1.9;
  const h = s * 0.866;
  const pts = down
    ? `${cx - s / 2},${cy - h / 2} ${cx + s / 2},${cy - h / 2} ${cx},${cy + h / 2}`
    : `${cx},${cy - h / 2} ${cx - s / 2},${cy + h / 2} ${cx + s / 2},${cy + h / 2}`;
  n.setAttribute('points', pts);
  return n;
}
function _svgHexagon(cx, cy, r) {
  const n = document.createElementNS(SVG_NS, 'polygon');
  const s = r * 1.1;
  const pts = [];
  for (let i = 0; i < 6; i++) {
    const ang = -Math.PI / 2 + i * Math.PI / 3;
    pts.push(`${cx + s * Math.cos(ang)},${cy + s * Math.sin(ang)}`);
  }
  n.setAttribute('points', pts.join(' '));
  return n;
}
function _svgDiamond(cx, cy, r) {
  const n = document.createElementNS(SVG_NS, 'polygon');
  const s = r * 1.25;
  n.setAttribute('points',
    `${cx},${cy - s} ${cx + s},${cy} ${cx},${cy + s} ${cx - s},${cy}`);
  return n;
}
function _svgStarburst(cx, cy, r) {
  // Eight spokes radiating from the centre — the sketch's "broken" mark.
  const g = document.createElementNS(SVG_NS, 'g');
  const long  = r * 1.0;
  const short = r * 0.55;
  const spokes = [
    [-long, -long,  long,  long],
    [-long,  long,  long, -long],
    [    0, -long,    0,  long],
    [-long,    0,  long,    0],
    [-short,-short,short,-short],
    [-short, short,short, short],
  ];
  spokes.forEach(([x1, y1, x2, y2]) => {
    const l = document.createElementNS(SVG_NS, 'line');
    l.setAttribute('x1', cx + x1); l.setAttribute('y1', cy + y1);
    l.setAttribute('x2', cx + x2); l.setAttribute('y2', cy + y2);
    g.appendChild(l);
  });
  return g;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function _normaliseEvents(rawEvents) {
  // Defensive: filter out malformed entries; always guarantee at least one
  // event (a synthetic "intake" marker) so even a sparse company has a
  // visible orb-and-square anchor on the spine.
  const out = [];
  for (const ev of (rawEvents || [])) {
    if (!ev || typeof ev !== 'object') continue;
    const type = String(ev.type || '').toLowerCase();
    if (!type) continue;
    out.push({
      type:   type,
      status: String(ev.status || 'active').toLowerCase(),
      label:  ev.label || '',
      utc:    ev.utc || '',
    });
  }
  if (!out.length) {
    out.push({ type: 'intake', status: 'active', label: 'intake', utc: '' });
  }
  return out;
}

function _normaliseStateToken(s) {
  const known = new Set([
    'healthy', 'stalled', 'failed', 'waiting_client', 'inconsistent', 'done',
  ]);
  return known.has(s) ? s : 'healthy';
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

  // Backend provides the stage label directly on the company object —
  // we no longer hold a client-side BACKBONE table because the sketch
  // model is a timeline, not a fixed stage bar.
  const stage = (company.stage || 'intake').replace(/_/g, ' ');
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
  stateRow.setAttribute('data-stage-state', _normaliseStateToken(state));
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
