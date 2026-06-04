/* ══════════════════════════════════════════════════════════════════════════════
   VIO — Level 2 (Visual Intelligent Landscape)

   When an operator clicks a company's Level 1 trace, that single line expands
   into an immersive horizontal landscape:

       [ORB]──●──────●──────●──────●──────●──────●──────●
       intake class. valid. evid.  review approv conv.
              │      │      │      │      │      │      │
              └ context     │      │      │      │      │
                     └ category    │      │      │      │
              ┐ identifiers ┘      │      │      │      │
                                   ├─ docs uploaded     │
                                   ├─ docs missing      │
                                   ├─ confirmation      │
                                   ├─ findings          │
                                                ├─ payment
                                                       └─ project
                                                       └─ generated

   Doctrine (docs/VIO_DOCTRINE.md):
     · Linear — orb on left, spine going right. NOT radial.
     · Branches sprout PERPENDICULAR from the spine.
     · Bushiness = real complexity.  Clean companies stay a clean spine.
     · Every visual element is clickable → recursive detail in side panel.
     · Stillness baseline; only `waiting_client` ever breathes.

   Side panel navigation:
     · A frame stack lets the operator drill from a leaf into its referenced
       data (a finding → its source file → that file's extracted entities →
       a specific entity's raw context).
     · Back button pops one frame; never just closes the whole panel.
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
    spineY:      260,
    spineX0:     130,
    stageGap:    180,
    stageR:      9,
    branchSpacing: 60,
    leafW:       66,
    leafH:       38,
    leafGap:     14,
    leavesPerRow: 4,
    // Collision-avoidance: minimum centre-to-centre x distance between
    // two clusters on the same side.
    clusterMinGap: 90,
  };

  function spineEndX() {
    return L.spineX0 + (STAGES.length - 1) * L.stageGap;
  }

  // ── Public entry ──────────────────────────────────────────────────────
  global.VioLevel2 = {
    open:  openLevel2,
    close: closeLevel2,
  };

  // ── State ─────────────────────────────────────────────────────────────
  let _activeCompany = null;
  let _activeDetail  = null;
  let _frameStack    = [];     // [{title, render(body)}]
  let _xref          = null;   // cross-reference index, built at open

  // ─────────────────────────────────────────────────────────────────────
  // OPEN / CLOSE
  // ─────────────────────────────────────────────────────────────────────
  async function openLevel2(company) {
    _activeCompany = company;
    _frameStack    = [];
    _xref          = null;

    const mount = document.getElementById('vio-level2-mount');
    if (!mount) return;
    mount.innerHTML = '';
    mount.removeAttribute('hidden');
    document.body.style.overflow = 'hidden';

    mount.appendChild(buildHeader(company));
    const canvas    = buildCanvas();      mount.appendChild(canvas);
    const sidepanel = buildSidePanel();   mount.appendChild(sidepanel);

    renderSkeletonSpine(canvas, company);
    showSideHint('reading the field…');

    const intakeKey = company.intake_id || company.row_id || company.project_id;
    if (!intakeKey) {
      showSideHint('no intake id — nothing to render');
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
      _xref = buildXref(detail);
      renderLandscape(canvas, company, detail);
      resetFrames(overviewFrame(company, detail));
    } catch (err) {
      showSideHint('could not load landscape: ' + err.message);
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
    _frameStack    = [];
    _xref          = null;
  }

  // ─────────────────────────────────────────────────────────────────────
  // CROSS-REFERENCE INDEX
  // Built once per open so drill-downs can answer "what other things
  // reference this thing?" without re-walking the payload each time.
  // ─────────────────────────────────────────────────────────────────────
  function buildXref(detail) {
    const xr = {
      docsByStored:   new Map(),
      docsByOriginal: new Map(),
      docsBySha:      new Map(),
      docByLabel:     new Map(),    // label-prefix → first matching doc
      identsByValue:  new Map(),    // value (lower) → [{kind, value, item}]
      findingsByCode: new Map(),    // code → [findings]
    };

    (detail.uploaded_documents || []).forEach(d => {
      if (d.stored_name)    xr.docsByStored.set(d.stored_name, d);
      if (d.original_name)  xr.docsByOriginal.set(d.original_name, d);
      if (d.sha256)         xr.docsBySha.set(d.sha256, d);
      if (d.original_name)  xr.docByLabel.set(d.original_name.toLowerCase(), d);
      if (d.stored_name)    xr.docByLabel.set(d.stored_name.toLowerCase(),   d);
    });

    const prof = (detail.evidence && detail.evidence.profile) || {};
    [['technologies', 'tech'], ['compliance_references', 'compliance'],
     ['vendors', 'vendor'],     ['company_names', 'company']].forEach(([k, kind]) => {
      const list = Array.isArray(prof[k]) ? prof[k] : [];
      list.forEach(item => {
        const value = (typeof item === 'string'
          ? item
          : (item && (item.value || item.name || item.label)));
        if (!value) return;
        const key = String(value).toLowerCase();
        if (!xr.identsByValue.has(key)) xr.identsByValue.set(key, []);
        xr.identsByValue.get(key).push({ kind, value, item });
      });
    });

    (detail.findings || []).forEach(f => {
      const code = f.code || 'unknown';
      if (!xr.findingsByCode.has(code)) xr.findingsByCode.set(code, []);
      xr.findingsByCode.get(code).push(f);
    });

    return xr;
  }

  // Try to resolve a free-text label/filename to a known document.
  function findRelatedDoc(text) {
    if (!_xref || !text) return null;
    const t = String(text).toLowerCase();
    if (_xref.docByLabel.has(t)) return _xref.docByLabel.get(t);
    for (const [key, doc] of _xref.docByLabel.entries()) {
      if (t.includes(key) || key.includes(t)) return doc;
    }
    return null;
  }

  // ─────────────────────────────────────────────────────────────────────
  // HEADER · CANVAS · SIDE PANEL  (DOM scaffolding)
  // ─────────────────────────────────────────────────────────────────────
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

  function buildCanvas() {
    const c = el('div', 'vio-l2-canvas');
    c.id = 'vio-l2-canvas';
    return c;
  }

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
    backBtn.addEventListener('click', popFrame);
    header.appendChild(backBtn);
    s.appendChild(header);

    const body = el('div', 'vio-l2-side-body');
    body.id    = 'vio-l2-side-body';
    s.appendChild(body);

    return s;
  }

  // ─────────────────────────────────────────────────────────────────────
  // SIDE-PANEL FRAME STACK
  // Each "frame" is a logical screen. `pushFrame` drills deeper;
  // `popFrame` returns to the previous frame. The back button is hidden
  // when the stack is at root depth (1).
  // ─────────────────────────────────────────────────────────────────────
  function resetFrames(rootFrame) {
    _frameStack = [];
    pushFrame(rootFrame);
  }

  function pushFrame(frame) {
    if (!frame || typeof frame.render !== 'function') return;
    _frameStack.push(frame);
    paintTopFrame();
  }

  function popFrame() {
    if (_frameStack.length > 1) _frameStack.pop();
    paintTopFrame();
  }

  function paintTopFrame() {
    const body  = document.getElementById('vio-l2-side-body');
    const title = document.getElementById('vio-l2-side-title');
    const back  = document.getElementById('vio-l2-side-back');
    if (!body || !title) return;
    const top = _frameStack[_frameStack.length - 1];
    if (!top) return;
    body.innerHTML = '';
    title.textContent = top.title || '';
    if (back) back.hidden = _frameStack.length <= 1;
    try { top.render(body); }
    catch (err) {
      console.error('[VIO L2] frame render failed:', err);
      body.appendChild(asProse('frame render failed: ' + err.message));
    }
  }

  function showSideHint(text) {
    resetFrames({
      title: 'overview',
      render: body => body.appendChild(asHint(text)),
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // SKELETON  +  FULL LANDSCAPE RENDER
  // ─────────────────────────────────────────────────────────────────────
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

  function renderLandscape(canvas, company, detail) {
    canvas.innerHTML = '';

    const branches = computeBranches(detail);
    // Apply collision avoidance per side so dense companies stay legible.
    spreadClusters(branches.above);
    spreadClusters(branches.below);

    const aboveMax = Math.max(0, ...branches.above.map(b => b.totalHeight));
    const belowMax = Math.max(0, ...branches.below.map(b => b.totalHeight));
    const spineY = Math.max(L.spineY, aboveMax + 90);
    // Make sure the right-most cluster fits inside the viewBox.
    const maxAnchorX = Math.max(
      spineEndX(),
      ...branches.above.map(b => b.anchorX),
      ...branches.below.map(b => b.anchorX),
    );
    const w = maxAnchorX + 240;
    const h = Math.max(420, spineY + belowMax + 100);

    const svg = svgEl('svg');
    svg.setAttribute('class', 'vio-l2-svg');
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);

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

    if (liveX < endX) {
      const future = svgEl('line');
      future.setAttribute('class', 'vio-l2-spine-future');
      future.setAttribute('x1', liveX);
      future.setAttribute('x2', endX);
      future.setAttribute('y1', spineY);
      future.setAttribute('y2', spineY);
      svg.appendChild(future);
    }
    const past = svgEl('line');
    past.setAttribute('class', 'vio-l2-spine-past');
    past.setAttribute('data-stage-state', company.stage_state || 'healthy');
    past.setAttribute('x1', L.spineX0);
    past.setAttribute('x2', liveX);
    past.setAttribute('y1', spineY);
    past.setAttribute('y2', spineY);
    svg.appendChild(past);

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

      g.addEventListener('click', () => pushFrame(stageFrame(s, company, _activeDetail)));
      svg.appendChild(g);
    });
  }

  // ── Orb ───────────────────────────────────────────────────────────────
  function drawOrb(svg, company, spineY = L.spineY) {
    const g = svgEl('g');
    g.setAttribute('class', 'vio-l2-orb-group');

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

    g.addEventListener('click', () => resetFrames(overviewFrame(company, _activeDetail)));
    svg.appendChild(g);
  }

  // ─────────────────────────────────────────────────────────────────────
  // BRANCH COMPOSITION  +  COLLISION AVOIDANCE
  // ─────────────────────────────────────────────────────────────────────
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
    const cls   = detail.classification || {};
    const conf  = detail.confirmation_needed || [];

    const stageX = key => L.spineX0 + STAGES.findIndex(s => s.key === key) * L.stageGap;

    // ── ABOVE the spine ────────────────────────────────────────────────
    if ((ictx.context && ictx.context.length) || ictx.urgent || ictx.deadline) {
      above.push(makeCluster('context', 'context', stageX('intake'), [
        ictx.urgent ? { kind: 'flag', label: 'urgent' } : null,
        ictx.deadline ? { kind: 'flag', label: `deadline ${ictx.deadline}` } : null,
        ictx.context ? { kind: 'note', label: truncate(ictx.context, 18), full: ictx.context } : null,
      ].filter(Boolean)));
    }

    if (cls.primary_category) {
      const leaves = [{ kind: 'flag', label: truncate(cls.primary_category, 16), full: cls.primary_category }];
      if (cls.secondary_category) leaves.push({ kind: 'flag', label: truncate(cls.secondary_category, 16), full: cls.secondary_category });
      if (cls.scope_label)        leaves.push({ kind: 'note', label: truncate(cls.scope_label, 14), full: cls.scope_label });
      above.push(makeCluster('category', 'category', stageX('classification'), leaves));
    }

    const identifierLeaves = [];
    pushIdent(identifierLeaves, prof.technologies,           'tech');
    pushIdent(identifierLeaves, prof.compliance_references,  'compliance');
    pushIdent(identifierLeaves, prof.vendors,                'vendor');
    pushIdent(identifierLeaves, prof.company_names,          'company');
    if (identifierLeaves.length) {
      above.push(makeCluster('identifiers', `identifiers (${identifierLeaves.length})`,
        stageX('evidence_mapping'), identifierLeaves));
    }

    if (['approved', 'payment_sent', 'verified_complete', 'archived'].includes(detail.review_status)) {
      above.push(makeCluster('tier', 'service tier', stageX('approval'), [
        { kind: 'flag', label: detail.review_status.replace(/_/g, ' ') },
      ]));
    }

    if (gen.length) {
      above.push(makeCluster('generated', `generated (${gen.length})`, stageX('conversion'),
        gen.map(g => ({ kind: 'gen', label: truncate(g.name, 16), full: g.name, size: g.size_bytes }))));
    }

    // ── BELOW the spine ────────────────────────────────────────────────
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

    if (miss.length) {
      below.push(makeCluster('gaps', `missing (${miss.length})`, stageX('evidence_mapping'),
        miss.map(m => ({
          kind: 'gap',
          label: truncate(m.label || 'gap', 16),
          priority: m.priority || 'medium',
          full: m,
        }))));
    }

    if (conf.length) {
      below.push(makeCluster('confirmation', `confirmation (${conf.length})`,
        stageX('evidence_mapping'),
        conf.map(c => ({
          kind: 'note',
          label: truncate(c.field || 'field', 14),
          full: c,
        }))));
    }

    if (find.length) {
      below.push(makeCluster('findings', `findings (${find.length})`, stageX('validation'),
        find.map(f => ({
          kind: 'finding',
          label: truncate(f.message || f.code || 'finding', 16),
          severity: f.severity || 'info',
          full: f,
        }))));
    }

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
    const rows = Math.ceil(leaves.length / L.leavesPerRow);
    const totalHeight = 36 + rows * L.branchSpacing;
    const widthLeaves = Math.min(leaves.length, L.leavesPerRow);
    const totalWidth  = widthLeaves * L.leafW + (widthLeaves - 1) * L.leafGap;
    return { id, title, anchorX, leaves, totalHeight, totalWidth, rows };
  }

  // Spread clusters that share too-tight an anchor along the spine so
  // their leaf rectangles don't overlap. Preserves relative ordering.
  function spreadClusters(clusters) {
    if (!clusters || clusters.length < 2) return;
    clusters.sort((a, b) => a.anchorX - b.anchorX);
    for (let i = 1; i < clusters.length; i++) {
      const prev = clusters[i - 1];
      const need = Math.max(L.clusterMinGap,
        (prev.totalWidth / 2 + clusters[i].totalWidth / 2 + 16));
      if (clusters[i].anchorX - prev.anchorX < need) {
        clusters[i].anchorX = prev.anchorX + need;
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────
  // BRANCH + LEAF RENDERING
  // ─────────────────────────────────────────────────────────────────────
  function drawBranch(svg, cluster, spineY, side, detail) {
    const sign = side === 'above' ? -1 : +1;
    const titleY = spineY + sign * 40;
    const baseY  = spineY + sign * 60;

    const limb = svgEl('path');
    const cp1x = cluster.anchorX, cp1y = spineY + sign * 8;
    const cp2x = cluster.anchorX, cp2y = spineY + sign * 32;
    limb.setAttribute('d',
      `M ${cluster.anchorX} ${spineY} Q ${cp1x} ${cp1y}, ${cp2x} ${cp2y} T ${cluster.anchorX} ${titleY}`);
    limb.setAttribute('class', 'vio-l2-branch-limb');
    limb.setAttribute('data-cluster', cluster.id);
    svg.appendChild(limb);

    const titleText = svgEl('text');
    titleText.setAttribute('class', 'vio-l2-branch-title');
    titleText.setAttribute('x', cluster.anchorX);
    titleText.setAttribute('y', titleY + (side === 'above' ? -6 : 12));
    titleText.setAttribute('text-anchor', 'middle');
    titleText.textContent = cluster.title;
    svg.appendChild(titleText);

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

  function drawLeaf(svg, leaf, x, y, cluster, detail) {
    const g = svgEl('g');
    g.setAttribute('class', `vio-l2-leaf vio-l2-leaf-${leaf.kind}`);
    g.setAttribute('data-kind', leaf.kind);
    if (leaf.severity) g.setAttribute('data-severity', leaf.severity);
    if (leaf.priority) g.setAttribute('data-priority', leaf.priority);
    if (leaf.status)   g.setAttribute('data-status', leaf.status);
    if (leaf.sub)      g.setAttribute('data-sub', leaf.sub);

    const shape = drawLeafShape(g, leaf, x, y);
    if (shape) shape.setAttribute('class', 'vio-l2-leaf-shape');

    const t = svgEl('text');
    t.setAttribute('class', 'vio-l2-leaf-text');
    t.setAttribute('x', x + L.leafW / 2);
    t.setAttribute('y', y + L.leafH / 2 + 4);
    t.setAttribute('text-anchor', 'middle');
    t.textContent = leaf.label;
    g.appendChild(t);

    g.addEventListener('click', e => {
      e.stopPropagation();
      pushFrame(leafFrame(leaf, cluster, detail));
    });
    svg.appendChild(g);
  }

  function drawLeafShape(parent, leaf, x, y) {
    const w = L.leafW, h = L.leafH;
    switch (leaf.kind) {
      case 'doc': {
        const r = svgEl('path');
        const corner = 10;
        r.setAttribute('d',
          `M ${x} ${y} L ${x + w - corner} ${y} L ${x + w} ${y + corner} L ${x + w} ${y + h} L ${x} ${y + h} Z`);
        parent.appendChild(r);
        const fold = svgEl('path');
        fold.setAttribute('class', 'vio-l2-leaf-fold');
        fold.setAttribute('d',
          `M ${x + w - corner} ${y} L ${x + w - corner} ${y + corner} L ${x + w} ${y + corner}`);
        parent.appendChild(fold);
        return r;
      }
      case 'gen': {
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
        const t = svgEl('polygon');
        const midX = x + w / 2;
        t.setAttribute('points',
          `${midX},${y + 3} ${x + w - 3},${y + h - 3} ${x + 3},${y + h - 3}`);
        parent.appendChild(t);
        return t;
      }
      case 'ident': {
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', h / 2);
        parent.appendChild(r);
        return r;
      }
      case 'payment': {
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
        const cx = x + w / 2, cy = y + h / 2;
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
      case 'flag':
      case 'note':
      default: {
        const r = svgEl('rect');
        r.setAttribute('x', x); r.setAttribute('y', y);
        r.setAttribute('width', w); r.setAttribute('height', h);
        r.setAttribute('rx', leaf.kind === 'flag' ? 3 : 4);
        parent.appendChild(r);
        return r;
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────
  // FRAMES  (root + per-leaf drill-down + per-stage drill-down)
  // ─────────────────────────────────────────────────────────────────────
  function overviewFrame(company, detail) {
    return {
      title: 'overview',
      render: body => {
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
        // Quick navigation: jump straight to the biggest data buckets
        const navTargets = [
          { label: `papers (${(detail.uploaded_documents || []).length})`,
            disabled: !(detail.uploaded_documents || []).length,
            onClick: () => pushFrame(listFrame('papers', detail.uploaded_documents || [],
              d => ({ kind: 'doc', label: d.original_name || d.stored_name, full: d }),
              null, detail)) },
          { label: `missing (${(detail.missing_documents || []).length})`,
            disabled: !(detail.missing_documents || []).length,
            onClick: () => pushFrame(listFrame('missing', detail.missing_documents || [],
              m => ({ kind: 'gap', label: m.label, priority: m.priority, full: m }),
              null, detail)) },
          { label: `findings (${(detail.findings || []).length})`,
            disabled: !(detail.findings || []).length,
            onClick: () => pushFrame(listFrame('findings', detail.findings || [],
              f => ({ kind: 'finding', label: f.message || f.code,
                      severity: f.severity, full: f }),
              null, detail)) },
        ];
        body.appendChild(sectionTitle('explore'));
        navTargets.forEach(t => {
          if (t.disabled) return;
          const a = el('button', 'vio-l2-side-btn');
          a.textContent = t.label + ' →';
          a.addEventListener('click', t.onClick);
          body.appendChild(a);
        });

        body.appendChild(sectionTitle('cockpit'));
        const link = el('a', 'vio-l2-side-link');
        link.href = '/ui/control.html';
        link.textContent = 'open cockpit for actions →';
        body.appendChild(link);
      },
    };
  }

  // A generic "list of items" frame — each row is clickable into a leaf frame.
  function listFrame(title, items, leafShaper, parentCluster, detail) {
    return {
      title,
      render: body => {
        if (!items.length) {
          body.appendChild(asHint('nothing here'));
          return;
        }
        items.forEach(item => {
          const leaf = leafShaper(item);
          const row = el('button', 'vio-l2-side-row');
          row.textContent = leaf.label || '—';
          row.addEventListener('click', () => pushFrame(leafFrame(leaf, parentCluster, detail)));
          body.appendChild(row);
        });
      },
    };
  }

  // ── Per-leaf detail frame  (the recursion engine) ─────────────────────
  function leafFrame(leaf, cluster, detail) {
    const title = cluster ? `${cluster.title} · ${leaf.label}` : leaf.label;
    return {
      title,
      render: body => renderLeafBody(body, leaf, cluster, detail),
    };
  }

  function renderLeafBody(body, leaf, cluster, detail) {
    const f = leaf.full || {};

    switch (leaf.kind) {
      case 'doc': {
        body.appendChild(kv('file',   f.original_name || f.stored_name || '—'));
        body.appendChild(kv('type',   f.document_type || '—'));
        body.appendChild(kv('status', f.status || '—'));
        body.appendChild(kv('size',   f.size_human || formatBytes(f.size_bytes)));
        if (f.classification_confidence != null) {
          body.appendChild(kv('confidence', `${Math.round((f.classification_confidence || 0) * 100)}%`));
        }
        if (f.sha256_short) body.appendChild(kv('sha256', f.sha256_short, 'mono'));
        if (f.access_error) {
          const err = el('div', 'vio-l2-side-error');
          err.textContent = f.access_error;
          body.appendChild(err);
        }

        // Drill-down: identifiers found in this document (via classification metadata)
        const identsInDoc = identifiersInDoc(f, detail);
        if (identsInDoc.length) {
          body.appendChild(sectionTitle(`extracted (${identsInDoc.length})`));
          identsInDoc.forEach(ident => {
            const row = el('button', 'vio-l2-side-row');
            row.textContent = `${ident.kind}: ${ident.value}`;
            row.addEventListener('click', () =>
              pushFrame(leafFrame(
                { kind: 'ident', sub: ident.kind, label: ident.value, full: ident.item },
                cluster, detail)));
            body.appendChild(row);
          });
        }

        // Drill-down: findings that reference this file
        const relFindings = findingsForDoc(f, detail);
        if (relFindings.length) {
          body.appendChild(sectionTitle(`findings (${relFindings.length})`));
          relFindings.forEach(fnd => {
            const row = el('button', 'vio-l2-side-row');
            row.textContent = (fnd.severity || 'info').toUpperCase() + ' · ' + (fnd.message || fnd.code);
            row.addEventListener('click', () =>
              pushFrame(leafFrame(
                { kind: 'finding', label: fnd.message || fnd.code, severity: fnd.severity, full: fnd },
                cluster, detail)));
            body.appendChild(row);
          });
        }

        if (f.view_url || f.download_url) {
          body.appendChild(sectionTitle('actions'));
          if (f.view_url)     body.appendChild(linkBtn('view in new tab', f.view_url, true));
          if (f.download_url) body.appendChild(linkBtn('download',        f.download_url, false));
        }
        return;
      }

      case 'gen':
        body.appendChild(kv('file', f.full || f.name || '—'));
        body.appendChild(kv('size', formatBytes(leaf.size || 0)));
        body.appendChild(kv('kind', 'auto-generated'));
        return;

      case 'gap':
        body.appendChild(kv('label',    f.label || '—'));
        body.appendChild(kv('priority', (f.priority || 'medium').toUpperCase()));
        if (f.explanation) {
          body.appendChild(sectionTitle('why this matters'));
          body.appendChild(asProse(f.explanation));
        }
        if (f.example_url)         body.appendChild(linkBtn('example',          f.example_url, true));
        if (f.retrieval_help_url)  body.appendChild(linkBtn('how to retrieve',  f.retrieval_help_url, true));
        return;

      case 'finding':
        body.appendChild(kv('severity', (f.severity || 'info').toUpperCase()));
        body.appendChild(kv('code',     f.code || '—', 'mono'));
        body.appendChild(sectionTitle('message'));
        body.appendChild(asProse(f.message || '—'));
        if (f.hint) {
          body.appendChild(sectionTitle('hint'));
          body.appendChild(asProse(f.hint));
        }
        // Drill-down to source file if we can resolve it
        const relDoc = findRelatedDoc(f.message)
                    || findRelatedDoc(f.code)
                    || findRelatedDoc(f.source_file);
        if (relDoc) {
          body.appendChild(sectionTitle('related document'));
          const row = el('button', 'vio-l2-side-row');
          row.textContent = relDoc.original_name || relDoc.stored_name;
          row.addEventListener('click', () =>
            pushFrame(leafFrame(
              { kind: 'doc', label: relDoc.original_name || relDoc.stored_name, full: relDoc },
              cluster, detail)));
          body.appendChild(row);
        }
        return;

      case 'ident': {
        const value = typeof f === 'string' ? f : (f.value || f.name || leaf.label);
        body.appendChild(kv('value', value));
        body.appendChild(kv('kind',  leaf.sub || 'identifier'));
        if (typeof f === 'object') {
          if (f.confidence != null) body.appendChild(kv('confidence', `${Math.round((f.confidence || 0) * 100)}%`));
          if (f.status)             body.appendChild(kv('status',     f.status));
          if (f.first_seen)         body.appendChild(kv('first seen', f.first_seen, 'mono'));
        }
        // Drill-down: files where this identifier appears
        const sources = filesContainingIdent(value, detail);
        if (sources.length) {
          body.appendChild(sectionTitle(`appears in (${sources.length})`));
          sources.forEach(d => {
            const row = el('button', 'vio-l2-side-row');
            row.textContent = d.original_name || d.stored_name;
            row.addEventListener('click', () =>
              pushFrame(leafFrame(
                { kind: 'doc', label: d.original_name || d.stored_name, full: d },
                cluster, detail)));
            body.appendChild(row);
          });
        }
        return;
      }

      case 'payment':
        body.appendChild(kv('paid', f.paid ? 'yes' : 'no'));
        if (f.amount)        body.appendChild(kv('amount',     String(f.amount)));
        if (f.product_id)    body.appendChild(kv('product',    f.product_id));
        if (f.link_sent_utc) body.appendChild(kv('link sent',  f.link_sent_utc, 'mono'));
        if (f.link)          body.appendChild(linkBtn('open payment link', f.link, true));
        return;

      case 'project':
        body.appendChild(kv('project id', f.project_id || '—', 'mono'));
        body.appendChild(sectionTitle('actions'));
        body.appendChild(linkBtn('open cockpit', '/ui/control.html', true));
        return;

      case 'flag':
        body.appendChild(kv('flag', leaf.label));
        if (f && typeof f === 'string' && f !== leaf.label) {
          body.appendChild(asProse(f));
        }
        return;

      case 'note':
      default:
        body.appendChild(sectionTitle(leaf.label));
        if (f && typeof f === 'object') {
          // For confirmation_needed items
          if (f.field)       body.appendChild(kv('field',  f.field));
          if (f.value)       body.appendChild(kv('value',  f.value));
          if (f.status)      body.appendChild(kv('status', f.status));
          if (f.source_file) {
            const relDoc = findRelatedDoc(f.source_file);
            if (relDoc) {
              body.appendChild(sectionTitle('source file'));
              const row = el('button', 'vio-l2-side-row');
              row.textContent = relDoc.original_name || relDoc.stored_name;
              row.addEventListener('click', () =>
                pushFrame(leafFrame(
                  { kind: 'doc', label: relDoc.original_name || relDoc.stored_name, full: relDoc },
                  cluster, detail)));
              body.appendChild(row);
            } else {
              body.appendChild(kv('source file', f.source_file));
            }
          }
        } else {
          body.appendChild(asProse(typeof f === 'string' ? f : leaf.label));
        }
        return;
    }
  }

  // ── Per-stage frame  (clicking a stage anchor on the spine) ───────────
  function stageFrame(stage, company, detail) {
    return {
      title: `stage · ${stage.label}`,
      render: body => {
        const currentIdx = company.stage_index ?? 0;
        const idx = STAGES.findIndex(s => s.key === stage.key);
        let position;
        if (idx < currentIdx) position = 'completed';
        else if (idx === currentIdx) position = `current — ${(company.stage_state || 'healthy').replace(/_/g, ' ')}`;
        else position = 'future';

        body.appendChild(kv('position',  position));
        body.appendChild(kv('stage key', stage.key, 'mono'));

        body.appendChild(sectionTitle('what happens here'));
        body.appendChild(asProse(STAGE_DESCRIPTIONS[stage.key] || ''));

        if (!detail) return;

        // Which branches anchor at this stage? Surface them as drill-down rows.
        const branches = computeBranches(detail);
        const own = [...branches.above, ...branches.below].filter(b => {
          const sx = L.spineX0 + STAGES.findIndex(s => s.key === stage.key) * L.stageGap;
          return Math.abs(b.anchorX - sx) < L.stageGap / 2;
        });
        if (own.length) {
          body.appendChild(sectionTitle(`clusters here (${own.length})`));
          own.forEach(cl => {
            const r = el('button', 'vio-l2-side-row');
            r.textContent = `${cl.title} (${cl.leaves.length})`;
            r.addEventListener('click', () => pushFrame(clusterFrame(cl, detail)));
            body.appendChild(r);
          });
        }
      },
    };
  }

  // A cluster frame lists each leaf in that cluster as a clickable row.
  function clusterFrame(cluster, detail) {
    return {
      title: cluster.title,
      render: body => {
        if (!cluster.leaves.length) {
          body.appendChild(asHint('nothing here'));
          return;
        }
        cluster.leaves.forEach(leaf => {
          const row = el('button', 'vio-l2-side-row');
          row.textContent = leaf.label || '—';
          row.addEventListener('click', () => pushFrame(leafFrame(leaf, cluster, detail)));
          body.appendChild(row);
        });
      },
    };
  }

  // ─────────────────────────────────────────────────────────────────────
  // CROSS-REFERENCE HELPERS  (consumed by leaf detail frames)
  // ─────────────────────────────────────────────────────────────────────
  function identifiersInDoc(doc, detail) {
    // EI does not currently emit per-file entity attribution, so we
    // approximate: identifiers whose label substring appears in any of
    // the document's known names get surfaced. Falsey when no signal.
    if (!detail || !doc) return [];
    const prof = (detail.evidence && detail.evidence.profile) || {};
    const hay = `${doc.original_name || ''} ${doc.stored_name || ''} ${doc.document_type || ''}`.toLowerCase();
    const out = [];
    [['technologies', 'tech'], ['compliance_references', 'compliance'],
     ['vendors', 'vendor'], ['company_names', 'company']].forEach(([k, kind]) => {
      const list = Array.isArray(prof[k]) ? prof[k] : [];
      list.forEach(item => {
        const value = (typeof item === 'string' ? item : (item.value || item.name || item.label || ''));
        if (!value) return;
        // Conservative: only show identifiers whose value (>=4 chars) is in the file's metadata.
        // For per-file attribution beyond this, EI would need to emit a `sources` array.
        const v = String(value).toLowerCase();
        if (v.length >= 4 && hay.includes(v)) {
          out.push({ kind, value, item });
        }
      });
    });
    return out;
  }

  function filesContainingIdent(value, detail) {
    if (!_xref || !value) return [];
    const v = String(value).toLowerCase();
    const docs = detail.uploaded_documents || [];
    return docs.filter(d => {
      const hay = `${d.original_name || ''} ${d.stored_name || ''} ${d.document_type || ''}`.toLowerCase();
      return v.length >= 4 && hay.includes(v);
    });
  }

  function findingsForDoc(doc, detail) {
    if (!detail || !doc) return [];
    const candidates = [doc.original_name, doc.stored_name].filter(Boolean).map(s => s.toLowerCase());
    return (detail.findings || []).filter(f => {
      const text = `${f.message || ''} ${f.code || ''}`.toLowerCase();
      return candidates.some(c => text.includes(c));
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // STAGE DESCRIPTIONS
  // ─────────────────────────────────────────────────────────────────────
  const STAGE_DESCRIPTIONS = {
    intake:           'Customer submits company name, contact, and uploads first files. The intake record is created and a magic-link session is issued.',
    classification:   'Auto-classification reads each file and routes the intake into a primary compliance category (CMMC, ISO, DFARS, ITAR…).',
    validation:       'Each file passes the proof gate (hash, durable storage, chain of custody) before it can be claimed as received.',
    evidence_mapping: 'Evidence intelligence extracts entities, identifies technologies and compliance references, and flags gaps that need customer follow-up.',
    review:           'Operator reviews what was uploaded and what is missing; selects the right service tier.',
    approval:         'Service tier is locked, payment link is dispatched, and the engagement waits on the customer to pay.',
    conversion:       'Payment received. Project kicks off, generated paperwork is produced, and the engagement is delivered.',
  };

  // ─────────────────────────────────────────────────────────────────────
  // DOM HELPERS
  // ─────────────────────────────────────────────────────────────────────
  function el(tag, cls) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    return n;
  }
  function svgEl(tag) { return document.createElementNS(SVG_NS, tag); }

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
  function asProse(text) {
    const d = el('div', 'vio-l2-side-prose');
    d.textContent = text == null ? '' : String(text);
    return d;
  }
  function asHint(text) {
    const d = el('div', 'vio-l2-side-hint');
    d.textContent = text;
    return d;
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

  // ─────────────────────────────────────────────────────────────────────
  // KEYBOARD
  //   ESC at root → close Level 2
  //   ESC inside drill-down → pop one frame (operator's natural muscle memory)
  // ─────────────────────────────────────────────────────────────────────
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape' || !_activeCompany) return;
    if (_frameStack.length > 1) popFrame();
    else closeLevel2();
  });
})(window);
