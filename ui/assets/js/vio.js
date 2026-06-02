/* ══════════════════════════════════════════════════════════════════════════════
   VIO 2.0 — Visual Intelligence Observatory
   Renders live company timelines from /api/operator/vio/overview
   ══════════════════════════════════════════════════════════════════════════════ */
'use strict';

// ── SVG namespace ──────────────────────────────────────────────────────────────
const SVG_NS = 'http://www.w3.org/2000/svg';

// ── Layout constants ────────────────────────────────────────────────────────────
const TIMELINE_H    = 72;   // row height in px
const NODE_CY       = 36;   // vertical centre of node in row
const NODE_R        = 18;   // node shape bounding radius
const FIRST_X       = 60;   // x of first node from SVG left edge
const NODE_SPACING  = 130;  // px between node centres
const STUB_LEN      = 80;   // trailing stub after last node

// ── State → line CSS class ──────────────────────────────────────────────────────
const LINE_CLASS = {
  new:             'vio-line-stub',
  active:          'vio-line-active',
  analyzing:       'vio-line-analyzing',
  gap:             'vio-line-gap',
  waiting:         'vio-line-waiting',
  payment_pending: 'vio-line-active',
  complete:        'vio-line-complete',
  error:           'vio-line-error',
  stuck:           'vio-line-error',
};

