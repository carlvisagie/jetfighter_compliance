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

    // Carl 2026-06-05 (the revolution mandate): "Make it a true work of
    // new level of Genius, imagination serving as the Apex of giving as
    // much information at a glance as we can imagine."
    //
    // The composition layers, drawn in z-order:
    //
    //   1. SPINE RIVER     — variable-thickness past + dashed future
    //   2. STAGE BACKBONE  — 7 ghost-hexagons across the spine (no text)
    //   3. NOW MARKER      — vertical glow at present-time X
    //   4. EVENT SHAPES    — papers / gaps / findings / etc. on/near spine,
    //                        sized by severity & bundled when crowded
    //   5. ORB             — state-coloured ring + age arc + initials,
    //                        click reveals card with full identity
    //   6. STATS PANEL     — top-right: 3 glance-numbers (papers, gaps,
    //                        stage age) for the unavoidable counts
    //   7. DEMAND MARKER   — the one breathing arrow above the spine
    //                        pointing at the most important next action

    const spineY = L.spineY;
    const axis   = _timeAxis(detail);
    const events = computeTimelineEvents(detail, axis);

    const w = Math.max(spineEndX(), L.spineX0 + L.spineWidth) + 240;
    const h = spineY + 160;

    const svg = svgEl('svg');
    svg.setAttribute('class', 'vio-l2-svg');
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);

    drawSpine(svg, company, spineY, axis, detail);
    drawTimelineEvents(svg, events, spineY, detail);
    drawOrb(svg, company, spineY);
    drawStatsPanel(svg, detail, w);
    drawDemandMarker(svg, detail, axis, spineY);

    canvas.appendChild(svg);
  }

  // ── Spine — the story line (Carl 2026-06-05 revolution) ──────────────
  //
  // Doctrine §11 made flesh: the spine is no longer a flat ruler. It is
  // a RIVER whose thickness encodes activity density per time-window, a
  // dashed-future ghost extending to the right edge, a glowing NOW
  // marker, and a ghost-hexagon backbone of the 7 KYC stages.
  //
  // Five forensic substrates speak through the spine:
  //
  //   1. River (past)  — variable-width filled path. Thin where nothing
  //      happened in a window, thick where many custody events landed.
  //      An operator reads the rhythm of work at one glance.
  //   2. Future tail   — thin dashed line from live-tip to spine end,
  //      signalling "journey not yet complete".
  //   3. Now marker    — vertical glowing bar at the X corresponding
  //      to Date.now(); a tiny inverted-triangle cap on top says
  //      "this is the present moment".
  //   4. Stage backbone — 7 hexagons across the spine (past=filled
  //      with state colour, current=glowing larger, future=ghost-
  //      dashed). NO TEXT LABELS. The shape order IS the meaning.
  //   5. Gap markers   — `||` glyphs at long quiet stretches between
  //      events (>=12h). Visible silences are themselves information.
  //
  // The skeleton path (no axis, no detail) renders just the flat thin
  // spine + future tail so the L2 canvas is never empty during loading.
  function drawSpine(svg, company, spineY = L.spineY, axis, detail) {
    if (!axis) axis = _timeAxis(detail);
    const events = (detail && detail.custody && detail.custody.events) || [];
    const lastEventT = events.length
      ? Math.max(...events.map(e => Date.parse(e.at_utc || '') || 0))
      : 0;
    const liveX = lastEventT > 0 ? axis.timeToX(lastEventT) : L.spineX0;
    const endX  = spineEndX();
    const state = company.stage_state || (detail && detail.stage_state) || 'healthy';

    // ── PAST: variable-thickness river (or thin flat line if no events) ──
    if (events.length && liveX > L.spineX0) {
      _drawSpineRiver(svg, spineY, events, axis, L.spineX0, liveX, state);
    } else {
      const flat = svgEl('line');
      flat.setAttribute('class', 'vio-l2-spine-past');
      flat.setAttribute('data-stage-state', state);
      flat.setAttribute('x1', L.spineX0);
      flat.setAttribute('x2', Math.max(L.spineX0 + 4, liveX));
      flat.setAttribute('y1', spineY);
      flat.setAttribute('y2', spineY);
      svg.appendChild(flat);
    }

    // ── FUTURE: dashed thin tail from live tip to spine end ──
    if (liveX < endX) {
      const future = svgEl('line');
      future.setAttribute('class', 'vio-l2-spine-future');
      future.setAttribute('x1', liveX);
      future.setAttribute('x2', endX);
      future.setAttribute('y1', spineY);
      future.setAttribute('y2', spineY);
      svg.appendChild(future);
    }

    // ── GAP MARKERS: `||` at >=12h silences ──
    _drawSpineGaps(svg, spineY, events, axis);

    // ── BREAK SCARS: red X-marks where critical/high findings landed ──
    // The river itself just shows activity density; the scar overlay
    // tells the operator "this is where it broke" without a single word.
    if (detail) _drawSpineScars(svg, spineY, detail, axis);

    // ── STAGE BACKBONE: 7 ghost-hexagons across the spine, no text ──
    _drawStageBackbone(svg, detail, axis, spineY, liveX);

    // ── NOW MARKER: glowing vertical bar at present-time X ──
    if (detail) _drawNowMarker(svg, axis, spineY, state);

    // ── Single quiet date label at the spine's left edge ──
    if (detail && axis.tMin) {
      const startLabel = svgEl('text');
      startLabel.setAttribute('class', 'vio-l2-spine-time-label');
      startLabel.setAttribute('x', L.spineX0);
      startLabel.setAttribute('y', spineY + 28);
      startLabel.setAttribute('text-anchor', 'start');
      startLabel.textContent = new Date(axis.tMin).toISOString().slice(0, 10);
      svg.appendChild(startLabel);
    }
  }

  // Build the river — a filled SVG path whose vertical extent at each
  // X encodes a MYRIAD of situations along the timeline (Carl 2026-
  // 06-05: "the timeline itself must convey a myriad of information
  // and situations — thicker lines for some things thinner for others
  // a broken line for some a choked out line in some cases"):
  //
  //   · BUSY  — many events in a window → river SWELLS
  //   · QUIET — few events              → river NARROWS
  //   · STALL — gap >= 24h with no events → river CHOKES (collapses
  //                                          to a hairline through
  //                                          the stall window)
  //   · BREAK — critical/high finding present → at the finding's X,
  //              river is OVERLAID with a vivid red X-scar via a
  //              second pass (drawn outside this function in JS so
  //              the scar always sits ON TOP of the river)
  //
  // Smoothed with a 3-point kernel so dense bursts read as a swell
  // instead of a comb. One <path> element, cheap to render.
  function _drawSpineRiver(svg, spineY, events, axis, x0, x1, state) {
    const BUCKETS = 80;
    const W = Math.max(1, x1 - x0);
    const counts = new Array(BUCKETS).fill(0);
    // Stamps sorted for stall detection.
    const stamps = [];
    events.forEach(e => {
      const t = Date.parse(e.at_utc || '') || 0;
      if (!t) return;
      stamps.push(t);
      const x = axis.timeToX(t);
      if (x < x0 || x > x1) return;
      const idx = Math.min(BUCKETS - 1, Math.max(0, Math.floor(((x - x0) / W) * BUCKETS)));
      counts[idx]++;
    });
    stamps.sort((a, b) => a - b);

    // Smooth counts.
    const smooth = counts.map((b, i) => {
      const a = counts[i - 1] || 0;
      const c = counts[i + 1] || 0;
      return (a + 2 * b + c) / 4;
    });
    const peak = Math.max(0.001, ...smooth);

    // ── STALL DETECTION ─────────────────────────────────────────────
    // Any inter-event gap >= 24h is a stall — the river chokes through
    // that X-range. Build a per-bucket boolean mask.
    const STALL_MS = 24 * 60 * 60 * 1000;
    const stallMask = new Array(BUCKETS).fill(false);
    for (let i = 1; i < stamps.length; i++) {
      const dt = stamps[i] - stamps[i - 1];
      if (dt < STALL_MS) continue;
      const xA = axis.timeToX(stamps[i - 1]);
      const xB = axis.timeToX(stamps[i]);
      const idxA = Math.max(0, Math.floor(((xA - x0) / W) * BUCKETS));
      const idxB = Math.min(BUCKETS - 1, Math.ceil(((xB - x0) / W) * BUCKETS));
      for (let j = idxA + 1; j < idxB; j++) stallMask[j] = true;
    }

    const MIN_HALF   = 1.4;   // px — quiet baseline
    const MAX_HALF   = 8.0;   // px — peak swell
    const STALL_HALF = 0.35;  // px — choked (almost invisible)
    const halves = smooth.map((v, i) => {
      if (stallMask[i]) return STALL_HALF;
      return MIN_HALF + (MAX_HALF - MIN_HALF) * (v / peak);
    });

    // Build the river path: top edge then bottom edge in reverse.
    const pts = halves.map((h, i) => ({
      x:   x0 + ((i + 0.5) / BUCKETS) * W,
      top: spineY - h,
      bot: spineY + h,
    }));
    let d = `M ${x0} ${spineY} `;
    pts.forEach(p => { d += `L ${p.x.toFixed(2)} ${p.top.toFixed(2)} `; });
    d += `L ${x1.toFixed(2)} ${spineY} `;
    for (let i = pts.length - 1; i >= 0; i--) {
      d += `L ${pts[i].x.toFixed(2)} ${pts[i].bot.toFixed(2)} `;
    }
    d += 'Z';

    const river = svgEl('path');
    river.setAttribute('class', 'vio-l2-spine-river');
    river.setAttribute('data-stage-state', state);
    river.setAttribute('d', d);
    svg.appendChild(river);

    // Soft live-tip glow at the rightmost end of the past river —
    // STATIC (no animation; recent activity is not a demand per
    // motion discipline). Reads as "the journey reaches up to here".
    const tip = svgEl('circle');
    tip.setAttribute('class', 'vio-l2-spine-livetip');
    tip.setAttribute('data-stage-state', state);
    tip.setAttribute('cx', x1);
    tip.setAttribute('cy', spineY);
    tip.setAttribute('r', 6);
    svg.appendChild(tip);
  }

  // Critical/high finding scars — drawn ON TOP of the river at the
  // X-positions where those findings landed. A small red X mark
  // visibly BREAKS the river at the moment of the failure. Called
  // after the river so the scar always sits above the fill.
  function _drawSpineScars(svg, spineY, detail, axis) {
    const findings = (detail && detail.findings) || [];
    findings.forEach(f => {
      const sev = f.severity || 'info';
      if (sev !== 'critical' && sev !== 'high') return;
      const t = Date.parse(f.detected_utc || f.at_utc || '') || 0;
      if (!t) return;
      const x = axis.timeToX(t);
      const r = 7;
      const scar = svgEl('g');
      scar.setAttribute('class', 'vio-l2-spine-scar');
      scar.setAttribute('data-severity', sev);
      const a = svgEl('line');
      a.setAttribute('x1', x - r); a.setAttribute('x2', x + r);
      a.setAttribute('y1', spineY - r); a.setAttribute('y2', spineY + r);
      scar.appendChild(a);
      const b = svgEl('line');
      b.setAttribute('x1', x - r); b.setAttribute('x2', x + r);
      b.setAttribute('y1', spineY + r); b.setAttribute('y2', spineY - r);
      scar.appendChild(b);
      const title = svgEl('title');
      title.textContent = (f.message || f.code || sev) + ' (' + sev + ')';
      scar.appendChild(title);
      svg.appendChild(scar);
    });
  }

  // Vertical glowing "you are here" bar — Doctrine §11. The cap on top
  // is a tiny inverted triangle pointing down at the spine so the
  // operator's eye snaps to NOW without a text label.
  function _drawNowMarker(svg, axis, spineY, state) {
    const x = axis.timeToX(Date.now());
    const g = svgEl('g');
    g.setAttribute('class', 'vio-l2-now');
    g.setAttribute('data-stage-state', state);

    const line = svgEl('line');
    line.setAttribute('class', 'vio-l2-now-line');
    line.setAttribute('x1', x); line.setAttribute('x2', x);
    line.setAttribute('y1', spineY - 60); line.setAttribute('y2', spineY + 60);
    g.appendChild(line);

    const cap = svgEl('polygon');
    cap.setAttribute('class', 'vio-l2-now-cap');
    cap.setAttribute('points',
      `${x},${spineY - 60} ${x - 6},${spineY - 70} ${x + 6},${spineY - 70}`);
    g.appendChild(cap);

    svg.appendChild(g);
  }

  // 7 hexagons across the spine — the canonical KYC backbone. NO TEXT
  // LABELS (Carl's directive — pictures over words). Past stages render
  // filled with the company's state colour; current stage glows; future
  // stages are ghost-dashed empty hexagons. Stage names live in <title>
  // for tooltip-on-hover only.
  function _drawStageBackbone(svg, detail, axis, spineY, liveX) {
    const stageTimestamps = STAGES.map(s => _stageStartUtc(detail, s.key));
    const startedCount = stageTimestamps.filter(t => t).length;
    const futureCount = STAGES.length - startedCount;
    const endX = spineEndX();
    const futureStep = futureCount > 0
      ? Math.max(40, (endX - liveX) / (futureCount + 1))
      : 0;
    let futureIndex = 0;
    const state = (detail && detail.stage_state) || 'healthy';

    STAGES.forEach((s, i) => {
      const tStart = stageTimestamps[i];
      let cx, kind;
      if (tStart) {
        cx = axis.timeToX(tStart);
        const isCurrent = (i === startedCount - 1);
        kind = isCurrent ? 'current' : 'past';
      } else {
        futureIndex++;
        cx = liveX + futureStep * futureIndex;
        kind = 'future';
      }
      const g = svgEl('g');
      g.setAttribute('class', `vio-l2-stage-hex vio-l2-stage-${kind}`);
      g.setAttribute('data-stage', s.key);
      if (kind === 'current') g.setAttribute('data-stage-state', state);

      const hex = _hexagon(cx, spineY, kind === 'current' ? 11 : 9);
      hex.setAttribute('class', 'vio-l2-stage-hex-shape');
      g.appendChild(hex);

      const title = svgEl('title');
      title.textContent = s.label;
      g.appendChild(title);

      svg.appendChild(g);
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

  // ── Orb — the company's symbol at rest ────────────────────────────────
  //
  // Carl 2026-06-05, said three ways:
  //   "the orb is company information... tel email address and so on"
  //   "you can NOT cram all that info into the orb without clicking
  //    to expand for the company information"
  //   (and his sketch labels "Company name & information" / "Tel email
  //    Address" sit NEXT TO the orb as annotations — not inside it)
  //
  // The orb is a SYMBOL for the company, not a billboard for its name.
  // At rest the only thing inside it is the company INITIALS (2–3
  // letters, generated from the first letters of each word, or the
  // first 2 letters of the domain if the name is a URL). Initials
  // always fit. No overflow. No banner. No clever wrapping.
  //
  // Clicking the orb toggles the expanded card next to it. THAT card
  // shows the full company NAME, tel, email, address — i.e. the rest
  // of "company information" that Carl said belongs behind the click.
  // Click anywhere else on the canvas collapses the card.
  function drawOrb(svg, company, spineY = L.spineY) {
    const detail = _activeDetail || {};
    const ictx   = detail.intake_context || {};
    const prof   = (detail.evidence && detail.evidence.profile) || {};
    const state  = detail.stage_state || company.stage_state || 'healthy';

    const g = svgEl('g');
    g.setAttribute('class', 'vio-l2-orb-group');
    g.setAttribute('data-stage-state', state);

    // Core static circle — stroke now driven by state colour via CSS
    // selectors keyed on data-stage-state on the parent group.
    const core = svgEl('circle');
    core.setAttribute('class', 'vio-l2-orb');
    core.setAttribute('cx', L.orbCx);
    core.setAttribute('cy', spineY);
    core.setAttribute('r', L.orbR);
    g.appendChild(core);

    // ── Age arc — thin ring inside the orb showing how much of the
    // stage-SLA window has been consumed. Starts at 12 o'clock and
    // sweeps clockwise. data-overdue="1" when ageH > SLA so CSS can
    // tint it red. Operator reads "this stage is fresh" vs "this stage
    // has been sitting" without a number.
    const ageH = _stageAgeHours(detail);
    const SLA_H = 48;
    const frac = Math.min(0.999, ageH / SLA_H);
    if (frac > 0.02) {
      const arc = _arc(
        L.orbCx, spineY, L.orbR - 7,
        -Math.PI / 2,
        -Math.PI / 2 + frac * 2 * Math.PI,
      );
      arc.setAttribute('class', 'vio-l2-orb-age-arc');
      arc.setAttribute('data-overdue', ageH > SLA_H ? '1' : '0');
      g.appendChild(arc);
    }

    // Initials inside — always fit, never overflow.
    const initials = _initialsForOrb(company);
    const initialsText = svgEl('text');
    initialsText.setAttribute('class', 'vio-l2-orb-initials');
    initialsText.setAttribute('x', L.orbCx);
    initialsText.setAttribute('y', spineY + 9);   // optical centre
    initialsText.setAttribute('text-anchor', 'middle');
    initialsText.textContent = initials;
    g.appendChild(initialsText);

    // Tiny "click-for-info" affordance — a quiet caret-down below the
    // initials so the operator knows the orb is interactive without
    // adding any motion or text. Hidden on hover -> replaced by full
    // initials brightening (CSS only).
    const hint = svgEl('text');
    hint.setAttribute('class', 'vio-l2-orb-hint');
    hint.setAttribute('x', L.orbCx);
    hint.setAttribute('y', spineY + L.orbR - 10);
    hint.setAttribute('text-anchor', 'middle');
    hint.textContent = '⌄';   // small caret-down glyph
    g.appendChild(hint);

    // ── Expanded-info card (collapsed by default) ─────────────────────
    // First row = the full company NAME (the thing that wouldn't fit
    // in the orb). Then tel / email / address. The card grows
    // vertically to fit; values are truncated only if they'd exceed
    // the card width.
    const fullName = (company.company_name || 'Unknown').trim();
    const cardItems = [
      { label: 'name',    value: fullName },
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

      const rowH  = 20;
      const padX  = 14;
      const padY  = 14;
      const cardW = 320;
      const cardH = cardItems.length * rowH + padY * 2;
      const cardX = L.orbCx + L.orbR + 14;
      const cardY = spineY - cardH / 2;

      const bg = svgEl('rect');
      bg.setAttribute('class', 'vio-l2-orb-card-bg');
      bg.setAttribute('x', cardX);
      bg.setAttribute('y', cardY);
      bg.setAttribute('width', cardW);
      bg.setAttribute('height', cardH);
      bg.setAttribute('rx', 6);
      card.appendChild(bg);

      cardItems.forEach((it, i) => {
        const y = cardY + padY + (i + 0.7) * rowH;
        const labelEl = svgEl('text');
        labelEl.setAttribute('class', 'vio-l2-orb-card-label');
        labelEl.setAttribute('x', cardX + padX);
        labelEl.setAttribute('y', y);
        labelEl.textContent = it.label;
        card.appendChild(labelEl);
        const valueEl = svgEl('text');
        valueEl.setAttribute('class', 'vio-l2-orb-card-value');
        valueEl.setAttribute('x', cardX + padX + 60);
        valueEl.setAttribute('y', y);
        // Card is 320px wide; minus label column (60) + padding (28) =
        // ~232px for the value. At 12px monospace, ~32 chars fit.
        const MAX = 38;
        valueEl.textContent = it.value.length > MAX
          ? it.value.slice(0, MAX - 1) + '…'
          : it.value;
        const title = svgEl('title');
        title.textContent = it.value;
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

  // Initials that always fit inside the orb. Strategy:
  //  1. If we have non-URL words, take the first letter of up to
  //     three of them (e.g. "Acme Corp Ltd" -> "ACL").
  //  2. If the name is a single URL-ish string (no spaces, contains
  //     '.'), take the first 2 letters of the leftmost host segment
  //     and uppercase (e.g. "purposefulliveccoaching.com" -> "PU").
  //  3. Else first 2 letters of whatever we've got, uppercased.
  //  4. Empty / "Unknown" -> "?".
  function _initialsForOrb(company) {
    const name = (company.company_name || '').trim();
    if (!name || /^unknown$/i.test(name)) return '?';
    const looksLikeUrl = !/\s/.test(name) && name.includes('.');
    if (looksLikeUrl) {
      const host = name.split('/')[0].split('@').pop();   // strip protocol/email-local
      const seg  = host.split('.')[0];
      return (seg.slice(0, 2) || '?').toUpperCase();
    }
    const words = name.split(/\s+/).filter(Boolean).slice(0, 3);
    if (words.length) {
      return words.map(w => w[0]).join('').toUpperCase().slice(0, 3);
    }
    return name.slice(0, 2).toUpperCase();
  }

  // ─────────────────────────────────────────────────────────────────────
  // BRANCH COMPOSITION  +  COLLISION AVOIDANCE
  // ─────────────────────────────────────────────────────────────────────
  // ─────────────────────────────────────────────────────────────────────
  // FLAT TIMELINE — events ON the spine (Carl 2026-06-05)
  //
  // Replaces the cluster-and-leaf system. Every meaningful unit of
  // company history is one discrete shape on the timeline at its
  // real timestamp:
  //
  //   □  square      — uploaded paper / generated paper
  //   ▲  triangle ↑  — issue / urgent context flag (sits just above spine)
  //   ▽  triangle ↓  — missing gap (sits just below spine, dashed if open)
  //   ⬡  hexagon    — phase completion (classification, evidence done)
  //   ○  circle     — milestone reached (tier approved, etc.)
  //   ◇  diamond    — payment (decision/transaction)
  //   ✱  starburst  — finding / blocker / broker (escalation)
  //
  // Position rules:
  //   - on-spine kinds render at Y = spineY (centred on the line)
  //   - above-spine kinds render at Y = spineY - 30
  //   - below-spine kinds render at Y = spineY + 30
  //   - collisions on the same row are resolved by nudging X right
  //
  // Drill-down click handlers are intentionally NO-OPS for now — the
  // side panel that used to receive them is gone, and we'll wire a
  // shape-local popover in a follow-up. A tooltip on hover (SVG
  // <title>) carries the label so the operator can still identify
  // each shape without text on the canvas itself (Carl: pictures
  // over words).
  // ─────────────────────────────────────────────────────────────────────

  const TL_SHAPE   = 16;
  const TL_GAP     = 6;
  const TL_OFFSET  = 30;   // px above/below the spine for off-spine kinds

  function computeTimelineEvents(detail, axis) {
    const events = [];
    const ictx   = detail.intake_context || {};
    const cls    = detail.classification || {};
    const pay    = detail.payment || {};
    const docs   = detail.uploaded_documents || [];
    const gen    = detail.generated_documents || [];
    const miss   = detail.missing_documents || [];
    const find   = detail.findings || [];
    const conf   = detail.confirmation_needed || [];

    // ── Issues / context flags (above the spine) ──────────────────────
    if (ictx.urgent) {
      events.push({
        kind: 'issue', side: 'above',
        ts: _branchStartUtc(detail, 'context'),
        label: 'urgent', sub: 'urgent', full: ictx,
      });
    }
    if (ictx.deadline) {
      events.push({
        kind: 'issue', side: 'above',
        ts: _branchStartUtc(detail, 'context'),
        label: `deadline ${ictx.deadline}`, sub: 'deadline', full: ictx,
      });
    }
    if (ictx.context) {
      events.push({
        kind: 'issue', side: 'above',
        ts: _branchStartUtc(detail, 'context'),
        label: ictx.context, sub: 'note', full: ictx,
      });
    }

    // ── Uploaded papers (on spine) ────────────────────────────────────
    docs.forEach(d => {
      events.push({
        kind: 'paper', side: 'on',
        ts: d.uploaded_utc || d.received_utc
            || _branchStartUtc(detail, 'docs'),
        label: d.original_name || d.stored_name || 'paper',
        status: d.status || 'on_disk',
        sub: 'uploaded',
        full: d,
      });
    });

    // ── Generated papers (on spine) ───────────────────────────────────
    gen.forEach(g => {
      events.push({
        kind: 'paper', side: 'on',
        ts: g.generated_utc || _branchStartUtc(detail, 'generated'),
        label: g.name || 'generated',
        sub: 'generated',
        full: g,
      });
    });

    // ── Classification = phase completion (on spine) ──────────────────
    if (cls.primary_category) {
      events.push({
        kind: 'phase', side: 'on',
        ts: _branchStartUtc(detail, 'category'),
        label: cls.primary_category,
        sub: 'classification',
        full: cls,
      });
    }

    // ── Missing gaps (below the spine, dashed) ────────────────────────
    miss.forEach(m => {
      events.push({
        kind: 'gap', side: 'below',
        ts: _branchStartUtc(detail, 'gaps'),
        label: m.label || 'gap',
        priority: m.priority || 'medium',
        sub: 'missing',
        full: m,
      });
    });

    // ── Confirmation needed (above the spine, open circle) ────────────
    conf.forEach(c => {
      events.push({
        kind: 'confirmation', side: 'above',
        ts: _branchStartUtc(detail, 'confirmation'),
        label: c.field || 'field needed',
        sub: 'confirmation',
        full: c,
      });
    });

    // ── Findings (above or below depending on severity) ───────────────
    find.forEach(f => {
      const sev = f.severity || 'info';
      events.push({
        kind: 'finding', side: (sev === 'critical' || sev === 'high') ? 'above' : 'below',
        ts: f.detected_utc || _branchStartUtc(detail, 'findings'),
        label: f.message || f.code || 'finding',
        severity: sev,
        sub: f.code || 'finding',
        full: f,
      });
    });

    // ── Payment (diamond on spine) ────────────────────────────────────
    if (pay && (pay.link || pay.amount || pay.link_sent_utc || pay.paid)) {
      events.push({
        kind: 'payment', side: 'on',
        ts: pay.link_sent_utc || _branchStartUtc(detail, 'payment'),
        label: pay.paid ? 'paid' : (pay.link ? 'link sent' : 'pending'),
        status: pay.paid ? 'paid' : 'pending',
        sub: 'payment',
        full: pay,
      });
    }

    // ── Tier approval = milestone (circle on spine) ───────────────────
    const reached = ['approved', 'payment_sent', 'verified_complete', 'archived'];
    if (reached.includes(detail.review_status)) {
      events.push({
        kind: 'milestone', side: 'on',
        ts: _branchStartUtc(detail, 'tier'),
        label: (detail.review_status || '').replace(/_/g, ' '),
        sub: 'tier',
        full: { review_status: detail.review_status },
      });
    }

    // ── Broker / completion (starburst on spine, far right) ───────────
    if (detail.review_status === 'archived' || detail.review_status === 'verified_complete') {
      events.push({
        kind: 'broker', side: 'on',
        ts: _branchStartUtc(detail, 'project'),
        label: detail.project_id ? `project ${detail.project_id}` : 'broker',
        sub: 'broker',
        full: { project_id: detail.project_id, review_status: detail.review_status },
      });
    }

    // ── Compute X for each event ──────────────────────────────────────
    events.forEach(ev => { ev.x = axis.timeToX(ev.ts); });

    // ── Bundle same-kind same-side neighbors into one weighted glyph ──
    // Within a 24-px window, N events of the same kind on the same
    // side collapse into ONE shape carrying a count badge. The worst
    // severity/priority among the children survives so the bundle's
    // colour and size still reflect the most important member.
    const bundled = _bundleTimelineEvents(events);

    // ── Resolve remaining same-row collisions ────────────────────────
    const sorted = bundled.slice().sort((a, b) => a.x - b.x);
    const lastX  = { on: -Infinity, above: -Infinity, below: -Infinity };
    sorted.forEach(ev => {
      const gap = _shapeRadiusFor(ev) * 2 + TL_GAP;
      const minNext = lastX[ev.side] + gap;
      ev.drawX = Math.max(ev.x, minNext);
      lastX[ev.side] = ev.drawX;
    });

    return sorted;
  }

  // ─── Bundling — collapse same-kind same-side neighbors ─────────────
  const _SEV_RANK = { info: 0, low: 1, medium: 2, high: 3, critical: 4 };
  const _PRI_RANK = { low: 0, medium: 1, high: 2, critical: 3 };
  function _sevRank(s) { return _SEV_RANK[s] != null ? _SEV_RANK[s] : 0; }
  function _priRank(p) { return _PRI_RANK[p] != null ? _PRI_RANK[p] : 0; }

  function _bundleTimelineEvents(events) {
    const BUNDLE_X = 24;
    const sorted = events.slice().sort((a, b) => {
      // Keep same-kind same-side neighbors adjacent in the input order
      if (a.x !== b.x) return a.x - b.x;
      if (a.side !== b.side) return a.side.localeCompare(b.side);
      return a.kind.localeCompare(b.kind);
    });
    const result = [];
    sorted.forEach(ev => {
      const last = result[result.length - 1];
      const sameTrack = last
        && last.side === ev.side
        && last.kind === ev.kind
        && Math.abs(last.x - ev.x) < BUNDLE_X;
      if (sameTrack) {
        last.count    = (last.count || 1) + 1;
        last.children = last.children || [last.full];
        last.children.push(ev.full);
        if (ev.severity && _sevRank(ev.severity) > _sevRank(last.severity)) last.severity = ev.severity;
        if (ev.priority && _priRank(ev.priority) > _priRank(last.priority)) last.priority = ev.priority;
        last.label    = `${last.kind} ×${last.count}`;
      } else {
        result.push(ev);
      }
    });
    return result;
  }

  // ─── Weight 0..1 by importance — drives both shape radius and X-gap ──
  function _eventWeight(ev) {
    if (ev.severity != null) {
      const w = { critical: 1, high: 0.78, medium: 0.55, low: 0.30, info: 0.10 };
      return w[ev.severity] != null ? w[ev.severity] : 0.40;
    }
    if (ev.priority != null) {
      const w = { critical: 1, high: 0.78, medium: 0.55, low: 0.30 };
      return w[ev.priority] != null ? w[ev.priority] : 0.40;
    }
    if (ev.count && ev.count > 1) return Math.min(1, 0.4 + ev.count * 0.1);
    return 0.35;
  }
  function _shapeRadiusFor(ev) {
    const baseR = TL_SHAPE / 2;
    return baseR + baseR * 1.6 * _eventWeight(ev);   // 8..~21 px
  }

  function drawTimelineEvents(svg, events, spineY, detail) {
    events.forEach(ev => {
      const y = ev.side === 'above' ? spineY - TL_OFFSET
              : ev.side === 'below' ? spineY + TL_OFFSET
              : spineY;
      drawTimelineEvent(svg, ev, ev.drawX, y, detail);
    });
  }

  function drawTimelineEvent(svg, ev, cx, cy, detail) {
    const g = svgEl('g');
    g.setAttribute('class', `vio-tle vio-tle-${ev.kind}`);
    g.setAttribute('data-kind', ev.kind);
    if (ev.sub)      g.setAttribute('data-sub',      ev.sub);
    if (ev.severity) g.setAttribute('data-severity', ev.severity);
    if (ev.priority) g.setAttribute('data-priority', ev.priority);
    if (ev.status)   g.setAttribute('data-status',   ev.status);
    if (ev.count && ev.count > 1) g.setAttribute('data-bundled', String(ev.count));

    const shape = _shapeForEvent(ev, cx, cy);
    if (shape) {
      // _shapeForEvent now returns a rich icon group with its own
      // `vio-icon vio-icon-${name}` class chain. APPEND the legacy
      // `vio-tle-shape` token so existing per-kind CSS rules keep
      // matching, but do not overwrite the icon's own classes.
      const existing = shape.getAttribute('class') || '';
      shape.setAttribute('class', (existing + ' vio-tle-shape').trim());
      g.appendChild(shape);
    }

    // Bundle count badge — only visible when N>1 collapsed into this glyph
    if (ev.count && ev.count > 1) {
      const r = _shapeRadiusFor(ev);
      const badge = svgEl('text');
      badge.setAttribute('class', 'vio-tle-count');
      badge.setAttribute('x', cx);
      badge.setAttribute('y', cy + 4);
      badge.setAttribute('text-anchor', 'middle');
      badge.textContent = String(ev.count);
      g.appendChild(badge);
    }

    // Tooltip — the label lives in SVG <title> so the canvas itself
    // stays text-free (pictures > words).
    const title = svgEl('title');
    title.textContent = ev.label || ev.kind;
    g.appendChild(title);

    svg.appendChild(g);
  }

  // ── ICON DISPATCH (Carl 2026-06-05: "go hog wild") ────────────────────
  //
  // Each event renders as a rich, recognizable PICTOGRAM (a folded-
  // corner page, an hourglass, a warning triangle with `!`, a finish
  // flag, an envelope, a dollar coin, a stop sign, a star, a checkmark
  // hexagon) instead of a generic geometric primitive. The pictogram
  // IS the meaning — the operator never needs to ask "what is this
  // shape?" because the shape already says.
  //
  // Every icon is a <g> containing 1..N styled paths so we can paint
  // multi-element glyphs (e.g. a paper with ruling-lines or a flag
  // with a stripe). All paths use one of a small palette of utility
  // classes (.vio-icon-fill, .vio-icon-outline, .vio-icon-stroke,
  // .vio-icon-glyph, etc.) and the kind class on the outer group
  // re-tints those utilities by event semantics.
  function _shapeForEvent(ev, cx, cy) {
    const r = _shapeRadiusFor(ev);
    const g = svgEl('g');
    g.setAttribute('class', 'vio-icon vio-icon-' + _iconNameFor(ev));
    switch (ev.kind) {
      case 'paper':        _iconPaper       (g, cx, cy, r, ev); break;
      case 'gap':          _iconGap         (g, cx, cy, r);     break;
      case 'issue':        _iconIssue       (g, cx, cy, r, ev); break;
      case 'phase':        _iconPhase       (g, cx, cy, r);     break;
      case 'milestone':    _iconMilestone   (g, cx, cy, r);     break;
      case 'confirmation': _iconConfirmation(g, cx, cy, r);     break;
      case 'payment':      _iconPayment     (g, cx, cy, r, ev); break;
      case 'finding':      _iconFinding     (g, cx, cy, r, ev); break;
      case 'broker':       _iconBroker      (g, cx, cy, r);     break;
      default: {
        const c = svgEl('circle');
        c.setAttribute('class', 'vio-icon-fill');
        c.setAttribute('cx', cx); c.setAttribute('cy', cy);
        c.setAttribute('r', Math.max(3, r * 0.35));
        g.appendChild(c);
      }
    }
    return g;
  }

  function _iconNameFor(ev) {
    if (ev.kind === 'paper'   && ev.sub      === 'generated') return 'paper-gen';
    if (ev.kind === 'issue'   && ev.sub      === 'urgent'   ) return 'urgent';
    if (ev.kind === 'issue'   && ev.sub      === 'deadline' ) return 'deadline';
    if (ev.kind === 'issue'   && ev.sub      === 'note'     ) return 'note';
    if (ev.kind === 'payment' && ev.status   === 'paid'     ) return 'coin';
    if (ev.kind === 'finding' && ev.severity === 'critical' ) return 'stop';
    return ev.kind;
  }

  // ── Pictogram drawers — each appends paths into the supplied group ───

  // Folded-corner page — universal "document" symbol. Generated docs
  // earn a lightning bolt inside (org-produced); uploaded docs get
  // three ruling lines (client-supplied).
  function _iconPaper(g, cx, cy, r, ev) {
    const c = r * 0.34;
    const body = svgEl('path');
    body.setAttribute('class', 'vio-icon-fill');
    body.setAttribute('d',
      `M ${cx - r} ${cy - r} ` +
      `L ${cx + r - c} ${cy - r} ` +
      `L ${cx + r} ${cy - r + c} ` +
      `L ${cx + r} ${cy + r} ` +
      `L ${cx - r} ${cy + r} Z`);
    g.appendChild(body);
    const fold = svgEl('path');
    fold.setAttribute('class', 'vio-icon-fold');
    fold.setAttribute('d',
      `M ${cx + r - c} ${cy - r} ` +
      `L ${cx + r - c} ${cy - r + c} ` +
      `L ${cx + r} ${cy - r + c}`);
    g.appendChild(fold);
    if (ev.sub === 'generated') {
      const bolt = svgEl('path');
      bolt.setAttribute('class', 'vio-icon-bolt');
      bolt.setAttribute('d',
        `M ${cx + r * 0.15} ${cy - r * 0.4} ` +
        `L ${cx - r * 0.25} ${cy + r * 0.05} ` +
        `L ${cx + r * 0.05} ${cy + r * 0.05} ` +
        `L ${cx - r * 0.15} ${cy + r * 0.5}`);
      g.appendChild(bolt);
    } else {
      [-0.20, 0.00, 0.20].forEach(yOff => {
        const ln = svgEl('line');
        ln.setAttribute('class', 'vio-icon-rule');
        ln.setAttribute('x1', cx - r * 0.45);
        ln.setAttribute('x2', cx + r * 0.45);
        ln.setAttribute('y1', cy + r * yOff);
        ln.setAttribute('y2', cy + r * yOff);
        g.appendChild(ln);
      });
    }
  }

  // Ghost paper — dashed outline with `?` inside. Reads as "an empty
  // document slot we don't yet have what should go there".
  function _iconGap(g, cx, cy, r) {
    const c = r * 0.34;
    const body = svgEl('path');
    body.setAttribute('class', 'vio-icon-outline');
    body.setAttribute('d',
      `M ${cx - r} ${cy - r} ` +
      `L ${cx + r - c} ${cy - r} ` +
      `L ${cx + r} ${cy - r + c} ` +
      `L ${cx + r} ${cy + r} ` +
      `L ${cx - r} ${cy + r} Z`);
    g.appendChild(body);
    const mark = svgEl('text');
    mark.setAttribute('class', 'vio-icon-glyph');
    mark.setAttribute('x', cx);
    mark.setAttribute('y', cy + r * 0.36);
    mark.setAttribute('text-anchor', 'middle');
    mark.textContent = '?';
    g.appendChild(mark);
  }

  // Issue — branches by sub: urgent→flame, deadline→hourglass,
  // note→speech-bubble, default→warning-triangle.
  function _iconIssue(g, cx, cy, r, ev) {
    if (ev.sub === 'deadline') return _drawHourglass(g, cx, cy, r);
    if (ev.sub === 'note')     return _drawSpeechBubble(g, cx, cy, r);
    if (ev.sub === 'urgent')   return _drawFlame(g, cx, cy, r);
    return _drawWarning(g, cx, cy, r);
  }

  function _drawHourglass(g, cx, cy, r) {
    const p = svgEl('path');
    p.setAttribute('class', 'vio-icon-fill');
    p.setAttribute('d',
      `M ${cx - r} ${cy - r} ` +
      `L ${cx + r} ${cy - r} ` +
      `L ${cx} ${cy} ` +
      `L ${cx + r} ${cy + r} ` +
      `L ${cx - r} ${cy + r} ` +
      `L ${cx} ${cy} Z`);
    g.appendChild(p);
    [-1, +1].forEach(s => {
      const cap = svgEl('line');
      cap.setAttribute('class', 'vio-icon-stroke-bold');
      cap.setAttribute('x1', cx - r - 1); cap.setAttribute('x2', cx + r + 1);
      cap.setAttribute('y1', cy + s * r); cap.setAttribute('y2', cy + s * r);
      g.appendChild(cap);
    });
  }

  function _drawSpeechBubble(g, cx, cy, r) {
    const rx = r * 0.25;
    const left = cx - r, right = cx + r, top = cy - r, bot = cy + r * 0.45;
    const body = svgEl('path');
    body.setAttribute('class', 'vio-icon-outline');
    body.setAttribute('d',
      `M ${left + rx} ${top} L ${right - rx} ${top} ` +
      `Q ${right} ${top} ${right} ${top + rx} ` +
      `L ${right} ${bot - rx} Q ${right} ${bot} ${right - rx} ${bot} ` +
      `L ${cx + r * 0.05} ${bot} L ${cx - r * 0.35} ${bot + r * 0.55} ` +
      `L ${cx - r * 0.15} ${bot} L ${left + rx} ${bot} ` +
      `Q ${left} ${bot} ${left} ${bot - rx} ` +
      `L ${left} ${top + rx} Q ${left} ${top} ${left + rx} ${top} Z`);
    g.appendChild(body);
  }

  function _drawFlame(g, cx, cy, r) {
    const p = svgEl('path');
    p.setAttribute('class', 'vio-icon-fill');
    p.setAttribute('d',
      `M ${cx} ${cy - r} ` +
      `Q ${cx + r} ${cy - r * 0.2} ${cx + r * 0.75} ${cy + r * 0.5} ` +
      `Q ${cx + r * 0.3} ${cy + r} ${cx} ${cy + r} ` +
      `Q ${cx - r * 0.3} ${cy + r} ${cx - r * 0.75} ${cy + r * 0.5} ` +
      `Q ${cx - r} ${cy - r * 0.2} ${cx} ${cy - r} Z`);
    g.appendChild(p);
    const inner = svgEl('path');
    inner.setAttribute('class', 'vio-icon-inner');
    inner.setAttribute('d',
      `M ${cx} ${cy - r * 0.4} ` +
      `Q ${cx + r * 0.32} ${cy + r * 0.05} ${cx + r * 0.22} ${cy + r * 0.55} ` +
      `Q ${cx} ${cy + r * 0.75} ${cx - r * 0.22} ${cy + r * 0.55} ` +
      `Q ${cx - r * 0.32} ${cy + r * 0.05} ${cx} ${cy - r * 0.4} Z`);
    g.appendChild(inner);
  }

  function _drawWarning(g, cx, cy, r) {
    const p = svgEl('path');
    p.setAttribute('class', 'vio-icon-fill');
    p.setAttribute('d',
      `M ${cx} ${cy - r} L ${cx + r} ${cy + r * 0.86} L ${cx - r} ${cy + r * 0.86} Z`);
    g.appendChild(p);
    const bang = svgEl('text');
    bang.setAttribute('class', 'vio-icon-glyph');
    bang.setAttribute('x', cx);
    bang.setAttribute('y', cy + r * 0.55);
    bang.setAttribute('text-anchor', 'middle');
    bang.textContent = '!';
    g.appendChild(bang);
  }

  // Phase completion — hexagon (echoes the stage backbone) with check.
  function _iconPhase(g, cx, cy, r) {
    const hex = _hexagon(cx, cy, r);
    hex.setAttribute('class', 'vio-icon-outline');
    g.appendChild(hex);
    const check = svgEl('path');
    check.setAttribute('class', 'vio-icon-check');
    check.setAttribute('d',
      `M ${cx - r * 0.45} ${cy + r * 0.05} ` +
      `L ${cx - r * 0.10} ${cy + r * 0.35} ` +
      `L ${cx + r * 0.50} ${cy - r * 0.35}`);
    g.appendChild(check);
  }

  // Milestone — 5-point star.
  function _iconMilestone(g, cx, cy, r) {
    const pts = [];
    for (let i = 0; i < 10; i++) {
      const a   = (Math.PI / 5) * i - Math.PI / 2;
      const rad = i % 2 === 0 ? r : r * 0.42;
      pts.push(
        (cx + rad * Math.cos(a)).toFixed(2) + ',' +
        (cy + rad * Math.sin(a)).toFixed(2)
      );
    }
    const star = svgEl('polygon');
    star.setAttribute('class', 'vio-icon-fill');
    star.setAttribute('points', pts.join(' '));
    g.appendChild(star);
  }

  // Confirmation needed — `?` in a circle.
  function _iconConfirmation(g, cx, cy, r) {
    const c = svgEl('circle');
    c.setAttribute('class', 'vio-icon-outline');
    c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', r);
    g.appendChild(c);
    const q = svgEl('text');
    q.setAttribute('class', 'vio-icon-glyph');
    q.setAttribute('x', cx);
    q.setAttribute('y', cy + r * 0.32);
    q.setAttribute('text-anchor', 'middle');
    q.textContent = '?';
    g.appendChild(q);
  }

  // Payment — envelope (link sent) or dollar coin (paid).
  function _iconPayment(g, cx, cy, r, ev) {
    if (ev.status === 'paid') {
      const c = svgEl('circle');
      c.setAttribute('class', 'vio-icon-fill');
      c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', r);
      g.appendChild(c);
      const d = svgEl('text');
      d.setAttribute('class', 'vio-icon-glyph');
      d.setAttribute('x', cx);
      d.setAttribute('y', cy + r * 0.32);
      d.setAttribute('text-anchor', 'middle');
      d.textContent = '$';
      g.appendChild(d);
      return;
    }
    const rect = svgEl('rect');
    rect.setAttribute('class', 'vio-icon-outline');
    rect.setAttribute('x', cx - r);
    rect.setAttribute('y', cy - r * 0.7);
    rect.setAttribute('width',  r * 2);
    rect.setAttribute('height', r * 1.4);
    rect.setAttribute('rx', 1);
    g.appendChild(rect);
    const flap = svgEl('path');
    flap.setAttribute('class', 'vio-icon-stroke');
    flap.setAttribute('d',
      `M ${cx - r} ${cy - r * 0.7} L ${cx} ${cy} L ${cx + r} ${cy - r * 0.7}`);
    g.appendChild(flap);
  }

  // Finding — critical → stop-sign octagon; everything else → warning.
  function _iconFinding(g, cx, cy, r, ev) {
    if (ev.severity === 'critical') {
      const pts = [];
      for (let i = 0; i < 8; i++) {
        const a = (Math.PI / 4) * i + Math.PI / 8;
        pts.push(
          (cx + r * Math.cos(a)).toFixed(2) + ',' +
          (cy + r * Math.sin(a)).toFixed(2)
        );
      }
      const oct = svgEl('polygon');
      oct.setAttribute('class', 'vio-icon-fill');
      oct.setAttribute('points', pts.join(' '));
      g.appendChild(oct);
      const bang = svgEl('text');
      bang.setAttribute('class', 'vio-icon-glyph');
      bang.setAttribute('x', cx);
      bang.setAttribute('y', cy + r * 0.32);
      bang.setAttribute('text-anchor', 'middle');
      bang.textContent = '!';
      g.appendChild(bang);
      return;
    }
    _drawWarning(g, cx, cy, r);
  }

  // Broker — finish flag on a pole.
  function _iconBroker(g, cx, cy, r) {
    const pole = svgEl('line');
    pole.setAttribute('class', 'vio-icon-stroke-bold');
    pole.setAttribute('x1', cx - r * 0.5); pole.setAttribute('x2', cx - r * 0.5);
    pole.setAttribute('y1', cy - r);       pole.setAttribute('y2', cy + r);
    g.appendChild(pole);
    const flag = svgEl('polygon');
    flag.setAttribute('class', 'vio-icon-fill');
    flag.setAttribute('points',
      `${cx - r * 0.5},${cy - r} ` +
      `${cx + r},${cy - r * 0.55} ` +
      `${cx - r * 0.5},${cy - r * 0.10}`);
    g.appendChild(flag);
    const stripe = svgEl('rect');
    stripe.setAttribute('class', 'vio-icon-inner');
    stripe.setAttribute('x', cx - r * 0.2);
    stripe.setAttribute('y', cy - r * 0.85);
    stripe.setAttribute('width',  r * 0.5);
    stripe.setAttribute('height', r * 0.3);
    g.appendChild(stripe);
  }

  function _hexagon(cx, cy, r) {
    const pts = [];
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - Math.PI / 6;
      pts.push(`${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`);
    }
    const poly = svgEl('polygon');
    poly.setAttribute('points', pts.join(' '));
    return poly;
  }

  function _starburst(cx, cy, r) {
    const pts = [];
    const inner = r * 0.42;
    for (let i = 0; i < 16; i++) {
      const a = (Math.PI / 8) * i - Math.PI / 2;
      const rad = i % 2 === 0 ? r : inner;
      pts.push(`${cx + rad * Math.cos(a)},${cy + rad * Math.sin(a)}`);
    }
    const poly = svgEl('polygon');
    poly.setAttribute('points', pts.join(' '));
    return poly;
  }

  // ─────────────────────────────────────────────────────────────────────
  // DEMAND MARKER — the ONE thing the operator must do next
  //
  // Doctrine §6 (motion discipline) + Carl 2026-06-05: continuous motion
  // is reserved exclusively for an unresolved demand on attention.
  // This marker IS that demand. It is the ONLY animated element on the
  // L2 canvas. The breathing stops the moment the demand is resolved.
  //
  // The label below the arrow is the one place on the canvas where text
  // is sanctioned — it's what the operator must do, expressed in 2-3
  // words, deliberately bigger than anything else on screen.
  // ─────────────────────────────────────────────────────────────────────

  function computeDemand(detail) {
    if (!detail) return null;
    const findings   = detail.findings || [];
    const miss       = detail.missing_documents || [];
    const conf       = detail.confirmation_needed || [];
    const pay        = detail.payment || {};
    const rs         = (detail.review_status || '').toLowerCase();
    const stageState = detail.stage_state || '';

    // Highest-priority demand wins. Ordered so safety/integrity beats
    // procedural backlog beats hygiene.
    const crit = findings.find(f => f.severity === 'critical' || f.severity === 'high');
    if (crit) {
      return { kind: 'finding', label: 'review finding', anchor: 'findings' };
    }
    if (rs === 'needs_info' || rs === 'abandoned_upload') {
      return { kind: 'client',  label: 'request info', anchor: 'context' };
    }
    if (stageState === 'failed') {
      return { kind: 'failed',  label: 'unblock — failed', anchor: null };
    }
    if (stageState === 'stalled') {
      return { kind: 'stall',   label: 'follow up · stalled', anchor: null };
    }
    if (stageState === 'waiting_client') {
      return { kind: 'client',  label: 'send reminder', anchor: 'gaps' };
    }
    const highMiss = miss.find(m => m.priority === 'high' || m.priority === 'critical');
    if (highMiss) {
      return { kind: 'gap',     label: 'request missing doc', anchor: 'gaps' };
    }
    if (conf.length) {
      return { kind: 'confirm', label: 'confirm fields', anchor: 'confirmation' };
    }
    if (miss.length) {
      return { kind: 'gap',     label: 'request missing', anchor: 'gaps' };
    }
    if (rs === 'pending_review' && (detail.uploaded_documents || []).length) {
      return { kind: 'review',  label: 'review intake', anchor: 'docs' };
    }
    if (pay && pay.link && !pay.paid) {
      return { kind: 'payment', label: 'follow up · payment', anchor: 'payment' };
    }
    return null;   // healthy / done — no demand, no motion
  }

  function drawDemandMarker(svg, detail, axis, spineY) {
    const demand = computeDemand(detail);
    if (!demand) return;

    // X-anchor: prefer the branch-opener timestamp; fall back to live
    // tip; fall back to "now" so the marker always lands somewhere
    // meaningful on the spine.
    const events = (detail && detail.custody && detail.custody.events) || [];
    const liveT  = events.reduce((m, e) => Math.max(m, Date.parse(e.at_utc || '') || 0), 0);
    const liveX  = liveT > 0 ? axis.timeToX(liveT) : axis.timeToX(Date.now());
    let x = liveX;
    if (demand.anchor) {
      const t = _branchStartUtc(detail, demand.anchor);
      if (t) x = axis.timeToX(t);
    }

    const g = svgEl('g');
    g.setAttribute('class', 'vio-l2-demand');
    g.setAttribute('data-kind', demand.kind);

    // Arrow points DOWN at the spine. Geometry: a chevron with a thin
    // shaft above, wings near the bottom, tip touching the event row.
    const tipY   = spineY - 38;
    const wingY  = spineY - 60;
    const topY   = spineY - 100;
    const wing   = 16;
    const shaft  = 6;
    const arrow = svgEl('polygon');
    arrow.setAttribute('class', 'vio-l2-demand-arrow');
    arrow.setAttribute('points',
      `${x},${tipY} ` +
      `${x - wing},${wingY} ` +
      `${x - shaft},${wingY} ` +
      `${x - shaft},${topY} ` +
      `${x + shaft},${topY} ` +
      `${x + shaft},${wingY} ` +
      `${x + wing},${wingY}`);
    g.appendChild(arrow);

    // Halo behind arrow — softer second pulse layer so the breathing
    // reads even at the edges of the operator's vision.
    const halo = svgEl('ellipse');
    halo.setAttribute('class', 'vio-l2-demand-halo');
    halo.setAttribute('cx', x);
    halo.setAttribute('cy', (topY + tipY) / 2);
    halo.setAttribute('rx', 24);
    halo.setAttribute('ry', 36);
    g.insertBefore(halo, arrow);

    // The single sanctioned text label on the canvas — 2-3 words.
    const label = svgEl('text');
    label.setAttribute('class', 'vio-l2-demand-label');
    label.setAttribute('x', x);
    label.setAttribute('y', topY - 12);
    label.setAttribute('text-anchor', 'middle');
    label.textContent = demand.label;
    g.appendChild(label);

    svg.appendChild(g);
  }

  // ─────────────────────────────────────────────────────────────────────
  // STATS PANEL — three giant glance-numbers in the top-right
  //
  // The ONLY unavoidable text + numerals on the canvas. They answer
  // the three quantitative questions the operator must answer in <5s:
  //   • papers in hand vs expected
  //   • gaps remaining (and how dangerous)
  //   • hours in current stage (and whether stalled)
  // Tone (--st-* colour) encodes severity without any extra text.
  // ─────────────────────────────────────────────────────────────────────
  function drawStatsPanel(svg, detail, canvasW) {
    if (!detail) return;
    const docs = detail.uploaded_documents || [];
    const miss = detail.missing_documents || [];
    const expected = (detail.intake_context || {}).expected_file_count
                     || (detail.expected_file_count || 0);
    const stageAgeH = _stageAgeHours(detail);

    const worstMissPri = miss.reduce((w, m) => {
      const p = _priRank(m.priority || 'medium');
      return p > w ? p : w;
    }, 0);

    const stats = [
      {
        big:    String(docs.length),
        tiny:   expected ? `/ ${expected}` : '',
        label:  'papers',
        tone:   (expected && docs.length >= expected) ? 'done'
              : (docs.length === 0)                    ? 'waiting'
              :                                          'healthy',
      },
      {
        big:    String(miss.length),
        tiny:   '',
        label:  'gaps',
        tone:   miss.length === 0   ? 'done'
              : worstMissPri >= 2   ? 'failed'
              :                       'waiting',
      },
      {
        big:    stageAgeH > 0 ? String(Math.round(stageAgeH)) : '–',
        tiny:   stageAgeH > 0 ? 'h'  : '',
        label:  'in stage',
        tone:   stageAgeH > 48 ? 'stalled'
              : stageAgeH > 24 ? 'waiting'
              :                  'healthy',
      },
    ];

    const colW = 110;
    const panelW = colW * stats.length;
    const panelX = canvasW - panelW - 24;
    const panelY = 28;

    const g = svgEl('g');
    g.setAttribute('class', 'vio-l2-stats');
    stats.forEach((s, i) => {
      const sx = panelX + i * colW;
      const block = svgEl('g');
      block.setAttribute('class', 'vio-l2-stat');
      block.setAttribute('data-tone', s.tone);

      const big = svgEl('text');
      big.setAttribute('class', 'vio-l2-stat-big');
      big.setAttribute('x', sx);
      big.setAttribute('y', panelY + 30);
      big.setAttribute('text-anchor', 'start');
      big.textContent = s.big;
      block.appendChild(big);

      if (s.tiny) {
        const tiny = svgEl('text');
        tiny.setAttribute('class', 'vio-l2-stat-tiny');
        // Position tiny suffix to the right of the big number — adjust
        // X based on big string length so different magnitudes don't
        // collide.
        tiny.setAttribute('x', sx + 16 + (s.big.length * 18));
        tiny.setAttribute('y', panelY + 30);
        tiny.setAttribute('text-anchor', 'start');
        tiny.textContent = s.tiny;
        block.appendChild(tiny);
      }

      const lbl = svgEl('text');
      lbl.setAttribute('class', 'vio-l2-stat-label');
      lbl.setAttribute('x', sx);
      lbl.setAttribute('y', panelY + 48);
      lbl.setAttribute('text-anchor', 'start');
      lbl.textContent = s.label;
      block.appendChild(lbl);

      g.appendChild(block);
    });
    svg.appendChild(g);
  }

  // Hours since the most recent custody event — a proxy for how long
  // the current stage has been active without progress.
  function _stageAgeHours(detail) {
    const events = (detail && detail.custody && detail.custody.events) || [];
    if (!events.length) return 0;
    const last = events.reduce((m, e) => Math.max(m, Date.parse(e.at_utc || '') || 0), 0);
    if (!last) return 0;
    return Math.max(0, (Date.now() - last) / 3600000);
  }

  // SVG arc primitive — used for the orb's age-arc ring.
  function _arc(cx, cy, r, aStart, aEnd) {
    const x0 = cx + r * Math.cos(aStart);
    const y0 = cy + r * Math.sin(aStart);
    const x1 = cx + r * Math.cos(aEnd);
    const y1 = cy + r * Math.sin(aEnd);
    const large = (aEnd - aStart) > Math.PI ? 1 : 0;
    const path = svgEl('path');
    path.setAttribute('d',
      `M ${x0.toFixed(2)} ${y0.toFixed(2)} ` +
      `A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`);
    path.setAttribute('fill', 'none');
    return path;
  }

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
