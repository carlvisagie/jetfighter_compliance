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
  //
  // Doctrine §5 (Level 2 anatomy): "The L2 spine is a timeline, not a
  // stage-grid." Left edge = intake_created_utc, right edge = now (or
  // archived_utc when done). Stage labels slide to the timestamp at
  // which each stage actually started. Every branch sprouts from the
  // spine at the moment its activity began. These constants below set
  // the *visual* extent of the spine; the time→x mapping lives in
  // `_timeAxis(detail)` and is rebuilt each render so it always
  // reflects the current journey duration.
  const L = {
    // ── COMPANY ORB ──────────────────────────────────────────────────────
    // Carl's directive 2026-06-05: "the orb should contain all company
    // information". The orb is the passport — name, contact, compliance,
    // state — all encoded VISUALLY so the operator reads the room at a
    // glance, never needing the header text bar. Bumped from R=24 to R=56
    // to fit the contact-satellites and identity ring without crowding.
    orbR:        56,
    orbCx:       92,
    spineY:      280,        // pushed down 20px to make vertical room for the bigger orb
    spineX0:     180,        // pushed right 50px so the spine starts AFTER the orb
    spineWidth:  1200,   // pixels the timeline expands across, regardless of duration
    stageR:      9,
    branchSpacing: 60,
    leafW:       66,
    leafH:       38,
    leafGap:     14,
    leavesPerRow: 4,
    // Collision-avoidance: minimum centre-to-centre x distance between
    // two clusters on the same side.
    clusterMinGap: 90,
    // Custody ribbon — its own branch off the intake anchor. Layout
    // values are doctrine: limb height ≈ leaf height so it visually
    // belongs to the same family of branches, ribbon line stays thin
    // by default and thickens with activity (data-activity band).
    custodyLimbH:     38,
    custodyRibbonGap: 18,
    custodyShapeR:    4,
    custodyReservedH: 96,
  };

  function spineEndX() {
    return L.spineX0 + L.spineWidth;
  }

  // ─── Time → X axis ───────────────────────────────────────────────────
  // Build a closure that maps any ISO-UTC timestamp to its X coordinate
  // on the spine. tMin floors at intake_created_utc (or the earliest
  // custody event); tMax ceilings at now (or archived_utc). A minimum
  // span (24 h) prevents the spine from collapsing for fresh intakes.
  function _timeAxis(detail) {
    const custody = (detail && detail.custody && detail.custody.events) || [];
    const earliest = custody.length
      ? Math.min(...custody.map(e => Date.parse(e.at_utc || '') || Infinity))
      : Infinity;
    const intakeTs = Date.parse((detail && detail.created_utc) || '') || 0;
    const tMin = Math.min(
      isFinite(earliest) ? earliest : Date.now(),
      intakeTs > 0 ? intakeTs : Date.now(),
    );
    const latest = custody.length
      ? Math.max(...custody.map(e => Date.parse(e.at_utc || '') || 0))
      : 0;
    const tMax = Math.max(latest, Date.now());
    const span = Math.max(86400000, tMax - tMin); // ≥ 24 h minimum
    const W = L.spineWidth;
    const x0 = L.spineX0;
    return {
      tMin,
      tMax,
      span,
      // Convert a timestamp (ISO string, number, or undefined) into the
      // matching X. Falsy / unparseable timestamps fall back to "now"
      // (the rightmost edge), so a branch with unknown start lands at
      // the present rather than collapsing into the orb.
      timeToX(t) {
        if (!t) return x0 + W;
        const parsed = typeof t === 'number' ? t : Date.parse(t);
        if (!parsed || isNaN(parsed)) return x0 + W;
        const clamped = Math.max(tMin, Math.min(tMax, parsed));
        return x0 + ((clamped - tMin) / span) * W;
      },
    };
  }

  // ─── Branch start timestamp resolver ─────────────────────────────────
  // Every branch on L2 anchors at the moment its activity *began*. This
  // function returns that timestamp by mining the custody chain — the
  // single substrate of truth — for the first event that opens each
  // branch. Falls back to detail.created_utc for branches whose opening
  // event isn't yet recorded (still beats anchoring at an arbitrary
  // stage grid position).
  const _BRANCH_OPENERS = {
    context:       ['upload_received', 'intake_committed'],
    category:      ['classification_complete'],
    identifiers:   ['evidence_intelligence_completed'],
    tier:          ['operator_action_approve_review', 'operator_approved'],
    generated:     ['binder_exported'],   // best proxy until a doc-gen event exists
    docs:          ['upload_received', 'evidence_registered', 'file_persisted'],
    gaps:          ['evidence_intelligence_completed'],
    confirmation:  ['evidence_intelligence_completed'],
    findings:      ['integrity_failure', 'evidence_intelligence_failed'],
    payment:       ['operator_payment_link_sent', 'payment_link_sent'],
    project:       ['index_committed', 'intake_committed'],
    custody:       ['upload_received', 'intake_committed'],
  };

  function _branchStartUtc(detail, branchKey) {
    const events = (detail && detail.custody && detail.custody.events) || [];
    const openers = _BRANCH_OPENERS[branchKey] || [];
    for (let i = 0; i < events.length; i++) {
      const ev = events[i];
      const phase = String(ev.phase || ev.event || '');
      if (openers.includes(phase)) return ev.at_utc;
    }
    return detail && detail.created_utc;
  }

  // ─── Stage start timestamp resolver ─────────────────────────────────
  // Each backbone stage gets positioned on the timeline at the moment
  // it actually started. If a stage hasn't been reached yet, return
  // null and the renderer leaves the spine future-dashed past the last
  // known stage.
  const _STAGE_OPENERS = {
    intake:           ['upload_received', 'intake_committed'],
    classification:   ['classification_complete'],
    validation:       ['hash_verified', 'audit_written'],
    evidence_mapping: ['evidence_intelligence_completed', 'evidence_registered'],
    review:           ['operator_review_needed', 'operator_request_more_info'],
    approval:         ['operator_action_approve_review', 'operator_approved',
                       'operator_payment_link_sent', 'payment_link_sent'],
    conversion:       ['binder_exported', 'project_created'],
  };

  function _stageStartUtc(detail, stageKey) {
    const events = (detail && detail.custody && detail.custody.events) || [];
    const openers = _STAGE_OPENERS[stageKey] || [];
    for (let i = 0; i < events.length; i++) {
      const ev = events[i];
      const phase = String(ev.phase || ev.event || '');
      if (openers.includes(phase)) return ev.at_utc;
    }
    return null;
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

    // Doctrine §5: "ESC, the back chevron, or a click outside the canvas
    // all return the operator to Level 1." A click whose target IS the
    // mount (i.e. the dark backdrop, not any descendant) closes Level 2.
    if (!mount.dataset.backdropBound) {
      mount.addEventListener('mousedown', e => {
        if (e.target === mount) closeLevel2();
      });
      mount.dataset.backdropBound = '1';
    }

    mount.appendChild(buildHeader(company));
    const canvas    = buildCanvas();      mount.appendChild(canvas);
    // Side panel removed 2026-06-05 per Carl's directive: "remove this
    // side panel shit, it prevents you from using your imagination, and
    // letting your timeline speak clearly". The timeline + shapes ARE
    // the story now. The grid in vio.css is collapsed to a single
    // canvas column so the spine has the full width to breathe.

    renderSkeletonSpine(canvas, company);

    const intakeKey = company.intake_id || company.row_id || company.project_id;
    if (!intakeKey) {
      console.warn('[VIO L2] no intake id — nothing to render');
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
    } catch (err) {
      console.error('[VIO L2]', err);
      // Defensive visibility contract: tell the boot watchdog something
      // failed so the operator never gets a silent empty canvas. A side
      // hint alone is easy to miss when the canvas itself is black.
      if (window.VIO_BOOT && typeof window.VIO_BOOT.fault === 'function') {
        try { window.VIO_BOOT.fault('l2-load-failed', err); } catch (_) { /* boot script absent in tests */ }
      }
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
    // Doctrine: VIO tells the story in pictures. The company orb
    // (built in drawOrb) is the company passport — it carries
    // identity (initials), state (halo colour + breathing), contacts
    // (N/E/S/W satellites) and compliance domains (perimeter dots).
    // The header used to duplicate all of that in TEXT (title, sub,
    // state pill). Carl 2026-06-05: "WE USE TABS TEXT AS ABSOLUTE
    // LAST RESORT. TELL THE STORY IN PICTURES." So the header is now
    // navigation chrome + operator-override action ONLY. The full
    // company name lives on the browser tab title so the OS bar /
    // task switcher still answers "which L2 am I in?" without the
    // canvas itself carrying redundant text. An aria-label keeps
    // screen readers fully informed.
    const h = el('div', 'vio-l2-header');

    const back = el('button', 'vio-l2-back');
    back.textContent = '← back to VIO';
    back.addEventListener('click', closeLevel2);
    h.appendChild(back);

    const name = company.company_name || 'Unknown';
    h.setAttribute(
      'aria-label',
      'Level 2 for ' + name
        + (company.stage_state ? ' (state: ' + company.stage_state + ')' : '')
    );
    // Update the document title so OS chrome carries the identity the
    // operator no longer reads from the on-canvas header.
    try { document.title = 'VIO · ' + name; } catch (_) { /* SSR safe */ }

    // Right side: only the operator-override action. The freshness
    // sweep reprocesses autonomously; this button stays for "I want
    // it now" and for diagnostic replay (KYC_ORGANISM_DOCTRINE.md
    // → Autonomy by default → manual = override).
    const iid = company.intake_id || company.row_id || company.project_id;
    if (iid) {
      const reproc = el('button', 'vio-l2-reproc');
      reproc.type        = 'button';
      reproc.textContent = 'reprocess EI';
      reproc.title = (
        'Override path — force a wipe + rebuild of EI artifacts now '
        + '(the freshness sweep does this automatically every 5 minutes '
        + 'when staleness signals fire). Preserves review-queue history.'
      );
      reproc.addEventListener('click', () => triggerReprocess(iid, reproc));
      h.appendChild(reproc);
    }

    return h;
  }

  // ─────────────────────────────────────────────────────────────────────
  // OPERATOR ACTION — re-run Evidence Intelligence
  // ─────────────────────────────────────────────────────────────────────
  async function triggerReprocess(intakeId, btnEl) {
    if (!intakeId) return;
    const ok = window.confirm(
      'Re-run Evidence Intelligence for ' + intakeId + '?\n\n'
      + 'This will wipe and rebuild profile.json, gaps.json, '
      + 'extractions.jsonl, classifications.jsonl, and entities.jsonl, '
      + 'then re-extract from the real customer uploads.\n\n'
      + 'Review queue history is preserved.'
    );
    if (!ok) return;

    if (btnEl) { btnEl.disabled = true; btnEl.textContent = 'reprocessing…'; }
    showSideHint('reprocessing — wiping artifacts and re-extracting…');

    let report = null;
    let httpStatus = 0;
    try {
      const resp = await fetch(
        `/api/operator/evidence-intelligence/reprocess/${encodeURIComponent(intakeId)}`,
        {
          method:      'POST',
          credentials: 'same-origin',
          headers:     { 'Content-Type': 'application/json' },
          body:        JSON.stringify({ wipe: true }),
        }
      );
      httpStatus = resp.status;
      const ctype = resp.headers.get('content-type') || '';
      report = ctype.includes('json')
        ? await resp.json()
        : { ok: false, error: 'non_json_response', body: (await resp.text()).slice(0, 300) };
    } catch (err) {
      report = { ok: false, error: 'fetch_failed', detail: String(err && err.message || err) };
    }

    if (btnEl) { btnEl.disabled = false; btnEl.textContent = 'reprocess EI'; }

    resetFrames({
      title: 'reprocess report',
      render: body => renderReprocessReport(body, report, httpStatus),
    });
  }

  function renderReprocessReport(body, report, httpStatus) {
    if (!report) {
      body.appendChild(asHint('no response from server'));
      return;
    }
    const summary = el('div', 'vio-l2-side-prose');
    const status  = report.ok === true ? 'OK' : 'FAILED';
    summary.textContent = (
      `status: ${status}  (HTTP ${httpStatus})\n`
      + `intake_id:     ${report.intake_id || '?'}\n`
      + `files seen:    ${report.files_seen || 0}\n`
      + `processed:     ${(report.files_processed || []).length}\n`
      + `failed:        ${(report.files_failed || []).length}\n`
      + `OCR attempts:  ${report.ocr_attempts || 0}\n`
      + `OCR succeeded: ${report.ocr_succeeded || 0}\n`
    );
    body.appendChild(summary);

    if (report.error) {
      const errBox = el('div', 'vio-l2-side-prose');
      errBox.style.color = 'var(--st-failed, #ff8080)';
      errBox.textContent = (
        `error: ${report.error}`
        + (report.detail ? `\n${report.detail}` : '')
      );
      body.appendChild(errBox);
    }

    if (Array.isArray(report.files_processed) && report.files_processed.length) {
      const h = el('div', 'vio-l2-side-section-title');
      h.textContent = 'files processed';
      body.appendChild(h);
      report.files_processed.forEach(f => {
        const row = el('div', 'vio-l2-side-row');
        const ocr = f.ocr_applied
          ? `OCR ok (${f.ocr_text_length || 0} chars)`
          : (f.ocr_status ? `OCR ${f.ocr_status}` : '');
        row.textContent = (
          `• ${f.file}  →  ${f.status || '?'}`
          + (f.entities != null ? `  | ${f.entities} entities` : '')
          + (f.gaps     != null ? `, ${f.gaps} gaps`           : '')
          + (ocr                 ? `  | ${ocr}`                : '')
          + (f.pending_analysis  ? `  | pending`               : '')
        );
        body.appendChild(row);
      });
    }

    if (Array.isArray(report.files_failed) && report.files_failed.length) {
      const h = el('div', 'vio-l2-side-section-title');
      h.textContent = 'files failed';
      h.style.color = 'var(--st-failed, #ff8080)';
      body.appendChild(h);
      report.files_failed.forEach(f => {
        const row = el('div', 'vio-l2-side-row');
        row.style.color = 'var(--st-failed, #ff8080)';
        row.textContent = `• ${f.file}: ${f.error || '?'}${f.detail ? ' — ' + f.detail : ''}`;
        body.appendChild(row);
      });
    }

    const hint = el('div', 'vio-l2-side-hint');
    hint.textContent = 'click "← back to VIO" then re-open this intake to see refreshed inventory + gaps.';
    body.appendChild(hint);
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
    // Reserve vertical room for the custody ribbon below the deepest
    // `below` cluster when there are any custody events to draw.
    const custodyEventCount = ((detail.custody || {}).events || []).length;
    const custodyExtra = custodyEventCount > 0 ? L.custodyReservedH : 0;
    const h = Math.max(420, spineY + belowMax + 100 + custodyExtra);

    const svg = svgEl('svg');
    svg.setAttribute('class', 'vio-l2-svg');
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);

    const axis = _timeAxis(detail);
    drawSpine(svg, company, spineY, axis, detail);
    branches.above.forEach(b => drawBranch(svg, b, spineY, 'above', detail));
    branches.below.forEach(b => drawBranch(svg, b, spineY, 'below', detail));

    // Custody chain is its own branch — anchored at the `intake` stage
    // Custody ribbon (parallel cyan timeline below the spine) disabled
    // 2026-06-05. Carl: "Make VIO emulate this nothing more no side
    // panels" + sketch shows ONE spine, not two. Custody events still
    // exist in the data and will be folded back into the main spine as
    // discrete shapes in a follow-up pass; for now we keep the spine
    // alone so the operator's eye has nothing to compete with the story.
    // drawCustodyBranch(svg, detail, spineY, belowMax);  // INTENTIONALLY OFF

    drawOrb(svg, company, spineY);

    canvas.appendChild(svg);
  }

  // ── Spine + stage anchors ─────────────────────────────────────────────
  // Doctrine §5: the spine is a timeline. Left edge = intake_created,
  // right edge = now. Past stages render at the timestamp they actually
  // started; future stages render as faint placeholders evenly spaced
  // along the future-dashed segment so the 7-stage legend stays
  // readable without lying about when those stages happened.
  function drawSpine(svg, company, spineY = L.spineY, axis, detail) {
    // SAFETY: skeleton renders (renderSkeletonSpine) call drawSpine without
    // an axis. Until 2026-06-05 this silently threw `Cannot read properties
    // of undefined (reading 'tMin')` inside the async openLevel2 — caught
    // only as an unhandled rejection, leaving operators staring at an empty
    // canvas with just "overview" in the side panel. _timeAxis(undefined)
    // is total: it returns a one-day-wide axis anchored at "now", which is
    // the right skeleton behaviour (no past, just a placeholder spine).
    if (!axis) axis = _timeAxis(detail);
    const events = (detail && detail.custody && detail.custody.events) || [];
    const lastEventT = events.length
      ? Math.max(...events.map(e => Date.parse(e.at_utc || '') || 0))
      : 0;
    const liveX = lastEventT > 0 ? axis.timeToX(lastEventT) : L.spineX0;
    const endX  = spineEndX();

    // Future dashed segment — from the last known event to "now".
    if (liveX < endX) {
      const future = svgEl('line');
      future.setAttribute('class', 'vio-l2-spine-future');
      future.setAttribute('x1', liveX);
      future.setAttribute('x2', endX);
      future.setAttribute('y1', spineY);
      future.setAttribute('y2', spineY);
      svg.appendChild(future);
    }
    // Past segment — from intake to the most recent event. The line
    // itself encodes state (colour + pulse) as §11 of the doctrine
    // requires; activity-band thickness is inherited from the company
    // payload so the spine reads heavier for active intakes.
    const past = svgEl('line');
    past.setAttribute('class', 'vio-l2-spine-past');
    past.setAttribute('data-stage-state', company.stage_state || 'healthy');
    past.setAttribute('x1', L.spineX0);
    past.setAttribute('x2', liveX);
    past.setAttribute('y1', spineY);
    past.setAttribute('y2', spineY);
    svg.appendChild(past);

    // Stage anchors. Past/current stages are positioned at their actual
    // start timestamp. Future stages are evenly distributed across the
    // remaining future-segment so the legend remains a stable backbone
    // even when most of the journey hasn't happened yet.
    const stageTimestamps = STAGES.map(s => _stageStartUtc(detail, s.key));
    const startedCount = stageTimestamps.filter(t => t).length;
    const futureCount = STAGES.length - startedCount;
    const futureStep = futureCount > 0
      ? Math.max(40, (endX - liveX) / (futureCount + 1))
      : 0;
    let futureIndex = 0;

    STAGES.forEach((s, i) => {
      const tStart = stageTimestamps[i];
      let cx, isPast;
      if (tStart) {
        cx = axis.timeToX(tStart);
        isPast = true;
      } else {
        futureIndex++;
        cx = liveX + futureStep * futureIndex;
        isPast = false;
      }
      const g = svgEl('g');
      g.setAttribute('class', isPast ? 'vio-l2-stage past' : 'vio-l2-stage future');
      g.setAttribute('data-stage', s.key);

      const isLive = isPast && cx >= liveX - 1;
      const c = svgEl('circle');
      c.setAttribute('cx', cx);
      c.setAttribute('cy', spineY);
      c.setAttribute('r', isLive ? L.stageR + 2 : L.stageR);
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

    // Quiet time-scale labels under the spine — start date on the left,
    // "now" on the right. Identity only; no axis ticks. Doctrine §11.
    const startLabel = svgEl('text');
    startLabel.setAttribute('class', 'vio-l2-spine-time-label');
    startLabel.setAttribute('x', L.spineX0);
    startLabel.setAttribute('y', spineY - 12);
    startLabel.setAttribute('text-anchor', 'start');
    startLabel.textContent = new Date(axis.tMin).toISOString().slice(0, 10);
    svg.appendChild(startLabel);

    const endLabel = svgEl('text');
    endLabel.setAttribute('class', 'vio-l2-spine-time-label');
    endLabel.setAttribute('x', endX);
    endLabel.setAttribute('y', spineY - 12);
    endLabel.setAttribute('text-anchor', 'end');
    endLabel.textContent = 'now';
    svg.appendChild(endLabel);

    // ── SIGNAL LAYERS — Carl's revolution-without-words directive ──────
    //
    // The spine isn't a line, it's a CONVERSATION between client and
    // organism rendered in light. Three overlays make it speak:
    //
    //   1. density band — vertical micro-bars below the spine, one per
    //      activity-bucket; taller bars = denser activity in that window.
    //      An operator reads the rhythm of work at a glance.
    //   2. gap markers — `||` glyphs at long quiet stretches between
    //      events (>= 12 h). Visible pause-points in the journey.
    //   3. live pulse — soft animated halo at the live tip when the most
    //      recent event landed in the last 60 minutes. "Right now" is a
    //      distinct visual class from "yesterday".
    //
    // Both layers are subordinate to the base spine line — they overlay
    // the same X-axis so the operator's eye stays on one timeline.
    //
    // MOTION DISCIPLINE (docs/VIO_DOCTRINE.md §6, Carl 2026-06-05):
    // "Continuous motion MUST point to something that demands attention,
    //  UNTIL it is handled. Once resolved, motion stops." Density bars
    //  and gap markers are STILL — they are visual weight, not motion.
    //  An earlier `_drawSpineLive` pulsed at the spine tip whenever the
    //  last event landed in the last 60 minutes. Recent activity is NOT
    //  an unresolved demand, so it was removed.
    _drawSpineSignal(svg, spineY, events, axis);
    _drawSpineGaps(svg, spineY, events, axis);
  }

  // Pack timestamps into N x-buckets along the spine and render each
  // bucket's count as a small vertical bar BELOW the spine. Opacity and
  // height scale together so a single event whispers and a busy cluster
  // shouts. Buckets are based on screen-space X (not time) so visual
  // density mirrors what the operator sees, not an abstract rate.
  function _drawSpineSignal(svg, spineY, events, axis) {
    if (!events || !events.length) return;
    const BUCKETS = 48;                    // ~25 px per bucket at 1200 px wide
    const w = L.spineWidth;
    const counts = new Array(BUCKETS).fill(0);
    events.forEach(ev => {
      const t = Date.parse(ev.at_utc || '') || 0;
      if (!t) return;
      const x = axis.timeToX(t) - L.spineX0;
      if (x < 0 || x > w) return;
      const idx = Math.min(BUCKETS - 1, Math.floor((x / w) * BUCKETS));
      counts[idx]++;
    });
    const peak = Math.max(1, ...counts);
    const bucketWidth = w / BUCKETS;
    counts.forEach((n, i) => {
      if (n === 0) return;
      const xMid = L.spineX0 + (i + 0.5) * bucketWidth;
      const h = 2 + Math.round((n / peak) * 12);   // 2..14 px bar
      const bar = svgEl('rect');
      bar.setAttribute('class', 'vio-l2-spine-signal');
      bar.setAttribute('x', xMid - 1.2);
      bar.setAttribute('y', spineY + 2);
      bar.setAttribute('width', 2.4);
      bar.setAttribute('height', h);
      bar.setAttribute('opacity', 0.35 + 0.55 * (n / peak));
      svg.appendChild(bar);
    });
  }

  // Render a small `||` glyph between events that are more than 12 h
  // apart. These are the visible silences in the journey — gaps where
  // nothing happened, which is itself information.
  function _drawSpineGaps(svg, spineY, events, axis) {
    if (!events || events.length < 2) return;
    const GAP_MS = 12 * 60 * 60 * 1000;   // 12 hours
    const stamped = events
      .map(e => Date.parse(e.at_utc || '') || 0)
      .filter(t => t > 0)
      .sort((a, b) => a - b);
    for (let i = 1; i < stamped.length; i++) {
      const dt = stamped[i] - stamped[i - 1];
      if (dt < GAP_MS) continue;
      const midT = (stamped[i] + stamped[i - 1]) / 2;
      const x = axis.timeToX(midT);
      // Two short vertical strokes — visually reads as a pause symbol.
      [-2, +2].forEach(dx => {
        const tick = svgEl('line');
        tick.setAttribute('class', 'vio-l2-spine-gap');
        tick.setAttribute('x1', x + dx);
        tick.setAttribute('x2', x + dx);
        tick.setAttribute('y1', spineY - 5);
        tick.setAttribute('y2', spineY + 5);
        svg.appendChild(tick);
      });
    }
  }

  // (`_drawSpineLive` removed 2026-06-05 — see motion-discipline note
  //  in drawSpine. Continuous animation reserved for unresolved demand;
  //  recent activity is not a demand. The spine's own terminus already
  //  marks "now" visually.)

  // ── Orb — the company's identity at rest ──────────────────────────────
  //
  // Carl 2026-06-05 (sharpened repeatedly through the day):
  //
  //   "the orb is company information... tel email address... you can
  //    not cram all that info into the orb without clicking to expand"
  //   "no movement no rings nothing"
  //   "tell the story with pictures"
  //
  // Resting state: a single static circle with the company NAME visible
  // inside (auto-wrapped to two lines if long). No halo. No identity
  // ring. No satellites. No compliance dots. No breathing. No limb.
  // Just the orb and the name.
  //
  // Clicking the orb toggles a small text card next to it that exposes
  // the rest of the company information — tel, email, address. The
  // card lives in the SVG so it shares the canvas coordinate system
  // (no DOM overlay drift). Click outside or click the orb again to
  // collapse it. Operator's choice; no persistent expanded surface
  // (one click in, one click out — never a side panel).
  function drawOrb(svg, company, spineY = L.spineY) {
    const detail = _activeDetail || {};
    const ictx   = detail.intake_context || {};
    const prof   = (detail.evidence && detail.evidence.profile) || {};

    const g = svgEl('g');
    g.setAttribute('class', 'vio-l2-orb-group');

    // Single static circle. Stroke only — no fill colour competing
    // with the spine. Sized big enough to read the company name from
    // across the room.
    const core = svgEl('circle');
    core.setAttribute('class', 'vio-l2-orb');
    core.setAttribute('cx', L.orbCx);
    core.setAttribute('cy', spineY);
    core.setAttribute('r', L.orbR);
    g.appendChild(core);

    // Company name inside the orb — wraps to up to 2 lines.
    const fullName = (company.company_name || 'Unknown').trim();
    const lines = _wrapNameForOrb(fullName, /*maxCharsPerLine=*/16, /*maxLines=*/2);
    const lineH = 18;
    const startY = spineY - ((lines.length - 1) * lineH) / 2 + 5;
    const nameText = svgEl('text');
    nameText.setAttribute('class', 'vio-l2-orb-name');
    nameText.setAttribute('x', L.orbCx);
    nameText.setAttribute('y', startY);
    nameText.setAttribute('text-anchor', 'middle');
    lines.forEach((line, i) => {
      const tspan = svgEl('tspan');
      tspan.setAttribute('x', L.orbCx);
      tspan.setAttribute('dy', i === 0 ? 0 : lineH);
      tspan.textContent = line;
      nameText.appendChild(tspan);
    });
    g.appendChild(nameText);

    // ── Expanded-info card (collapsed by default) ─────────────────────
    // Click the orb -> show this card to the right of the orb. Click
    // again -> hide. Contains Tel / Email / Address — the rest of the
    // company information that doesn't fit in the orb itself.
    const cardItems = [
      { label: 'tel',     value: ictx.phone || '' },
      { label: 'email',   value: company.email_anchor || company.email || (ictx.email || '') },
      { label: 'address', value: ictx.address
                                 || (Array.isArray(prof.addresses) && prof.addresses[0])
                                 || '' },
    ].filter(it => it.value);

    if (cardItems.length) {
      const card = svgEl('g');
      card.setAttribute('class', 'vio-l2-orb-card');
      card.setAttribute('data-open', '0');

      const cardX = L.orbCx + L.orbR + 14;
      const cardY = spineY - (cardItems.length * 16) / 2 - 14;
      const cardW = 240;
      const cardH = cardItems.length * 18 + 22;

      const bg = svgEl('rect');
      bg.setAttribute('class', 'vio-l2-orb-card-bg');
      bg.setAttribute('x', cardX);
      bg.setAttribute('y', cardY);
      bg.setAttribute('width', cardW);
      bg.setAttribute('height', cardH);
      bg.setAttribute('rx', 6);
      card.appendChild(bg);

      cardItems.forEach((it, i) => {
        const y = cardY + 18 + i * 18;
        const labelEl = svgEl('text');
        labelEl.setAttribute('class', 'vio-l2-orb-card-label');
        labelEl.setAttribute('x', cardX + 12);
        labelEl.setAttribute('y', y);
        labelEl.textContent = it.label;
        card.appendChild(labelEl);
        const valueEl = svgEl('text');
        valueEl.setAttribute('class', 'vio-l2-orb-card-value');
        valueEl.setAttribute('x', cardX + 70);
        valueEl.setAttribute('y', y);
        // Truncate very long values so the card doesn't span the canvas.
        valueEl.textContent = it.value.length > 30
          ? it.value.slice(0, 28) + '…'
          : it.value;
        const title = svgEl('title');
        title.textContent = it.value;   // full value on hover
        valueEl.appendChild(title);
        card.appendChild(valueEl);
      });

      g.appendChild(card);

      g.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = card.getAttribute('data-open') === '1';
        card.setAttribute('data-open', open ? '0' : '1');
      });
      // Click anywhere else on the SVG collapses the card.
      svg.addEventListener('click', () => {
        card.setAttribute('data-open', '0');
      });
    }

    svg.appendChild(g);
  }

  // Greedy line-wrap for the company name inside the orb. Splits on
  // whitespace; if a single word still overflows we soft-break at the
  // limit. Keeps the wrap deterministic so tests + screenshots are
  // reproducible.
  function _wrapNameForOrb(name, maxCharsPerLine, maxLines) {
    if (!name) return ['Unknown'];
    if (name.length <= maxCharsPerLine) return [name];
    const words = name.split(/\s+/);
    const lines = [];
    let cur = '';
    for (const w of words) {
      if (!cur) { cur = w; continue; }
      if ((cur + ' ' + w).length <= maxCharsPerLine) cur += ' ' + w;
      else { lines.push(cur); cur = w; if (lines.length === maxLines - 1) break; }
    }
    if (cur && lines.length < maxLines) lines.push(cur);
    // If the last line still overflows or words got dropped, hard-truncate.
    if (lines.length === maxLines) {
      const last = lines[maxLines - 1];
      if (last.length > maxCharsPerLine) {
        lines[maxLines - 1] = last.slice(0, maxCharsPerLine - 1) + '…';
      }
      // If there's leftover words we never appended, indicate truncation.
      const consumed = lines.join(' ').replace(/…$/, '').trim();
      if (name.length > consumed.length && !lines[maxLines - 1].endsWith('…')) {
        lines[maxLines - 1] = lines[maxLines - 1].slice(0, maxCharsPerLine - 1) + '…';
      }
    }
    return lines.length ? lines : [name.slice(0, maxCharsPerLine - 1) + '…'];
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

    // Doctrine §5: branches anchor at the TIMESTAMP the activity began,
    // not at a fixed stage-grid position. `axis.timeToX` maps any
    // ISO-UTC timestamp into a spine X; `_branchStartUtc` mines the
    // custody chain for the first event that opens each branch.
    const axis = _timeAxis(detail);
    const at = key => axis.timeToX(_branchStartUtc(detail, key));

    // ── ABOVE the spine ────────────────────────────────────────────────
    if ((ictx.context && ictx.context.length) || ictx.urgent || ictx.deadline) {
      above.push(makeCluster('context', 'context', at('context'), [
        ictx.urgent ? { kind: 'flag', label: 'urgent' } : null,
        ictx.deadline ? { kind: 'flag', label: `deadline ${ictx.deadline}` } : null,
        ictx.context ? { kind: 'note', label: truncate(ictx.context, 18), full: ictx.context } : null,
      ].filter(Boolean)));
    }

    if (cls.primary_category) {
      const leaves = [{ kind: 'flag', label: truncate(cls.primary_category, 16), full: cls.primary_category }];
      if (cls.secondary_category) leaves.push({ kind: 'flag', label: truncate(cls.secondary_category, 16), full: cls.secondary_category });
      if (cls.scope_label)        leaves.push({ kind: 'note', label: truncate(cls.scope_label, 14), full: cls.scope_label });
      above.push(makeCluster('category', 'category', at('category'), leaves));
    }

    const identifierLeaves = [];
    pushIdent(identifierLeaves, prof.technologies,           'tech');
    pushIdent(identifierLeaves, prof.compliance_references,  'compliance');
    pushIdent(identifierLeaves, prof.vendors,                'vendor');
    pushIdent(identifierLeaves, prof.company_names,          'company');
    if (identifierLeaves.length) {
      above.push(makeCluster('identifiers', `identifiers (${identifierLeaves.length})`,
        at('identifiers'), identifierLeaves));
    }

    if (['approved', 'payment_sent', 'verified_complete', 'archived'].includes(detail.review_status)) {
      above.push(makeCluster('tier', 'service tier', at('tier'), [
        { kind: 'flag', label: detail.review_status.replace(/_/g, ' ') },
      ]));
    }

    if (gen.length) {
      above.push(makeCluster('generated', `generated (${gen.length})`, at('generated'),
        gen.map(g => ({ kind: 'gen', label: truncate(g.name, 16), full: g.name, size: g.size_bytes }))));
    }

    // ── BELOW the spine ────────────────────────────────────────────────
    if (docs.length) {
      below.push(makeCluster('docs', `papers (${docs.length})`, at('docs'),
        docs.map(d => ({
          kind: 'doc',
          label: truncate(d.original_name || d.stored_name || 'file', 16),
          status: d.status || 'on_disk',
          doc_type: d.document_type || '',
          full: d,
        }))));
    }

    if (miss.length) {
      below.push(makeCluster('gaps', `missing (${miss.length})`, at('gaps'),
        miss.map(m => ({
          kind: 'gap',
          label: truncate(m.label || 'gap', 16),
          priority: m.priority || 'medium',
          full: m,
        }))));
    }

    if (conf.length) {
      below.push(makeCluster('confirmation', `confirmation (${conf.length})`,
        at('confirmation'),
        conf.map(c => ({
          kind: 'note',
          label: truncate(c.field || 'field', 14),
          full: c,
        }))));
    }

    if (find.length) {
      below.push(makeCluster('findings', `findings (${find.length})`, at('findings'),
        find.map(f => ({
          kind: 'finding',
          label: truncate(f.message || f.code || 'finding', 16),
          severity: f.severity || 'info',
          full: f,
        }))));
    }

    if (pay && (pay.link || pay.amount || pay.link_sent_utc || pay.paid)) {
      const paidLabel = pay.paid ? 'paid' : (pay.link ? 'link sent' : 'pending');
      const paymentAnchorUtc = pay.link_sent_utc || _branchStartUtc(detail, 'payment');
      below.push(makeCluster('payment', 'payment', axis.timeToX(paymentAnchorUtc), [
        { kind: 'payment', label: paidLabel, full: pay },
      ]));
    } else if (['approved', 'payment_sent', 'verified_complete', 'archived'].includes(detail.review_status)) {
      below.push(makeCluster('payment', 'payment', at('payment'), [
        { kind: 'payment', label: 'awaiting record', full: pay },
      ]));
    }

    if (detail.project_id) {
      below.push(makeCluster('project', 'project', at('project'), [
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

    // Branch limb removed 2026-06-05 per Carl: "Remove cyan branch/limb
    // line unless state absolutely requires it." Default = no limb. The
    // cluster's vertical position relative to the spine is enough of a
    // visual anchor; the limb was decorative cyan ink that the eye
    // couldn't ignore and that the sketch never had.

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
  // CUSTODY BRANCH  (splits off the intake anchor, runs along time)
  // ─────────────────────────────────────────────────────────────────────
  /**
   * Render the chain-of-custody as a real branch on the L2 spine.
   *
   * Doctrine §11 + §12: a line that itself communicates (thickness ∝
   * activity, opacity ∝ age) carrying shapes (channel-glyphed, ok=teal
   * fail=red) for every recorded custody event. The branch *splits off
   * the intake stage anchor* — the moment we start dealing with the
   * company — and stretches rightward to the right edge of the spine,
   * with each event placed by its real timestamp between intake_start
   * and now. Reads as a parallel mini-spine specifically about evidence
   * provenance, not as a row table.
   */
  function drawCustodyBranch(svg, detail, spineY, belowMax) {
    const custody = detail && detail.custody;
    const events  = (custody && custody.events) || [];
    if (!events.length) return;

    // Parse timestamps; ignore unparseable rows (rare but possible).
    const stamped = events
      .map(e => ({ ev: e, t: Date.parse(e.at_utc || '') || 0 }))
      .filter(p => p.t > 0)
      .sort((a, b) => a.t - b.t);
    if (!stamped.length) return;

    const tMin = stamped[0].t;
    const tMax = Math.max(stamped[stamped.length - 1].t, Date.now());
    const span = Math.max(1, tMax - tMin);

    // Geometry: limb splits off the intake anchor, bends 90° down to a
    // horizontal ribbon that runs to the right edge of the spine.
    const limbX  = L.spineX0;
    const ribbonY = spineY + Math.max(belowMax, 36) + L.custodyRibbonGap + L.custodyLimbH;
    const limbTopY    = spineY;
    const limbBottomY = ribbonY;
    const rightX = spineEndX();

    // Activity band — events per day, capped to the same vocabulary the
    // L1 spine uses. The custody line itself encodes density, in addition
    // to the shapes on it ("line is parallel language" — doctrine §1.4).
    const days = Math.max(0.5, span / 86400000);
    const perDay = stamped.length / days;
    let band = 'normal';
    if (perDay <= 0.5)      band = 'idle';
    else if (perDay <= 2)   band = 'low';
    else if (perDay <= 8)   band = 'normal';
    else if (perDay <= 20)  band = 'high';
    else                    band = 'peak';

    const group = svgEl('g');
    group.setAttribute('class', 'vio-l2-custody');
    group.setAttribute('id', 'vio-l2-custody-group');

    // The limb (bent path from intake anchor down to ribbon level).
    const limb = svgEl('path');
    limb.setAttribute('class', 'vio-l2-custody-limb');
    limb.setAttribute('data-activity', band);
    limb.setAttribute(
      'd',
      `M ${limbX} ${limbTopY} ` +
      `Q ${limbX} ${limbTopY + 14}, ${limbX + 14} ${limbTopY + 14} ` +
      `L ${limbX + 14} ${limbBottomY - 14} ` +
      `Q ${limbX + 14} ${limbBottomY}, ${limbX + 28} ${limbBottomY}`,
    );
    group.appendChild(limb);

    // The ribbon (horizontal time-axis line under the spine).
    const ribbon = svgEl('line');
    ribbon.setAttribute('class', 'vio-l2-custody-line');
    ribbon.setAttribute('data-activity', band);
    ribbon.setAttribute('x1', limbX + 28);
    ribbon.setAttribute('x2', rightX);
    ribbon.setAttribute('y1', ribbonY);
    ribbon.setAttribute('y2', ribbonY);
    group.appendChild(ribbon);

    // End tick (the "now" anchor).
    const endTick = svgEl('line');
    endTick.setAttribute('class', 'vio-l2-custody-tick');
    endTick.setAttribute('x1', rightX);
    endTick.setAttribute('x2', rightX);
    endTick.setAttribute('y1', ribbonY - 5);
    endTick.setAttribute('y2', ribbonY + 5);
    group.appendChild(endTick);

    // Quiet label at the branch start — identity only ("custody"), per
    // doctrine: "text is the absolute minimum needed for identity."
    const label = svgEl('text');
    label.setAttribute('class', 'vio-l2-custody-branch-label');
    label.setAttribute('x', limbX + 6);
    label.setAttribute('y', limbBottomY - 8);
    label.textContent = `custody · ${stamped.length}`;
    group.appendChild(label);

    // Event shapes on the ribbon. Time-mapped between limb origin and
    // right edge. Channel→silhouette, ok=teal, fail=red, hover scales.
    const ribbonLeftX = limbX + 28;
    const ribbonWidth = Math.max(40, rightX - ribbonLeftX);
    stamped.forEach(({ ev, t }) => {
      const x = ribbonLeftX + ((t - tMin) / span) * ribbonWidth;
      const shape = _custodyShape(ev, x, ribbonY);
      shape.setAttribute('class', 'vio-l2-custody-mark');
      shape.setAttribute('data-source', String(ev.source || ''));
      shape.setAttribute('data-ok',
        String(ev.ok === false ? 'false' : 'true'));
      shape.setAttribute('tabindex', '0');
      const nativeTitle = svgEl('title');
      nativeTitle.textContent =
        `${(ev.at_utc || '').replace('T', ' ').replace('Z', '')}  ` +
        `${String(ev.event || '').replace(/_/g, ' ')}`;
      shape.appendChild(nativeTitle);
      const open = () => pushFrame(_custodyEventFrame(ev));
      shape.addEventListener('click', e => { e.stopPropagation(); open(); });
      shape.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          open();
        }
      });
      group.appendChild(shape);
    });

    svg.appendChild(group);
  }

  // Single-event frame (clicking one custody mark drills into it).
  function _custodyEventFrame(ev) {
    return {
      title: `custody · ${String(ev.event || '').replace(/_/g, ' ')}`,
      render: body => {
        const meta = ev.metadata || {};
        const head = el('div', 'vio-l2-custody-detail');
        const headLine = el('div', 'vio-l2-custody-detail-head');
        const evtSpan = el('span', 'vio-l2-custody-detail-evt');
        evtSpan.textContent = String(ev.event || '').replace(/_/g, ' ');
        const whenSpan = el('span', 'vio-l2-custody-detail-when');
        whenSpan.textContent =
          (ev.at_utc || '').replace('T', ' ').replace('Z', '');
        headLine.appendChild(evtSpan);
        headLine.appendChild(whenSpan);
        head.appendChild(headLine);

        const srcLine = el('div', 'vio-l2-custody-detail-src');
        srcLine.textContent =
          `source: ${ev.source || 'unknown'}` +
          (ev.ok === false ? '  ·  INTEGRITY FAIL' : '');
        head.appendChild(srcLine);

        const keys = Object.keys(meta);
        if (keys.length) {
          const dl = el('dl', 'vio-l2-custody-detail-meta');
          keys.forEach(k => {
            const dt = document.createElement('dt');
            dt.textContent = k;
            const dd = document.createElement('dd');
            const v = meta[k];
            dd.textContent = (typeof v === 'object') ? JSON.stringify(v) : String(v);
            dl.appendChild(dt);
            dl.appendChild(dd);
          });
          head.appendChild(dl);
        }
        body.appendChild(head);
      },
    };
  }

  // ─────────────────────────────────────────────────────────────────────
  // FRAMES  (root + per-leaf drill-down + per-stage drill-down)
  // ─────────────────────────────────────────────────────────────────────
  function overviewFrame(company, detail) {
    return {
      title: 'overview',
      render: body => {
        const stage = STAGES[company.stage_index ?? 0]?.label || 'intake';

        // ── At-a-glance KPI tiles (Constitution: "State Before Detail") ─
        // Four declarative numbers so the operator reads the room without
        // hunting for any of them. Doctrine: "Within five seconds … know
        // who, where, healthy, waiting, broken, next action."
        const filesCount    = (detail.uploaded_documents || []).length || (detail.file_count || 0);
        const gapsCount     = (detail.missing_documents || []).length;
        const findingsCount = (detail.findings || []).length;
        const daysInStage   = company.days_in_stage ?? 0;
        const custody       = detail.custody || {};
        const custodyCount  = Number(custody.event_count || 0);
        const tiles = el('div', 'vio-l2-tiles');
        // L2 rule: "all of it clickable for more detailed information."
        // Every tile drills into the list it represents. Tiles with a
        // zero count have no destination and are presented as quiet
        // not-actionable artifacts (still readable, just inert).
        tiles.appendChild(_kpiTileDrill(
          filesCount, 'files received', '',
          filesCount > 0 ? () => pushFrame(listFrame('papers', detail.uploaded_documents || [],
            d => ({ kind: 'doc', label: d.original_name || d.stored_name, full: d }),
            null, detail)) : null,
        ));
        tiles.appendChild(_kpiTileDrill(
          findingsCount, findingsCount === 1 ? 'finding' : 'findings',
          findingsCount > 0 ? 'tile-warn' : '',
          findingsCount > 0 ? () => pushFrame(listFrame('findings', detail.findings || [],
            f => ({ kind: 'finding', label: f.message || f.code, severity: f.severity, full: f }),
            null, detail)) : null,
        ));
        tiles.appendChild(_kpiTileDrill(
          gapsCount, gapsCount === 1 ? 'gap' : 'gaps',
          gapsCount > 0 ? 'tile-amber' : '',
          gapsCount > 0 ? () => pushFrame(listFrame('missing', detail.missing_documents || [],
            m => ({ kind: 'gap', label: m.label, priority: m.priority, full: m }),
            null, detail)) : null,
        ));
        tiles.appendChild(_kpiTileDrill(
          `${daysInStage}d`, 'in stage', '',
          () => pushFrame(_stageHistoryFrame(company, detail)),
        ));
        tiles.appendChild(_kpiTileDrill(
          custodyCount, custodyCount === 1 ? 'custody event' : 'custody events',
          '',
          // Doctrine: custody is rendered as a real branch on the spine
          // (drawCustodyBranch). The tile is a navigation hint — scroll
          // the operator to that branch and pulse it briefly so they
          // know where their click landed. No frame, no row list.
          custodyCount > 0 ? () => _focusCustodyBranch() : null,
        ));
        body.appendChild(tiles);

        // ── Recommended Action (the single sentence + one-click CTA) ───
        // Constitution: "No Hunting Rule" — the next step must present
        // itself, not be inferred from inspecting multiple panels.
        body.appendChild(recommendedActionBlock(company, detail));

        // ── State (calmer, secondary) ─────────────────────────────────
        body.appendChild(kv('stage', `${stage} · ${(company.stage_state || 'healthy').replace(/_/g, ' ')}`));
        body.appendChild(kv('age', `${detail.age_hours ?? 0}h`));
        body.appendChild(kv('review status', detail.review_status || '—'));
        body.appendChild(kv('intake id', detail.intake_id || '—', 'mono'));
        if (detail.project_id) body.appendChild(kv('project id', detail.project_id, 'mono'));

        const acts = detail.next_actions || [];
        if (acts.length > 1) {
          body.appendChild(sectionTitle('also'));
          acts.slice(1).forEach(a => {
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

        // Which branches anchor at this stage? Doctrine §5: branches
        // are anchored by timestamp, not by stage. A branch "belongs to"
        // a stage if its anchor X falls between the start of this stage
        // and the start of the next stage. Use the time axis to compute
        // both points and the window between them.
        const branches = computeBranches(detail);
        const axis = _timeAxis(detail);
        // (idx already computed above; reuse it — re-declaring as const
        //  here is a SyntaxError that crashes parse of the entire file,
        //  which in turn prevents vio.js from running and leaves VIO
        //  rendering as a black void below the env-ribbon. Caught by
        //  `node --check` on the JS bundle during the doctrine sweep
        //  on 2026-06-04 — root cause of the "VIO not connected" bug.)
        const thisX = axis.timeToX(_stageStartUtc(detail, stage.key));
        const nextKey = STAGES[idx + 1] && STAGES[idx + 1].key;
        const nextStart = nextKey ? _stageStartUtc(detail, nextKey) : null;
        const nextX = nextStart ? axis.timeToX(nextStart) : (L.spineX0 + L.spineWidth);
        const own = [...branches.above, ...branches.below].filter(b => {
          return b.anchorX >= thisX - 1 && b.anchorX < nextX;
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

  // ── KPI tile (Constitution: "State Before Detail") ─────────────────
  // A compact, declarative number + label that the operator reads in a
  // glance. Optional severity class (`tile-warn` / `tile-amber`) turns
  // the tile colour-positive only when the count is nonzero — staying
  // loyal to "stillness is the baseline."
  //
  // L2 rule: every visual artifact inside the universe is clickable and
  // drills to its source data. `kpiTile` keeps the calm form; the click
  // wiring lives in `_kpiTileDrill` so the tile can be inert when there
  // is nothing to drill to (zero count = no destination).
  function kpiTile(value, label, severityCls) {
    const t = el('div', 'vio-l2-tile' + (severityCls ? ' vio-l2-' + severityCls : ''));
    const v = el('div', 'vio-l2-tile-value');
    v.textContent = String(value);
    const l = el('div', 'vio-l2-tile-label');
    l.textContent = label;
    t.appendChild(v);
    t.appendChild(l);
    return t;
  }

  function _kpiTileDrill(value, label, severityCls, onClick) {
    const t = kpiTile(value, label, severityCls);
    if (onClick) {
      t.classList.add('vio-l2-tile--drill');
      t.setAttribute('role', 'button');
      t.setAttribute('tabindex', '0');
      t.title = `open ${label}`;
      t.addEventListener('click', onClick);
      t.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); }
      });
    } else {
      t.classList.add('vio-l2-tile--inert');
    }
    return t;
  }

  // Scroll the operator's view to the on-canvas custody branch and
  // pulse it briefly so they can see where their click landed.
  // Replaces the obsolete side-panel custody frame; the chain itself
  // lives in the main L2 canvas as a real branch off the intake anchor
  // (drawCustodyBranch above).
  function _focusCustodyBranch() {
    const group = document.getElementById('vio-l2-custody-group');
    if (!group) return;
    try {
      group.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (_) { /* older browsers */ }
    group.classList.remove('vio-l2-custody--pulse');
    void group.getBoundingClientRect();
    group.classList.add('vio-l2-custody--pulse');
    setTimeout(() => group.classList.remove('vio-l2-custody--pulse'), 1600);
  }

  // Retained for reference but no longer wired anywhere — the row-list
  // frame this used to render violates §11 (the line is information)
  // and has been replaced by drawCustodyBranch. Kept temporarily as a
  // dead block so a future contributor sees what was rejected and why.
  // TODO: remove after one release cycle.
  // eslint-disable-next-line no-unused-vars
  function _custodyFrame(custody) {
    return {
      title: 'chain of custody',
      render: body => {
        const events = (custody && custody.events) || [];
        if (!events.length) {
          body.appendChild(asHint('no custody events recorded for this intake yet'));
          return;
        }

        // Compute the time domain. Floor t=0 at the earliest event,
        // ceiling at the latest (or now). Both are ISO-UTC; rendering
        // is a simple x = (t - tMin) / (tMax - tMin) * width.
        const stamped = events
          .map(e => ({ ev: e, t: Date.parse(e.at_utc || '') || 0 }))
          .filter(p => p.t > 0)
          .sort((a, b) => a.t - b.t);
        if (!stamped.length) {
          body.appendChild(asHint('events present but no parseable timestamps'));
          return;
        }
        const tMin = stamped[0].t;
        const tMax = Math.max(stamped[stamped.length - 1].t, Date.now());
        const span = Math.max(1, tMax - tMin);

        // Header — minimal text, intentionally quiet.
        const head = el('div', 'vio-l2-custody-head');
        head.textContent =
          `${stamped.length} event${stamped.length === 1 ? '' : 's'} · ` +
          `custody=${custody.custody_status || 'unknown'} · ` +
          `${_fmtSpan(span)} elapsed`;
        body.appendChild(head);

        // The branch itself — an SVG line with shape markers.
        const SVG_NS = 'http://www.w3.org/2000/svg';
        const W = 720, H = 56, PAD = 16;
        const innerW = W - PAD * 2;
        const cy = H / 2;

        const svg = document.createElementNS(SVG_NS, 'svg');
        svg.setAttribute('class', 'vio-l2-custody-spine');
        svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
        svg.setAttribute('width', '100%');
        svg.setAttribute('preserveAspectRatio', 'none');

        // Density band — thickness encodes events / day, capped.
        const dayMs = 86400000;
        const days = Math.max(0.5, span / dayMs);
        const perDay = stamped.length / days;
        let band = 'normal';
        if (perDay <= 0.5)  band = 'idle';
        else if (perDay <= 2)   band = 'low';
        else if (perDay <= 8)   band = 'normal';
        else if (perDay <= 20)  band = 'high';
        else                    band = 'peak';

        const line = document.createElementNS(SVG_NS, 'line');
        line.setAttribute('class', 'vio-l2-custody-line');
        line.setAttribute('data-activity', band);
        line.setAttribute('x1', PAD);
        line.setAttribute('y1', cy);
        line.setAttribute('x2', W - PAD);
        line.setAttribute('y2', cy);
        svg.appendChild(line);

        // t=0 and now anchors.
        const startTick = document.createElementNS(SVG_NS, 'line');
        startTick.setAttribute('class', 'vio-l2-custody-tick');
        startTick.setAttribute('x1', PAD);
        startTick.setAttribute('x2', PAD);
        startTick.setAttribute('y1', cy - 6);
        startTick.setAttribute('y2', cy + 6);
        svg.appendChild(startTick);
        const endTick = document.createElementNS(SVG_NS, 'line');
        endTick.setAttribute('class', 'vio-l2-custody-tick');
        endTick.setAttribute('x1', W - PAD);
        endTick.setAttribute('x2', W - PAD);
        endTick.setAttribute('y1', cy - 6);
        endTick.setAttribute('y2', cy + 6);
        svg.appendChild(endTick);

        // Inline detail card (created once, populated on click).
        const detailCard = el('div', 'vio-l2-custody-detail');
        detailCard.hidden = true;

        // Shapes on the line. Channel → silhouette; ok/fail → colour.
        stamped.forEach(({ ev, t }) => {
          const x = PAD + ((t - tMin) / span) * innerW;
          const shape = _custodyShape(ev, x, cy);
          shape.setAttribute('data-source', String(ev.source || ''));
          shape.setAttribute('data-ok',
            String(ev.ok === false ? 'false' : 'true'));
          shape.setAttribute('class', 'vio-l2-custody-mark');
          shape.setAttribute('tabindex', '0');
          const nativeTitle = document.createElementNS(SVG_NS, 'title');
          nativeTitle.textContent =
            `${(ev.at_utc || '').replace('T', ' ').replace('Z', '')}  ` +
            `${String(ev.event || '').replace(/_/g, ' ')}`;
          shape.appendChild(nativeTitle);
          shape.addEventListener('click', () => _showCustodyDetail(detailCard, ev));
          shape.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              _showCustodyDetail(detailCard, ev);
            }
          });
          svg.appendChild(shape);
        });

        body.appendChild(svg);

        // Quiet time scale beneath the branch — single label pair,
        // not a numeric axis. Echoes the L1 temporal-scale hint.
        const scale = el('div', 'vio-l2-custody-scale');
        scale.innerHTML =
          `<span>${new Date(tMin).toISOString().slice(0, 10)}</span>` +
          `<span>${new Date(tMax).toISOString().slice(0, 10)}</span>`;
        body.appendChild(scale);

        body.appendChild(detailCard);
      },
    };
  }

  // Channel → shape silhouette. Same doctrinal vocabulary as L1
  // (square=healthy/done, triangle=warn/delay, hexagon=audit/binder,
  // diamond=communication, dot=upload/transaction). Coordinates are
  // small (5–7 px) so the chain reads as a row of shapes on a line,
  // not as a row of buttons.
  function _custodyShape(ev, x, cy) {
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const s = String(ev.source || '').toLowerCase();
    const evt = String(ev.event || '').toLowerCase();

    if (s === 'communications_ledger') {
      const p = document.createElementNS(SVG_NS, 'polygon');
      p.setAttribute('points',
        `${x - 5},${cy} ${x},${cy - 5} ${x + 5},${cy} ${x},${cy + 5}`);
      return p;
    }
    if (s === 'audit_receipt' || evt === 'binder_exported') {
      const p = document.createElementNS(SVG_NS, 'polygon');
      const r = 5;
      const pts = [];
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i - Math.PI / 2;
        pts.push(`${x + r * Math.cos(a)},${cy + r * Math.sin(a)}`);
      }
      p.setAttribute('points', pts.join(' '));
      return p;
    }
    if (s === 'delay_attribution') {
      const p = document.createElementNS(SVG_NS, 'polygon');
      p.setAttribute('points',
        `${x - 5},${cy + 5} ${x + 5},${cy + 5} ${x},${cy - 5}`);
      return p;
    }
    if (s === 'evidence_registry' || s === 'upload_custody') {
      const r = document.createElementNS(SVG_NS, 'rect');
      r.setAttribute('x', x - 4);
      r.setAttribute('y', cy - 4);
      r.setAttribute('width', 8);
      r.setAttribute('height', 8);
      return r;
    }
    if (evt === 'operator_archived' || ev.event === 'binder_exported') {
      const r = document.createElementNS(SVG_NS, 'rect');
      r.setAttribute('x', x - 4);
      r.setAttribute('y', cy - 4);
      r.setAttribute('width', 8);
      r.setAttribute('height', 8);
      r.setAttribute('rx', 1);
      return r;
    }
    const c = document.createElementNS(SVG_NS, 'circle');
    c.setAttribute('cx', x);
    c.setAttribute('cy', cy);
    c.setAttribute('r', 3.5);
    return c;
  }

  function _showCustodyDetail(card, ev) {
    card.hidden = false;
    const meta = ev.metadata || {};
    const lines = [
      `<div class="vio-l2-custody-detail-head">`,
      `  <span class="vio-l2-custody-detail-evt">${String(ev.event || '').replace(/_/g, ' ')}</span>`,
      `  <span class="vio-l2-custody-detail-when">${(ev.at_utc || '').replace('T', ' ').replace('Z', '')}</span>`,
      `</div>`,
      `<div class="vio-l2-custody-detail-src">source: ${ev.source || 'unknown'}${ev.ok === false ? ' · <strong>INTEGRITY FAIL</strong>' : ''}</div>`,
    ];
    const metaKeys = Object.keys(meta);
    if (metaKeys.length) {
      lines.push('<dl class="vio-l2-custody-detail-meta">');
      metaKeys.forEach(k => {
        const v = meta[k];
        const display = (typeof v === 'object') ? JSON.stringify(v) : String(v);
        lines.push(`<dt>${k}</dt><dd>${display}</dd>`);
      });
      lines.push('</dl>');
    }
    card.innerHTML = lines.join('');
  }

  function _fmtSpan(ms) {
    const days = ms / 86400000;
    if (days >= 1) return `${days.toFixed(days < 10 ? 1 : 0)}d`;
    const hours = ms / 3600000;
    if (hours >= 1) return `${hours.toFixed(1)}h`;
    const mins = ms / 60000;
    return `${mins.toFixed(0)}m`;
  }

  // Stage history frame — what the "in stage Xd" tile drills into. Shows
  // the chain of state transitions for this company so the operator can
  // see why we believe the company has been here for that long. Reads
  // straight from detail.timeline (built by services.vio_company_detail).
  function _stageHistoryFrame(company, detail) {
    return {
      title: 'stage history',
      render: body => {
        const timeline = (detail && detail.timeline) || [];
        if (!timeline.length) {
          body.appendChild(asHint('no timeline events recorded yet'));
          return;
        }
        body.appendChild(asProse(
          'time-since-last-movement for this company. Each row is one event ' +
          'that touched the intake on disk.'));
        timeline.forEach(ev => {
          const r = el('div', 'vio-l2-side-row');
          const left  = el('div', 'vio-l2-side-row-l');
          const right = el('div', 'vio-l2-side-row-r');
          left.textContent  = ev.label || ev.kind || ev.event || '(unnamed)';
          right.textContent = ev.when_human || ev.utc || ev.when || '';
          r.appendChild(left); r.appendChild(right);
          body.appendChild(r);
        });
      },
    };
  }

  // ── Recommended Action block (Constitution: "No Hunting Rule") ─────
  // One declarative sentence + one primary CTA. The sentence is the
  // bottleneck if present, else the first next_action, else a calm
  // confirmation. The CTA always resolves to a single click that takes
  // the operator to where they can complete the action.
  function recommendedActionBlock(company, detail) {
    const wrap = el('div', 'vio-l2-recommend');
    const sev  = (detail.bottleneck_severity || _bottleneckSeverity(company, detail));
    wrap.classList.add('vio-l2-recommend--' + sev);

    const head = el('div', 'vio-l2-recommend-head');
    head.textContent = _recommendHeadline(company, detail);
    wrap.appendChild(head);

    const sentence = el('div', 'vio-l2-recommend-sentence');
    sentence.textContent = _recommendSentence(company, detail);
    wrap.appendChild(sentence);

    const cta = _recommendCta(company, detail);
    if (cta) {
      const btn = el('a', 'vio-l2-recommend-cta');
      btn.textContent = cta.label;
      btn.href = cta.href;
      if (cta.external) { btn.target = '_blank'; btn.rel = 'noopener'; }
      wrap.appendChild(btn);
    }
    return wrap;
  }

  function _bottleneckSeverity(company, detail) {
    const st = (company.stage_state || '').toLowerCase();
    if (st === 'failed') return 'critical';
    if (st === 'waiting_client') return 'waiting';
    if (st === 'inconsistent') return 'amber';
    if (st === 'stalled') return 'amber';
    if (st === 'done') return 'complete';
    const review = (detail.review_status || '').toLowerCase();
    if (review === 'pending_review' || review === 'needs_review') return 'review';
    return 'processing';
  }

  function _recommendHeadline(company, detail) {
    const sev = _bottleneckSeverity(company, detail);
    return ({
      critical:   '⚡ CRITICAL — act now',
      waiting:    '📬 waiting on client',
      amber:      '◐ review the conflict',
      review:     '👁 operator review',
      processing: '🧠 organism is working',
      complete:   '✓ complete',
    })[sev] || 'next step';
  }

  function _recommendSentence(company, detail) {
    if (detail.bottleneck) return detail.bottleneck;
    const acts = detail.next_actions || [];
    if (acts.length) return acts[0];
    const st = (company.stage_state || '').toLowerCase();
    if (st === 'done') return 'Engagement complete. No outstanding items.';
    if (st === 'healthy') return 'No bottleneck. Organism is progressing the line on its own.';
    return 'Open the cockpit to inspect this company in detail.';
  }

  function _recommendCta(company, detail) {
    const sev    = _bottleneckSeverity(company, detail);
    const pid    = detail.project_id || '';
    const iid    = detail.intake_id || '';
    const target = pid || iid;
    if (!target) return null;
    const cockpitLink = '/ui/control.html#intake=' + encodeURIComponent(target);
    switch (sev) {
      case 'critical':
        return { label: 'Open in cockpit · resolve →', href: cockpitLink };
      case 'waiting':
        return { label: 'Send client reminder →', href: cockpitLink };
      case 'amber':
        return { label: 'Open review →', href: cockpitLink };
      case 'review':
        return { label: 'Open review →', href: cockpitLink };
      case 'processing':
        return { label: 'Monitor in cockpit →', href: cockpitLink };
      case 'complete': {
        if (pid) {
          return { label: 'Download deliverable binder →',
                   href: '/api/project/' + encodeURIComponent(pid) + '/export',
                   external: true };
        }
        return { label: 'Open in cockpit →', href: cockpitLink };
      }
      default:
        return { label: 'Open in cockpit →', href: cockpitLink };
    }
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