// ── Node type → shape drawing function ──────────────────────────────────────────
const NODE_SHAPES = {
  intake(svg, cx, cy) {
    // Hexagon — the entry portal
    const hex = poly(svg, hexPoints(cx, cy, NODE_R - 2));
    return hex;
  },
  upload(svg, cx, cy) {
    // Folder with upward chevron
    const g = el(svg, 'g');
    const body = el(g, 'rect');
    attr(body, { x: cx - 14, y: cy - 10, width: 28, height: 20, rx: 3 });
    const tab = el(g, 'rect');
    attr(tab, { x: cx - 14, y: cy - 14, width: 12, height: 5, rx: 2 });
    const arrow = el(g, 'polyline');
    attr(arrow, { points: `${cx},${cy + 6} ${cx},${cy - 2} ${cx - 5},${cy + 3} ${cx},${cy - 2} ${cx + 5},${cy + 3}`, fill: 'none', 'stroke-width': 2, stroke: 'inherit' });
    return g;
  },
  analysis(svg, cx, cy) {
    // Diamond
    return poly(svg, `${cx},${cy - NODE_R + 2} ${cx + NODE_R - 2},${cy} ${cx},${cy + NODE_R - 2} ${cx - NODE_R + 2},${cy}`);
  },
  gap(svg, cx, cy) {
    // Broken circle — missing piece
    const g = el(svg, 'g');
    const arc = el(g, 'path');
    const r = NODE_R - 3;
    // Circle arc with a gap at the bottom-right
    attr(arc, { d: describeArc(cx, cy, r, 50, 310), fill: 'none', 'stroke-width': 4, stroke: 'inherit' });
    // Small gap indicator lines
    const l1 = el(g, 'line');
    const l2 = el(g, 'line');
    attr(l1, { x1: cx + r * Math.cos(50 * Math.PI / 180) - 3, y1: cy + r * Math.sin(50 * Math.PI / 180) + 3, x2: cx + r * Math.cos(50 * Math.PI / 180) + 5, y2: cy + r * Math.sin(50 * Math.PI / 180) - 3, 'stroke-width': 2, stroke: 'inherit' });
    attr(l2, { x1: cx + r * Math.cos(310 * Math.PI / 180) - 3, y1: cy + r * Math.sin(310 * Math.PI / 180) - 3, x2: cx + r * Math.cos(310 * Math.PI / 180) + 5, y2: cy + r * Math.sin(310 * Math.PI / 180) + 3, 'stroke-width': 2, stroke: 'inherit' });
    // Question mark dot
    const dot = el(g, 'circle');
    attr(dot, { cx, cy: cy + 1, r: 2, fill: 'inherit' });
    return g;
  },
  confirmation(svg, cx, cy) {
    // Warning triangle with !
    const g = el(svg, 'g');
    const tri = poly(svg, `${cx},${cy - NODE_R + 2} ${cx + NODE_R - 2},${cy + NODE_R - 4} ${cx - NODE_R + 2},${cy + NODE_R - 4}`);
    g.appendChild(tri);
    const bang = el(g, 'text');
    attr(bang, { x: cx, y: cy + NODE_R - 8, 'text-anchor': 'middle', 'dominant-baseline': 'middle', 'font-size': 11, 'font-weight': 700, fill: 'inherit' });
    bang.textContent = '!';
    return g;
  },
  payment(svg, cx, cy) {
    // Payment card
    const g = el(svg, 'g');
    const card = el(g, 'rect');
    attr(card, { x: cx - 16, y: cy - 11, width: 32, height: 22, rx: 3 });
    const strip = el(g, 'rect');
    attr(strip, { x: cx - 16, y: cy - 5, width: 32, height: 6, fill: 'inherit', 'fill-opacity': 0.4 });
    const dot1 = el(g, 'circle');
    attr(dot1, { cx: cx - 6, cy: cy + 5, r: 2, fill: 'inherit', 'fill-opacity': 0.6 });
    const dot2 = el(g, 'circle');
    attr(dot2, { cx: cx + 2, cy: cy + 5, r: 2, fill: 'inherit', 'fill-opacity': 0.6 });
    return g;
  },
  complete(svg, cx, cy) {
    // Circle with checkmark burst
    const g = el(svg, 'g');
    const circ = el(g, 'circle');
    attr(circ, { cx, cy, r: NODE_R - 3 });
    const tick = el(g, 'polyline');
    attr(tick, { points: `${cx - 8},${cy} ${cx - 2},${cy + 7} ${cx + 9},${cy - 7}`, fill: 'none', 'stroke-width': 2.5, stroke: '#fff', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
    return g;
  },
  error(svg, cx, cy) {
    // Lightning bolt
    return poly(svg, `${cx - 2},${cy - NODE_R + 2} ${cx + 6},${cy - 2} ${cx + 1},${cy - 2} ${cx + 4},${cy + NODE_R - 2} ${cx - 4},${cy + 2} ${cx + 1},${cy + 2} ${cx - 2},${cy - NODE_R + 2}`);
  },
};

// ── SVG helpers ─────────────────────────────────────────────────────────────────
function el(parent, tag) {
  const e = document.createElementNS(SVG_NS, tag);
  parent.appendChild(e);
  return e;
}
function attr(e, attrs) {
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
}
function poly(parent, points) {
  const p = el(parent, 'polygon');
  attr(p, { points });
  return p;
}
function hexPoints(cx, cy, r) {
  return Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 180) * (60 * i - 30);
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  }).join(' ');
}
function describeArc(cx, cy, r, startDeg, endDeg) {
  const toRad = d => d * Math.PI / 180;
  const x1 = cx + r * Math.cos(toRad(startDeg));
  const y1 = cy + r * Math.sin(toRad(startDeg));
  const x2 = cx + r * Math.cos(toRad(endDeg));
  const y2 = cy + r * Math.sin(toRad(endDeg));
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
}

// ── State color (for orb and badges) ───────────────────────────────────────────
const STATE_COLORS = {
  new: '#475569', active: '#3b82f6', analyzing: '#8b5cf6',
  gap: '#f59e0b', waiting: '#fb923c', payment_pending: '#10b981',
  complete: '#22c55e', error: '#ef4444', stuck: '#dc2626',
};

function stateColor(s) { return STATE_COLORS[s] || '#475569'; }

// ── Node line class ─────────────────────────────────────────────────────────────
function lineClass(company, nodeIndex, totalNodes) {
  if (nodeIndex >= totalNodes - 1) return 'vio-line-stub';
  return LINE_CLASS[company.state] || 'vio-line-normal';
}

