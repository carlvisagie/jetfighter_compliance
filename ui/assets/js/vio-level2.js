/* ══════════════════════════════════════════════════════════════════════════════
   VIO — Level 2 (Visual Intelligent Landscape)

   When an operator clicks a company's Level 1 trace, that single line expands
   into an immersive horizontal landscape:

       [ORB]──●──────●──────●──────●──────●──────●──────●
       intake class. valid. evid.  review approv conv.
              │      │      │      │      │      │      │
              └ context     │      │      │      │      │
              ┐ identifiers ┘      │      │      │      │
                                   ├─ docs uploaded     │
                                   ├─ docs missing      │
                                   ├─ findings          │
                                                ├─ payment
                                                       └─ kickoff
                                                       └─ generated

   Doctrine (docs/VIO_DOCTRINE.md):
     · Linear — orb on left, spine going right. NOT radial.
     · Branches sprout PERPENDICULAR from the spine.
     · Bushiness = real complexity.  Clean companies stay a clean spine.
     · Every visual element is clickable → recursive detail in side panel.
     · Stillness baseline; only `waiting_client` ever breathes.
   ══════════════════════════════════════════════════════════════════════════════ */
'use strict';

(function (global) {
  const SVG_NS = 'http://www.w3.org/2000/svg';

  // ── Must mirror services/vio_overview.STAGE_BACKBONE ────────────────────
  const STAGES = [
    { key: 'intake',           label: 'intake' },
    { key: 'classification',   label: 'classification' },
    { key: 'validation',       label: 'validation' },
    { key: 'evidence_mapping', label: 'evidence mapping' },
    { key: 'review',           label: 'review' },
    { key: 'approval',         label: 'approval' },
    { key: 'conversion',       label: 'conversion' },
  ];

  // ── Layout constants ──────────────────────────────────────────────────
  const L = {
    orbR:        24,
    orbCx:       60,
    spineY:      260,         // vertical centre of viewport
    spineX0:     130,
    stageGap:    180,
    stageR:      9,
    branchSpacing: 60,        // vertical distance between successive leaves
    leafW:       66,
    leafH:       38,
    leafGap:     14,          // horizontal spacing between leaves in a cluster
    leavesPerRow: 4,          // how many leaves wrap before a new row
  };

  function spineEndX() {
    return L.spineX0 + (STAGES.length - 1) * L.stageGap;
  }

  // ── Public entry ──────────────────────────────────────────────────────
  global.VioLevel2 = {
    open: openLevel2,
    close: closeLevel2,
  };

  // ── State ─────────────────────────────────────────────────────────────
  let _activeCompany = null;
  let _activeDetail  = null;

  async function openLevel2(company) {
    _activeCompany = company;

    const mount = document.getElementById('vio-level2-mount');
    if (!mount) return;
    mount.innerHTML = '';
    mount.removeAttribute('hidden');
    document.body.style.overflow = 'hidden';

    // Build skeleton immediately (so the operator sees the orb and a sense
    // of place even before the fetch resolves).
    mount.appendChild(buildHeader(company));
    const canvas = buildCanvas();
    mount.appendChild(canvas);
    const sidepanel = buildSidePanel();
    mount.appendChild(sidepanel);

    renderSkeletonSpine(canvas, company);
    showSideHint(sidepanel, 'reading the field…');

    // Fetch the composite detail and re-render with full data.
    const intakeKey = company.intake_id || company.row_id || company.project_id;
    if (!intakeKey) {
      showSideHint(sidepanel, 'no intake id — nothing to render');
      return;
    }
    try {
      const resp = await fetch(`/api/operator/vio/company/${encodeURIComponent(intakeKey)}`, {
        credentials: 'same-origin',
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const detail = await resp.json();
      if (!detail.ok) throw new Error(detail.error || 'API error');
      _activeDetail = detail;
      renderLandscape(canvas, company, detail);
      renderOverview(sidepanel, company, detail);
    } catch (err) {
      showSideHint(sidepanel, 'could not load landscape: ' + err.message);
      console.error('[VIO L2]', err);
    }
  }

  function closeLevel2() {
    const mount = document.getElementById('vio-level2-mount');
    if (mount) {
      mount.setAttribute('hidden', '');
      mount.innerHTML = '';
    }
    document.body.style.overflow = '';
    _activeCompany = null;
    _activeDetail  = null;
  }

  // ── Header (back chevron · company · state) ───────────────────────────
  function buildHeader(company) {
    const h = el('div', 'vio-l2-header');

    const back = el('button', 'vio-l2-back');
    back.textContent = '← back to VIO';
    back.addEventListener('click', closeLevel2);
    h.appendChild(back);

    const titleWrap = el('div', 'vio-l2-titlewrap');
    const t = el('div', 'vio-l2-title');
    t.textContent = company.company_name || 'Unknown';
    titleWrap.appendChild(t);

    const sub = el('div', 'vio-l2-sub');
    sub.textContent = company.contact_email || '';
    titleWrap.appendChild(sub);
    h.appendChild(titleWrap);

    const state = el('div', 'vio-l2-state');
    state.setAttribute('data-stage-state', company.stage_state || 'healthy');
    state.textContent = (company.stage_state || 'healthy').replace(/_/g, ' ');
    h.appendChild(state);

    return h;
  }

  // ── Canvas (scrollable SVG container) ─────────────────────────────────
  function buildCanvas() {
    const c = el('div', 'vio-l2-canvas');
    c.id = 'vio-l2-canvas';
    return c;
  }

  // ── Side panel (recursive detail surface) ─────────────────────────────
  function buildSidePanel() {
    const s = el('aside', 'vio-l2-side');
    s.id = 'vio-l2-side';

    const header = el('div', 'vio-l2-side-header');
    const title  = el('div', 'vio-l2-side-title');
    title.id     = 'vio-l2-side-title';
    title.textContent = 'overview';
    header.appendChild(title);

    const backBtn = el('button', 'vio-l2-side-back');
    backBtn.id = 'vio-l2-side-back';
    backBtn.textContent = '← back';
    backBtn.hidden = true;
    backBtn.addEventListener('click', () => {
      if (_activeDetail) renderOverview(s, _activeCompany, _activeDetail);
    });
    header.appendChild(backBtn);
    s.appendChild(header);

    const body = el('div', 'vio-l2-side-body');
    body.id    = 'vio-l2-side-body';
    s.appendChild(body);

    return s;
  }

  function showSideHint(side, text) {
    const body = side.querySelector('#vio-l2-side-body');
    if (!body) return;
    body.innerHTML = '';
    const hint = el('div', 'vio-l2-side-hint');
    hint.textContent = text;
    body.appendChild(hint);
  }

  // ── Skeleton: bare spine + orb so there's never a flash of empty ──────
  function renderSkeletonSpine(canvas, company) {
    canvas.innerHTML = '';
    const w = spineEndX() + 240;
    const h = 520;
    const svg = svgEl('svg');
    svg.setAttribute('class', 'vio-l2-svg');
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);

    drawSpine(svg, company);
    drawOrb(svg, company);
    canvas.appendChild(svg);
  }

  // ── Full landscape render ─────────────────────────────────────────────
  function renderLandscape(canvas, company, detail) {
    canvas.innerHTML = '';

    // Figure out branch demand per stage and per direction so layout can
    // give every cluster the room it needs.
    const branches = computeBranches(detail);

    // Compute SVG height from the densest branch column.
    const aboveMax = Math.max(0, ...branches.above.map(b => b.totalHeight));
    const belowMax = Math.max(0, ...branches.below.map(b => b.totalHeight));
    const w = spineEndX() + 240;
    const h = Math.max(420, L.spineY + belowMax + 60 + 80) + Math.max(0, aboveMax - 60);
    // Recompute spine y so above-spine clusters fit on screen.
    const spineY = Math.max(L.spineY, aboveMax + 90);

    const svg = svgEl('svg');
    svg.setAttribute('class', 'vio-l2-svg');
    svg.setAttribute('width', w);
    svg.setAttribute('height', Math.max(h, spineY + belowMax + 100));
    svg.setAttribute('viewBox', `0 0 ${w} ${Math.max(h, spineY + belowMax + 100)}`);

    drawSpine(svg, company, spineY);
    branches.above.forEach(b => drawBranch(svg, b, spineY, 'above', detail));
    branches.below.forEach(b => drawBranch(svg, b, spineY, 'below', detail));
    drawOrb(svg, company, spineY);

    canvas.appendChild(svg);
  }

  // ── Spine + stage anchors ─────────────────────────────────────────────
  function drawSpine(svg, company, spineY = L.spineY) {
    const stageIdx = Math.max(0, Math.min(STAGES.length - 1, company.stage_index ?? 0));
    const liveX = L.spineX0 + stageIdx * L.stageGap;
    const endX  = spineEndX();

    // Future segment (faint dashed)
    if (liveX < endX) {
      const future = svgEl('line');
      future.setAttribute('class', 'vio-l2-spine-future');
      future.setAttribute('x1', liveX);
      future.setAttribute('x2', endX);
      future.setAttribute('y1', spineY);
      future.setAttribute('y2', spineY);
      svg.appendChild(future);
    }
    // Past segment (bright, coloured by stage_state)
    const past = svgEl('line');
    past.setAttribute('class', 'vio-l2-spine-past');
    past.setAttribute('data-stage-state', company.stage_state || 'healthy');
    past.setAttribute('x1', L.spineX0);
    past.setAttribute('x2', liveX);
    past.setAttribute('y1', spineY);
    past.setAttribute('y2', spineY);
    svg.appendChild(past);

    // Stage anchors (clickable; click pins side panel to that stage)
    STAGES.forEach((s, i) => {
      const cx = L.spineX0 + i * L.stageGap;
      const past = i <= stageIdx;
      const g = svgEl('g');
      g.setAttribute('class', past ? 'vio-l2-stage past' : 'vio-l2-stage future');
      g.setAttribute('data-stage', s.key);

      const c = svgEl('circle');
      c.setAttribute('cx', cx);
      c.setAttribute('cy', spineY);
      c.setAttribute('r', i === stageIdx ? L.stageR + 2 : L.stageR);
      g.appendChild(c);

      const lbl = svgEl('text');
      lbl.setAttribute('class', 'vio-l2-stage-label');
      lbl.setAttribute('x', cx);
      lbl.setAttribute('y', spineY + L.stageR + 18);
      lbl.setAttribute('text-anchor', 'middle');
      lbl.textContent = s.label;
      g.appendChild(lbl);

      g.addEventListener('click', () => openStageDetail(s, company));
      svg.appendChild(g);
    });
  }

  // ── Orb (anchored at far left of spine) ───────────────────────────────
  function drawOrb(svg, company, spineY = L.spineY) {
    const g = svgEl('g');
    g.setAttribute('class', 'vio-l2-orb-group');

    // limb from orb to spine
    const limb = svgEl('line');
    limb.setAttribute('class', 'vio-l2-orb-limb');
    limb.setAttribute('x1', L.orbCx + L.orbR);
    limb.setAttribute('y1', spineY);
    limb.setAttribute('x2', L.spineX0);
    limb.setAttribute('y2', spineY);
    g.appendChild(limb);

    const c = svgEl('circle');
    c.setAttribute('class', 'vio-l2-orb');
    c.setAttribute('data-stage-state', company.stage_state || 'healthy');
    c.setAttribute('cx', L.orbCx);
    c.setAttribute('cy', spineY);
    c.setAttribute('r', L.orbR);
    g.appendChild(c);

    const t = svgEl('text');
    t.setAttribute('class', 'vio-l2-orb-text');
    t.setAttribute('x', L.orbCx);
    t.setAttribute('y', spineY + 5);
    t.setAttribute('text-anchor', 'middle');
    t.textContent = company.initials || '?';
    g.appendChild(t);

    g.addEventListener('click', () => openOrbDetail(company));
    svg.appendChild(g);
  }

  // ── Branch composition ────────────────────────────────────────────────
  // Decide what branches to render, where they anchor, and how tall each
  // cluster will be. Bushiness is data-driven: empty categories don't render.
  function computeBranches(detail) {
    const above = [];
    const below = [];

    const ev    = detail.evidence || {};
    const prof  = ev.profile || {};
    const docs  = detail.uploaded_documents || [];
    const gen   = detail.generated_documents || [];
    const miss  = detail.missing_documents || [];
    const find  = detail.findings || [];
    const ictx  = detail.intake_context || {};
    const pay   = detail.payment || {};

    const stageX = key => L.spineX0 + STAGES.findIndex(s => s.key === key) * L.stageGap;

    // ── ABOVE the spine ────────────────────────────────────────────────
    // intake context (only if customer wrote something or it's urgent)
    if ((ictx.context && ictx.context.length) || ictx.urgent || ictx.deadline) {
      above.push(makeCluster('context', 'context', stageX('intake'), [
        ictx.urgent ? { kind: 'flag', label: 'urgent' } : null,
        ictx.deadline ? { kind: 'flag', label: `deadline ${ictx.deadline}` } : null,
        ictx.context ? { kind: 'note', label: truncate(ictx.context, 18), full: ictx.context } : null,
      ].filter(Boolean)));
    }

    // identifiers / extracted entities (anchored at evidence_mapping)
    const identifierLeaves = [];
    pushIdent(identifierLeaves, prof.technologies,           'tech');
    pushIdent(identifierLeaves, prof.compliance_references,  'compliance');
    pushIdent(identifierLeaves, prof.vendors,                'vendor');
    pushIdent(identifierLeaves, prof.company_names,          'company');
    if (identifierLeaves.length) {
      above.push(makeCluster('identifiers', 'identifiers', stageX('evidence_mapping'), identifierLeaves));
    }

    // service tier (anchored at approval) — when review_status indicates approval
    if (['approved', 'payment_sent', 'verified_complete', 'archived'].includes(detail.review_status)) {
      above.push(makeCluster('tier', 'service tier', stageX('approval'), [
        { kind: 'flag', label: detail.review_status.replace(/_/g, ' ') },
      ]));
    }

    // generated paperwork (anchored at conversion)
    if (gen.length) {
      above.push(makeCluster('generated', `generated (${gen.length})`, stageX('conversion'),
        gen.map(g => ({ kind: 'gen', label: truncate(g.name, 16), full: g.name, size: g.size_bytes }))));
    }

    // ── BELOW the spine ────────────────────────────────────────────────
    // documents uploaded (anchored at evidence_mapping)
    if (docs.length) {
      below.push(makeCluster('docs', `papers (${docs.length})`, stageX('evidence_mapping'),
        docs.map(d => ({
          kind: 'doc',
          label: truncate(d.original_name || d.stored_name || 'file', 16),
          status: d.status || 'on_disk',
          doc_type: d.document_type || '',
          full: d,
        }))));
    }

    // gaps / missing documents (anchored at evidence_mapping, below as well —
    // it's the same conceptual stage where they were detected)
    if (miss.length) {
      below.push(makeCluster('gaps', `missing (${miss.length})`,
        stageX('evidence_mapping') + 40,           // shifted right so it doesn't collide
        miss.map(m => ({
          kind: 'gap',
          label: truncate(m.label || 'gap', 16),
          priority: m.priority || 'medium',
          full: m,
        }))));
    }

    // findings (anchored at validation)
    if (find.length) {
      below.push(makeCluster('findings', `findings (${find.length})`, stageX('validation'),
        find.map(f => ({
          kind: 'finding',
          label: truncate(f.message || f.code || 'finding', 16),
          severity: f.severity || 'info',
          full: f,
        }))));
    }

    // payment (anchored at approval)
    if (pay && (pay.link || pay.amount || pay.link_sent_utc || pay.paid)) {
      const paidLabel = pay.paid ? 'paid' : (pay.link ? 'link sent' : 'pending');
      below.push(makeCluster('payment', 'payment', stageX('approval'), [
        { kind: 'payment', label: paidLabel, full: pay },
      ]));
    } else if (['approved', 'payment_sent', 'verified_complete', 'archived'].includes(detail.review_status)) {
      below.push(makeCluster('payment', 'payment', stageX('approval'), [
        { kind: 'payment', label: 'awaiting record', full: pay },
      ]));
    }

    // kickoff / project (anchored at conversion)
    if (detail.project_id) {
      below.push(makeCluster('project', 'project', stageX('conversion'), [
        { kind: 'project', label: truncate(detail.project_id, 14), full: { project_id: detail.project_id } },
      ]));
    }

    return { above, below };
  }

  function pushIdent(into, list, kind) {
    if (!Array.isArray(list)) return;
    list.slice(0, 8).forEach(item => {
      if (item == null) return;
      const label = typeof item === 'string'
        ? item
        : (item.value || item.name || item.label || String(item));
      if (!label) return;
      into.push({ kind: 'ident', sub: kind, label: truncate(label, 14), full: item });
    });
  }

  function makeCluster(id, title, anchorX, leaves) {
    // Compute cluster footprint so the layout engine can give it room.
    const rows = Math.ceil(leaves.length / L.leavesPerRow);
    const totalHeight = 36 /* title */ + rows * L.branchSpacing;
    return { id, title, anchorX, leaves, totalHeight, rows };
  }

  // ── Render one branch cluster ─────────────────────────────────────────
  function drawBranch(svg, cluster, spineY, side, detail) {
    const sign = side === 'above' ? -1 : +1;
    const titleY = spineY + sign * 40;
    const baseY  = spineY + sign * 60;

    // Limb from spine to title pivot
    const limb = svgEl('path');
    const cp1x = cluster.anchorX;
    const cp1y = spineY + sign * 8;
    const cp2x = cluster.anchorX;
    const cp2y = spineY + sign * 32;
    limb.setAttribute('d', `M ${cluster.anchorX} ${spineY} Q ${cp1x} ${cp1y}, ${cp2x} ${cp2y} T ${cluster.anchorX} ${titleY}`);
    limb.setAttribute('class', 'vio-l2-branch-limb');
    limb.setAttribute('data-cluster', cluster.id);
    svg.appendChild(limb);

    // Cluster title text
    const titleText = svgEl('text');
    titleText.setAttribute('class', 'vio-l2-branch-title');
    titleText.setAttribute('x', cluster.anchorX);
    titleText.setAttribute('y', titleY + (side === 'above' ? -6 : 12));
    titleText.setAttribute('text-anchor', 'middle');
    titleText.textContent = cluster.title;
    svg.appendChild(titleText);

    // Leaves laid out in rows of L.leavesPerRow, growing away from spine
    cluster.leaves.forEach((leaf, i) => {
      const row = Math.floor(i / L.leavesPerRow);
      const col = i % L.leavesPerRow;
      const rowCount = Math.min(L.leavesPerRow, cluster.leaves.length - row * L.leavesPerRow);
      const rowWidth = (rowCount - 1) * (L.leafW + L.leafGap);
      const x = cluster.anchorX - rowWidth / 2 + col * (L.leafW + L.leafGap);
      const y = baseY + sign * (row * L.branchSpacing) + (sign === -1 ? -L.leafH : 6);
      drawLeaf(svg, leaf, x, y, cluster, detail);
    });
  }

  // ── Render one leaf ───────────────────────────────────────────────────
  function drawLeaf(svg, leaf, x, y, cluster, detail) {
    const g = svgEl('g');
    g.setAttribute('class', `vio-l2-leaf vio-l2-leaf-${leaf.kind}`);
    g.setAttribute('data-kind', leaf.kind);
    if (leaf.severity) g.setAttribute('data-severity', leaf.severity);
    if (leaf.priority) g.setAttribute('data-priority', leaf.priority);
    if (leaf.status)   g.setAttribute('data-status', leaf.status);
    if (leaf.sub)      g.setAttribute('data-sub', leaf.sub);

    // Shape (by kind) — each kind has a distinct silhouette
    const shape = drawLeafShape(g, leaf, x, y);
    if (shape) shape.setAttribute('class', 'vio-l2-leaf-shape');

    // Label inside / below
    const t = svgEl('text');
    t.setAttribute('class', 'vio-l2-leaf-text');
    t.setAttribute('x', x + L.leafW / 2);
    t.setAttribute('y', y + L.leafH / 2 + 4);
    t.setAttribute('text-anchor', 'middle');
    t.textContent = leaf.label;
    g.appendChild(t);

    // Hover + click
    g.addEventListener('click', e => {
      e.stopPropagation();
      openLeafDetail(leaf, cluster, detail);
    });

    svg.appendChild(g);
  }

  function drawLeafShape(parent, leaf, x, y) {
    const w = L.leafW;
    const h = L.leafH;

    switch (leaf.kind) {
      case 'doc': {
        // Page with corner fold
        const r = svgEl('path');
        const corner = 10;
        r.setAttribute('d',
          `M ${x} ${y} L ${x + w - corner} ${y} L ${x + w} ${y + corner} L ${x + w} ${y + h} L ${x} ${y + h} Z`
        );
        parent.appendChild(r);
        const fold = svgEl('path');
        fold.setAttribute('class', 'vio-l2-leaf-fold');
        fold.setAttribute('d',
          `M ${x + w - corner} ${y} L ${x + w - corner} ${y + corner} L ${x + w} ${y + corner}`
        );
        parent.appendChild(fold);
        return r;
      }
      case 'gen': {
        // Page with double border (machine-generated)
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', 2);
        parent.appendChild(r);
        const inner = svgEl('rect');
        inner.setAttribute('class', 'vio-l2-leaf-inner');
        inner.setAttribute('x', x + 3); inner.setAttribute('y', y + 3);
        inner.setAttribute('width', w - 6); inner.setAttribute('height', h - 6);
        inner.setAttribute('rx', 1);
        parent.appendChild(inner);
        return r;
      }
      case 'gap': {
        // Dashed empty page — "missing"
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', 2);
        r.setAttribute('stroke-dasharray', '4 3');
        r.setAttribute('fill', 'none');
        parent.appendChild(r);
        return r;
      }
      case 'finding': {
        // Triangle warning
        const t = svgEl('polygon');
        const midX = x + w / 2;
        t.setAttribute('points',
          `${midX},${y + 3} ${x + w - 3},${y + h - 3} ${x + 3},${y + h - 3}`
        );
        parent.appendChild(t);
        return t;
      }
      case 'ident': {
        // Rounded pill (tag)
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', h / 2);
        parent.appendChild(r);
        return r;
      }
      case 'payment': {
        // Card with magnetic band
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', 3);
        parent.appendChild(r);
        const band = svgEl('rect');
        band.setAttribute('class', 'vio-l2-leaf-card-band');
        band.setAttribute('x', x); band.setAttribute('y', y + 8);
        band.setAttribute('width', w); band.setAttribute('height', 5);
        parent.appendChild(band);
        return r;
      }
      case 'project': {
        // Hexagon (project anchor)
        const cx = x + w / 2;
        const cy = y + h / 2;
        const rr = Math.min(w, h) / 2 - 2;
        const points = Array.from({ length: 6 }, (_, i) => {
          const a = (Math.PI / 180) * (60 * i - 30);
          return `${cx + rr * Math.cos(a)},${cy + rr * Math.sin(a)}`;
        }).join(' ');
        const poly = svgEl('polygon');
        poly.setAttribute('points', points);
        parent.appendChild(poly);
        return poly;
      }
      case 'flag': {
        // Pennant — small marker
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', 3);
        parent.appendChild(r);
        return r;
      }
      case 'note':
      default: {
        // Speech-bubble / note
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', 4);
        parent.appendChild(r);
        return r;
      }
    }
  }

  // ── Side panel renderers ──────────────────────────────────────────────
  function renderOverview(side, company, detail) {
    const body = side.querySelector('#vio-l2-side-body');
    const title = side.querySelector('#vio-l2-side-title');
    const back  = side.querySelector('#vio-l2-side-back');
    if (!body || !title) return;
    body.innerHTML = '';
    title.textContent = 'overview';
    if (back) back.hidden = true;

    const stage = STAGES[company.stage_index ?? 0]?.label || 'intake';
    body.appendChild(kv('stage', `${stage} · ${(company.stage_state || 'healthy').replace(/_/g, ' ')}`));
    body.appendChild(kv('days in stage', `${company.days_in_stage ?? 0}d`));
    body.appendChild(kv('age', `${detail.age_hours ?? 0}h`));
    body.appendChild(kv('review status', detail.review_status || '—'));
    body.appendChild(kv('intake id', detail.intake_id || '—', 'mono'));
    if (detail.project_id) body.appendChild(kv('project id', detail.project_id, 'mono'));

    if (detail.bottleneck) {
      body.appendChild(sectionTitle('bottleneck'));
      const bn = el('div', 'vio-l2-side-bottleneck');
      bn.textContent = detail.bottleneck;
      body.appendChild(bn);
    }

    const acts = detail.next_actions || [];
    if (acts.length) {
      body.appendChild(sectionTitle('next actions'));
      acts.forEach(a => {
        const r = el('div', 'vio-l2-side-action');
        r.textContent = '→ ' + a;
        body.appendChild(r);
      });
    }

    body.appendChild(sectionTitle('cockpit'));
    const link = el('a', 'vio-l2-side-link');
    link.href = '/ui/control.html';
    link.textContent = 'open cockpit for actions →';
    body.appendChild(link);
  }

  function openLeafDetail(leaf, cluster, detail) {
    const side = document.getElementById('vio-l2-side');
    const body = side?.querySelector('#vio-l2-side-body');
    const title = side?.querySelector('#vio-l2-side-title');
    const back  = side?.querySelector('#vio-l2-side-back');
    if (!body || !title) return;
    body.innerHTML = '';
    title.textContent = `${cluster.title} · ${leaf.label}`;
    if (back) back.hidden = false;

    const f = leaf.full || {};

    switch (leaf.kind) {
      case 'doc':
        body.appendChild(kv('file', f.original_name || f.stored_name || '—'));
        body.appendChild(kv('type', f.document_type || '—'));
        body.appendChild(kv('status', f.status || '—'));
        body.appendChild(kv('size', f.size_human || formatBytes(f.size_bytes)));
        if (f.classification_confidence != null) {
          body.appendChild(kv('confidence', `${Math.round((f.classification_confidence || 0) * 100)}%`));
        }
        if (f.sha256_short) body.appendChild(kv('sha256', f.sha256_short, 'mono'));
        if (f.access_error) {
          const err = el('div', 'vio-l2-side-error');
          err.textContent = f.access_error;
          body.appendChild(err);
        }
        if (f.view_url || f.download_url) {
          body.appendChild(sectionTitle('actions'));
          if (f.view_url) body.appendChild(linkBtn('view in new tab', f.view_url, true));
          if (f.download_url) body.appendChild(linkBtn('download', f.download_url, false));
        }
        break;

      case 'gen':
        body.appendChild(kv('file', f.full || f.name || '—'));
        body.appendChild(kv('size', formatBytes(leaf.size || 0)));
        body.appendChild(kv('kind', 'auto-generated'));
        break;

      case 'gap':
        body.appendChild(kv('label', f.label || '—'));
        body.appendChild(kv('priority', (f.priority || 'medium').toUpperCase()));
        if (f.explanation) {
          body.appendChild(sectionTitle('why this matters'));
          const p = el('div', 'vio-l2-side-prose');
          p.textContent = f.explanation;
          body.appendChild(p);
        }
        if (f.example_url) body.appendChild(linkBtn('example', f.example_url, true));
        if (f.retrieval_help_url) body.appendChild(linkBtn('how to retrieve', f.retrieval_help_url, true));
        break;

      case 'finding':
        body.appendChild(kv('severity', (f.severity || 'info').toUpperCase()));
        body.appendChild(kv('code', f.code || '—', 'mono'));
        body.appendChild(sectionTitle('message'));
        {
          const msg = el('div', 'vio-l2-side-prose');
          msg.textContent = f.message || '—';
          body.appendChild(msg);
        }
        if (f.hint) {
          body.appendChild(sectionTitle('hint'));
          const h = el('div', 'vio-l2-side-prose');
          h.textContent = f.hint;
          body.appendChild(h);
        }
        break;

      case 'ident': {
        const value = typeof f === 'string' ? f : (f.value || f.name || leaf.label);
        body.appendChild(kv('value', value));
        body.appendChild(kv('kind', leaf.sub || 'identifier'));
        if (typeof f === 'object') {
          if (f.confidence != null)  body.appendChild(kv('confidence', `${Math.round((f.confidence || 0) * 100)}%`));
          if (f.status)              body.appendChild(kv('status', f.status));
          if (f.first_seen)          body.appendChild(kv('first seen', f.first_seen, 'mono'));
        }
        break;
      }

      case 'payment':
        body.appendChild(kv('paid', f.paid ? 'yes' : 'no'));
        if (f.amount)        body.appendChild(kv('amount', String(f.amount)));
        if (f.product_id)    body.appendChild(kv('product', f.product_id));
        if (f.link_sent_utc) body.appendChild(kv('link sent', f.link_sent_utc, 'mono'));
        if (f.link)          body.appendChild(linkBtn('open payment link', f.link, true));
        break;

      case 'project':
        body.appendChild(kv('project id', f.project_id || '—', 'mono'));
        body.appendChild(sectionTitle('actions'));
        body.appendChild(linkBtn('open cockpit', '/ui/control.html', true));
        break;

      case 'flag':
        body.appendChild(kv('flag', leaf.label));
        break;

      case 'note':
      default:
        body.appendChild(sectionTitle(leaf.label));
        {
          const p = el('div', 'vio-l2-side-prose');
          p.textContent = (typeof f === 'string') ? f : (f.full || leaf.label);
          body.appendChild(p);
        }
        break;
    }
  }

  function openOrbDetail(company) {
    if (_activeDetail) renderOverview(document.getElementById('vio-l2-side'), company, _activeDetail);
  }

  function openStageDetail(stage, company) {
    const side = document.getElementById('vio-l2-side');
    const body = side?.querySelector('#vio-l2-side-body');
    const title = side?.querySelector('#vio-l2-side-title');
    const back  = side?.querySelector('#vio-l2-side-back');
    if (!body || !title) return;
    body.innerHTML = '';
    title.textContent = `stage · ${stage.label}`;
    if (back) back.hidden = false;

    const currentIdx = company.stage_index ?? 0;
    const idx = STAGES.findIndex(s => s.key === stage.key);
    let position;
    if (idx < currentIdx) position = 'completed';
    else if (idx === currentIdx) position = `current — ${(company.stage_state || 'healthy').replace(/_/g, ' ')}`;
    else position = 'future';

    body.appendChild(kv('position', position));
    body.appendChild(kv('stage key', stage.key, 'mono'));
    body.appendChild(sectionTitle('what happens here'));
    const p = el('div', 'vio-l2-side-prose');
    p.textContent = STAGE_DESCRIPTIONS[stage.key] || '';
    body.appendChild(p);
  }

  const STAGE_DESCRIPTIONS = {
    intake:           'Customer submits company name, contact, and uploads first files. The intake record is created and a magic-link session is issued.',
    classification:   'Auto-classification reads each file and routes the intake into a primary compliance category (CMMC, ISO, DFARS, ITAR…).',
    validation:       'Each file passes the proof gate (hash, durable storage, chain of custody) before it can be claimed as received.',
    evidence_mapping: 'Evidence intelligence extracts entities, identifies technologies and compliance references, and flags gaps that need customer follow-up.',
    review:           'Operator reviews what was uploaded and what is missing; selects the right service tier.',
    approval:         'Service tier is locked, payment link is dispatched, and the engagement waits on the customer to pay.',
    conversion:       'Payment received. Project kicks off, generated paperwork is produced, and the engagement is delivered.',
  };

  // ── DOM helpers ───────────────────────────────────────────────────────
  function el(tag, cls) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    return n;
  }
  function svgEl(tag) {
    return document.createElementNS(SVG_NS, tag);
  }
  function kv(k, v, cls) {
    const r = el('div', 'vio-l2-kv');
    const ke = el('span', 'vio-l2-kv-k');
    ke.textContent = k;
    const ve = el('span', 'vio-l2-kv-v' + (cls ? ' ' + cls : ''));
    ve.textContent = v == null ? '—' : String(v);
    r.appendChild(ke);
    r.appendChild(ve);
    return r;
  }
  function sectionTitle(text) {
    const s = el('div', 'vio-l2-side-section');
    s.textContent = text;
    return s;
  }
  function linkBtn(text, url, external) {
    const a = el('a', 'vio-l2-side-btn');
    a.href = url;
    if (external) { a.target = '_blank'; a.rel = 'noopener'; }
    a.textContent = text;
    return a;
  }
  function truncate(s, n) {
    s = String(s || '');
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
  }
  function formatBytes(n) {
    if (n == null || isNaN(n)) return '—';
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
    return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  // ── ESC to close ──────────────────────────────────────────────────────
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && _activeCompany) closeLevel2();
  });
})(window);