// ── Build one company row ────────────────────────────────────────────────────────
function buildCompanyRow(company, rowIndex) {
  const row = document.createElement('div');
  row.className = 'vio-company-row';
  row.setAttribute('data-state', company.state);
  row.setAttribute('data-pid', company.project_id);
  row.style.animationDelay = `${rowIndex * 60}ms`;

  // ── Orb ──
  const orbWrap = document.createElement('div');
  orbWrap.className = 'vio-orb-wrap';
  orbWrap.title = `${company.company_name}\n${company.contact_email}`;

  const orb = document.createElement('div');
  orb.className = 'vio-orb';
  orb.setAttribute('data-state', company.state);
  orb.textContent = company.initials;

  const orbLabel = document.createElement('div');
  orbLabel.className = 'vio-orb-label';
  orbLabel.textContent = company.company_name;

  orbWrap.appendChild(orb);
  orbWrap.appendChild(orbLabel);
  orbWrap.addEventListener('click', () => openDetailPanel(company, 'company'));
  row.appendChild(orbWrap);

  // ── Timeline ──
  const tlWrap = document.createElement('div');
  tlWrap.className = 'vio-timeline-wrap';

  const segments = company.timeline || [];
  const totalNodes = segments.length;
  const svgW = FIRST_X + totalNodes * NODE_SPACING + STUB_LEN;

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'vio-timeline-svg');
  attr(svg, { width: svgW, height: TIMELINE_H, viewBox: `0 0 ${svgW} ${TIMELINE_H}` });

  // Draw lines between nodes
  for (let i = 0; i < totalNodes; i++) {
    const x1 = i === 0 ? 0 : FIRST_X + (i - 1) * NODE_SPACING + NODE_R + 2;
    const x2 = FIRST_X + i * NODE_SPACING - NODE_R - 2;
    if (x2 > x1) {
      const line = el(svg, 'line');
      attr(line, { x1, y1: NODE_CY, x2, y2: NODE_CY });
      line.setAttribute('class', lineClass(company, i, totalNodes));
    }
  }
  // Trailing stub
  if (totalNodes > 0 && company.state !== 'complete') {
    const lastX = FIRST_X + (totalNodes - 1) * NODE_SPACING + NODE_R + 2;
    const stubLine = el(svg, 'line');
    attr(stubLine, { x1: lastX, y1: NODE_CY, x2: lastX + STUB_LEN, y2: NODE_CY });
    stubLine.setAttribute('class', 'vio-line-stub');
  }

  // Draw nodes
  segments.forEach((seg, i) => {
    const cx = FIRST_X + i * NODE_SPACING;
    const nodeGroup = el(svg, 'g');
    nodeGroup.setAttribute('class', 'vio-node-group');
    nodeGroup.setAttribute('data-state', seg.status);
    nodeGroup.setAttribute('data-type', seg.type);

    // Invisible hit area
    const hitArea = el(nodeGroup, 'circle');
    attr(hitArea, { cx, cy: NODE_CY, r: NODE_R + 6, fill: 'transparent' });

    // Shape
    const drawFn = NODE_SHAPES[seg.type] || NODE_SHAPES.intake;
    const shape = drawFn(nodeGroup, cx, NODE_CY);
    if (shape) {
      shape.setAttribute('class', 'vio-node-shape');
      shape.setAttribute('data-type', seg.type);
      shape.setAttribute('data-status', seg.status);
    }

    // Label below (odd indices) or above (even)
    const labelY = i % 2 === 0 ? NODE_CY + NODE_R + 10 : NODE_CY - NODE_R - 4;
    const labelClass = i % 2 === 0 ? 'vio-node-label' : 'vio-node-label-top';
    const label = el(svg, 'text');
    attr(label, { x: cx, y: labelY, class: labelClass });
    // Shorten long labels
    const shortLabel = seg.label.length > 16 ? seg.label.slice(0, 14) + '…' : seg.label;
    label.textContent = shortLabel;

    // Tooltip + click
    nodeGroup.addEventListener('mouseenter', e => showTooltip(e, seg.label));
    nodeGroup.addEventListener('mouseleave', hideTooltip);
    nodeGroup.addEventListener('click', () => openDetailPanel(company, seg.type, seg));

    svg.appendChild(nodeGroup);
  });

  tlWrap.appendChild(svg);
  row.appendChild(tlWrap);

  // ── Quick stats strip (far right) ──
  if (company.quick_stats) {
    const statsEl = buildQuickStats(company);
    row.appendChild(statsEl);
  }

  return row;
}

// ── Quick stats column ─────────────────────────────────────────────────────────
function buildQuickStats(company) {
  const s = company.quick_stats;
  const div = document.createElement('div');
  div.style.cssText = 'flex-shrink:0; padding:0 14px; display:flex; flex-direction:column; gap:4px; font-size:11px; color:var(--vio-text-dim); border-left:1px solid var(--vio-border); min-width:90px; justify-content:center;';

  const items = [];
  if (s.files_uploaded)  items.push([s.files_uploaded, '📄', 'files']);
  if (s.gaps)            items.push([s.gaps, '⚠', 'gaps']);
  if (s.failures)        items.push([s.failures, '⚡', 'errors']);
  if (s.confirmation_needed) items.push([s.confirmation_needed, '?', 'confirm']);

  items.slice(0, 3).forEach(([count, icon, label]) => {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex; align-items:center; gap:5px;';
    row.innerHTML = `<span style="opacity:.6">${icon}</span><strong style="color:var(--vio-text)">${count}</strong><span>${label}</span>`;
    div.appendChild(row);
  });

  if (!items.length) {
    div.innerHTML = '<span style="opacity:.4">No activity</span>';
  }

  return div;
}

// ── Health summary bar ────────────────────────────────────────────────────────
function renderHealthBar(health) {
  const bar = document.getElementById('vio-health-bar');
  if (!bar) return;
  bar.innerHTML = '';

  const order = ['error', 'stuck', 'gap', 'waiting', 'analyzing', 'active', 'payment_pending', 'new', 'complete'];
  const labels = {
    error: 'Error', stuck: 'Stuck', gap: 'Gap', waiting: 'Waiting',
    analyzing: 'Analyzing', active: 'Active', payment_pending: 'Payment',
    new: 'New', complete: 'Done',
  };

  for (const state of order) {
    const count = health[state];
    if (!count) continue;
    const pill = document.createElement('span');
    pill.className = 'vio-health-pill';
    pill.setAttribute('data-state', state);
    pill.title = `Filter: ${labels[state]}`;
    pill.innerHTML = `<span class="vio-hp-dot" data-state="${state}"></span>${count} ${labels[state]}`;
    pill.addEventListener('click', () => filterByState(state));
    bar.appendChild(pill);
  }

  if (!bar.children.length) {
    bar.innerHTML = '<span style="color:var(--vio-text-dim);font-size:12px">No companies yet</span>';
  }
}

// ── Filter ──────────────────────────────────────────────────────────────────────
let _currentFilter = 'all';
let _allCompanies  = [];

function filterByState(state) {
  _currentFilter = (_currentFilter === state) ? 'all' : state;
  renderCompanyList(_allCompanies);
}

function filterBySearch(query) {
  renderCompanyList(_allCompanies, query);
}

function renderCompanyList(companies, searchQuery = '') {
  const stage = document.getElementById('vio-stage');
  if (!stage) return;

  // Remove existing rows (keep loading/empty placeholders)
  stage.querySelectorAll('.vio-company-row').forEach(r => r.remove());

  const q = (searchQuery || '').toLowerCase();
  let filtered = companies;

  if (_currentFilter !== 'all') {
    filtered = filtered.filter(c => c.state === _currentFilter);
  }
  if (q) {
    filtered = filtered.filter(c =>
      c.company_name.toLowerCase().includes(q) ||
      (c.contact_email || '').toLowerCase().includes(q)
    );
  }

  const loading = document.getElementById('vio-loading');
  if (loading) loading.remove();

  if (!filtered.length) {
    let empty = stage.querySelector('.vio-empty');
    if (!empty) {
      empty = document.createElement('div');
      empty.className = 'vio-empty';
      empty.innerHTML = '<div class="vio-empty-icon">◎</div><div>No companies match this view</div>';
      stage.appendChild(empty);
    }
    return;
  }

  stage.querySelector('.vio-empty')?.remove();
  filtered.forEach((company, idx) => {
    stage.appendChild(buildCompanyRow(company, idx));
  });
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
let _tooltip = null;
function showTooltip(e, text) {
  if (!_tooltip) {
    _tooltip = document.createElement('div');
    _tooltip.className = 'vio-tooltip';
    document.body.appendChild(_tooltip);
  }
  _tooltip.textContent = text;
  _tooltip.removeAttribute('hidden');
  positionTooltip(e);
}
function positionTooltip(e) {
  if (!_tooltip) return;
  const x = e.clientX + 12;
  const y = e.clientY - 28;
  _tooltip.style.left = `${Math.min(x, window.innerWidth - 240)}px`;
  _tooltip.style.top  = `${Math.max(y, 4)}px`;
}
function hideTooltip() {
  if (_tooltip) _tooltip.setAttribute('hidden', '');
}
document.addEventListener('mousemove', positionTooltip);

// ── Detail panel ─────────────────────────────────────────────────────────────
function openDetailPanel(company, nodeType, segment) {
  const panel = document.getElementById('vio-detail-panel');
  const body  = document.getElementById('vio-detail-body');
  if (!panel || !body) return;

  body.innerHTML = '';
  body.appendChild(buildDetailContent(company, nodeType, segment));

  panel.removeAttribute('hidden');
  document.body.style.overflow = 'hidden';
}

function closeDetailPanel() {
  const panel = document.getElementById('vio-detail-panel');
  if (panel) panel.setAttribute('hidden', '');
  document.body.style.overflow = '';
}

function buildDetailContent(company, nodeType, segment) {
  const frag = document.createDocumentFragment();

  // Header
  const header = div('vio-detail-header');
  const orbEl  = div('vio-detail-orb');
  orbEl.textContent = company.initials;
  orbEl.style.background = `radial-gradient(circle at 35% 35%, ${stateColor(company.state)}cc, ${stateColor(company.state)}55)`;
  orbEl.style.boxShadow   = `0 0 16px ${stateColor(company.state)}66`;

  const titleWrap = div('');
  titleWrap.style.flex = '1';
  const titleEl = div('vio-detail-title');
  titleEl.textContent = company.company_name;
  const subEl = div('vio-detail-sub');
  subEl.textContent = company.contact_email || '';

  const stateBadge = div('vio-detail-state-badge');
  stateBadge.textContent = company.state.replace(/_/g, ' ').toUpperCase();
  stateBadge.style.cssText = `background:${stateColor(company.state)}22; color:${stateColor(company.state)}; border:1px solid ${stateColor(company.state)}44; border-radius:12px; font-size:10px; font-weight:700; padding:2px 8px; margin-top:5px; display:inline-flex; align-items:center; gap:4px;`;

  titleWrap.appendChild(titleEl);
  titleWrap.appendChild(subEl);
  titleWrap.appendChild(stateBadge);
  header.appendChild(orbEl);
  header.appendChild(titleWrap);
  frag.appendChild(header);

  // Quick stats
  const qs = company.quick_stats;
  if (qs) {
    const statsSection = section('At a glance');
    const grid = div('vio-kv-grid');
    const kvItems = [
      ['Files uploaded',  qs.files_uploaded],
      ['Files analyzed',  qs.files_analyzed],
      ['Gaps detected',   qs.gaps],
      ['Errors',          qs.failures],
      ['Pending analysis',qs.pending],
      ['Need confirmation', qs.confirmation_needed],
    ].filter(([, v]) => v != null);
    kvItems.forEach(([k, v]) => {
      const kv = div('vio-kv');
      kv.innerHTML = `<div class="vio-kv-key">${k}</div><div class="vio-kv-value">${v}</div>`;
      grid.appendChild(kv);
    });
    statsSection.appendChild(grid);
    frag.appendChild(statsSection);
  }

  // Next action
  if (company.next_action) {
    const actionSection = section('Recommended action');
    const box = div('vio-next-action');
    box.textContent = company.next_action;
    actionSection.appendChild(box);
    frag.appendChild(actionSection);
  }

  // Node-specific detail
  if (segment && segment.detail) {
    const d = segment.detail;

    // Gaps
    if (d.gaps && d.gaps.length) {
      const gapSection = section('Evidence gaps');
      const list = document.createElement('ul');
      list.className = 'vio-gap-list';
      d.gaps.forEach(g => {
        const item = document.createElement('li');
        item.className = 'vio-gap-item';
        item.setAttribute('data-priority', g.priority || 'medium');
        const badge = span('vio-gap-badge', (g.priority || 'med').toUpperCase());
        badge.setAttribute('data-priority', g.priority || 'medium');
        const label = span('', g.label || g.id);
        item.appendChild(badge);
        item.appendChild(label);
        list.appendChild(item);
      });
      gapSection.appendChild(list);
      frag.appendChild(gapSection);
    }

    // Document types
    if (d.doc_types && d.doc_types.length) {
      const docSection = section('Documents uploaded');
      const list = document.createElement('ul');
      list.className = 'vio-doc-list';
      d.doc_types.forEach(doc => {
        const item = document.createElement('li');
        item.className = 'vio-doc-item';
        const typeEl = span('vio-doc-type', (doc.type || 'unknown').replace(/_/g, ' '));
        const nameEl = span('', doc.file || '');
        nameEl.style.cssText = 'flex:1; color:var(--vio-text-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;';
        const confBar = div('vio-confidence-bar');
        const confFill = div('vio-confidence-fill');
        confFill.style.width = `${Math.round((doc.confidence || 0) * 100)}%`;
        confBar.appendChild(confFill);
        item.appendChild(typeEl);
        item.appendChild(nameEl);
        item.appendChild(confBar);
        list.appendChild(item);
      });
      docSection.appendChild(list);
      frag.appendChild(docSection);
    }

    // Company profile
    if (d.company_names && d.company_names.length) {
      const profileSection = section('Extracted profile');
      if (d.technologies && d.technologies.length) {
        const tagWrap = div('');
        tagWrap.innerHTML = '<div class="vio-kv-key" style="margin-bottom:5px">Technologies</div>';
        const tags = div('vio-tag-list');
        d.technologies.forEach(t => {
          const tag = span('vio-tag', t);
          tags.appendChild(tag);
        });
        tagWrap.appendChild(tags);
        profileSection.appendChild(tagWrap);
      }
      if (d.compliance_references && d.compliance_references.length) {
        const cr = div('');
        cr.innerHTML = '<div class="vio-kv-key" style="margin-top:10px;margin-bottom:5px">Compliance references</div>';
        const tags = div('vio-tag-list');
        d.compliance_references.forEach(r => {
          const tag = span('vio-tag', r);
          tag.style.background = 'rgba(139,92,246,.15)';
          tag.style.color = '#c4b5fd';
          tags.appendChild(tag);
        });
        cr.appendChild(tags);
        profileSection.appendChild(cr);
      }
      frag.appendChild(profileSection);
    }

    // Confirmation items
    if (d.items && d.items.length) {
      const confSection = section('Items needing confirmation');
      d.items.forEach(item => {
        const row = div('');
        row.style.cssText = 'padding:7px 10px; background:var(--vio-bg); border:1px solid var(--vio-border); border-radius:6px; margin-bottom:5px; font-size:12px;';
        const fieldEl = span('', (item.field || '').replace(/_/g, ' '));
        fieldEl.style.color = 'var(--vio-text-dim)';
        const valEl = document.createElement('strong');
        valEl.style.cssText = 'color:var(--vio-text); margin-left:8px;';
        valEl.textContent = item.value || '';
        const statusEl = span('', item.status || 'inferred');
        statusEl.style.cssText = 'float:right; font-size:10px; color:var(--vio-text-dim);';
        row.appendChild(statusEl);
        row.appendChild(fieldEl);
        row.appendChild(valEl);
        confSection.appendChild(row);
      });
      frag.appendChild(confSection);
    }
  }

  // Cockpit link
  const linkSection = section('');
  const link = document.createElement('a');
  link.href = `/ui/control.html`;
  link.style.cssText = 'color:var(--vio-text-dim); font-size:11px; text-decoration:none; display:block; text-align:center; padding:8px; border:1px solid var(--vio-border); border-radius:6px; transition:color .2s;';
  link.textContent = '⚙ Open full cockpit for actions';
  link.addEventListener('mouseenter', () => { link.style.color = 'var(--vio-text)'; });
  link.addEventListener('mouseleave', () => { link.style.color = 'var(--vio-text-dim)'; });
  linkSection.appendChild(link);
  frag.appendChild(linkSection);

  return frag;
}

// ── DOM helpers ───────────────────────────────────────────────────────────────
function div(cls) {
  const e = document.createElement('div');
  if (cls) e.className = cls;
  return e;
}
function span(cls, text) {
  const e = document.createElement('span');
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function section(title) {
  const wrap = div('vio-section');
  if (title) {
    const t = div('vio-section-title');
    t.textContent = title;
    wrap.appendChild(t);
  }
  return wrap;
}

// ── Data load ─────────────────────────────────────────────────────────────────
async function loadVioData() {
  try {
    const resp = await fetch('/api/operator/vio/overview?limit=80');
    if (resp.status === 401 || resp.status === 403) {
      window.location.href = '/ui/login.html?next=/ui/vio.html';
      return;
    }
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'API error');
    _allCompanies = data.companies || [];
    renderHealthBar(data.organism_health || {});
    renderCompanyList(_allCompanies);
  } catch (err) {
    const stage = document.getElementById('vio-stage');
    if (stage) {
      const loading = document.getElementById('vio-loading');
      if (loading) loading.remove();
      const errEl = div('vio-error-state');
      errEl.innerHTML = `<strong>Could not load awareness field</strong><br><span style="opacity:.7">${err.message}</span>`;
      stage.appendChild(errEl);
    }
    console.error('[VIO]', err);
  }
}

// ── Auto-refresh every 60s ────────────────────────────────────────────────────
function startAutoRefresh() {
  setInterval(async () => {
    try {
      const resp = await fetch('/api/operator/vio/overview?limit=80');
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data.ok) return;
      _allCompanies = data.companies || [];
      renderHealthBar(data.organism_health || {});
      // Only re-render list if no detail panel is open
      if (document.getElementById('vio-detail-panel')?.hasAttribute('hidden')) {
        renderCompanyList(_allCompanies, document.getElementById('vio-search')?.value || '');
      }
    } catch (_) { /* silent on auto-refresh */ }
  }, 60_000);
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Search
  const searchEl = document.getElementById('vio-search');
  if (searchEl) {
    let debounce;
    searchEl.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => filterBySearch(searchEl.value), 200);
    });
  }

  // Refresh button
  document.getElementById('vio-refresh-btn')?.addEventListener('click', () => {
    const stage = document.getElementById('vio-stage');
    stage?.querySelectorAll('.vio-company-row, .vio-empty, .vio-error-state').forEach(e => e.remove());
    const loading = document.createElement('div');
    loading.id = 'vio-loading';
    loading.className = 'vio-loading';
    loading.innerHTML = '<div class="vio-loading-orb"></div><span>Refreshing...</span>';
    stage?.appendChild(loading);
    loadVioData();
  });

  // Detail panel close
  document.getElementById('vio-detail-close')?.addEventListener('click', closeDetailPanel);
  document.getElementById('vio-detail-backdrop')?.addEventListener('click', closeDetailPanel);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDetailPanel(); });

  loadVioData();
  startAutoRefresh();
});
