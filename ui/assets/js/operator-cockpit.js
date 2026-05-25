/**
 * Operator cockpit — workflow steering + contextual knowledge from /api/operator/cockpit and /api/knowledge/*
 */
(function (global) {
  'use strict';

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function mdToHtml(md) {
    if (!md) return '<p>No content (file missing on server).</p>';
    let html = esc(md);
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => '<ul>' + m + '</ul>');
    html = html.replace(/\n\n/g, '</p><p>');
    return '<p>' + html + '</p>';
  }

  async function api(path) {
    const r = await fetch(path, { credentials: 'same-origin' });
    if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
    return r.json();
  }

  function renderCommandStrip(root, c) {
    const el = root.querySelector('[data-cockpit="command"]');
    if (!el) return;
    const rag = c.rag || '—';
    const ragClass =
      rag === 'green' ? 'ok' : rag === 'red' ? 'bad' : rag === 'amber' ? 'warn' : 'info';
    const blockers =
      (c.blockers || [])
        .map((b) => '<span class="cockpit-blocker">' + esc(b.message) + '</span>')
        .join('') || '<span class="cockpit-blocker" style="opacity:0.5;border-color:var(--kyc-line);color:var(--kyc-text-dim);background:transparent;">No blockers</span>';

    el.innerHTML =
      '<div class="cockpit-project-picker">' +
      '<div class="kyc-field"><label for="cockpitProject">Active project</label>' +
      '<select id="cockpitProject"><option value="">Loading…</option></select></div>' +
      '<div class="kyc-field"><label for="cockpitMode">Operator mode</label>' +
      '<select id="cockpitMode">' +
      '<option value="">Auto (from workflow)</option>' +
      '<option value="acquisition">Acquisition</option>' +
      '<option value="acquisition_discovery">Lead discovery</option>' +
      '<option value="inquiry">Inquiry</option>' +
      '<option value="intake">Intake</option>' +
      '<option value="evidence">Evidence</option>' +
      '<option value="binder">Binder / export</option>' +
      '<option value="event_logging">Event logging</option>' +
      '<option value="self_heal">Self-heal</option>' +
      '</select></div>' +
      '<button type="button" class="btn secondary" id="cockpitReload">Update cockpit</button>' +
      '</div>' +
      '<div class="cockpit-command-grid">' +
      '<div><div class="label">Customer / project</div><div class="value">' +
      esc(c.customer_label) +
      '<br><small>' +
      esc(c.project_id || '—') +
      '</small></div></div>' +
      '<div><div class="label">Workflow phase</div><div class="value">' +
      esc(c.workflow_phase) +
      '</div></div>' +
      '<div><div class="label">Next required step</div><div class="value">' +
      esc((c.next_step && c.next_step.title) || '—') +
      '</div></div>' +
      '<div><div class="label">RAG</div><div class="value"><span class="org-card-state ' +
      ragClass +
      '">' +
      esc(rag) +
      '</span></div></div>' +
      '</div>' +
      '<div class="cockpit-do-now"><strong>What Carl should do now</strong><p>' +
      esc(c.do_now) +
      '</p></div>' +
      '<p class="cockpit-why"><strong>Why it matters:</strong> ' +
      esc(c.why_it_matters) +
      '</p>' +
      '<div class="cockpit-blockers">' +
      blockers +
      '</div>';
  }

  function renderGuidance(root, g) {
    const el = root.querySelector('[data-cockpit="guidance"]');
    if (!el || !g) return;
    const checks = (g.check || []).map((c) => '<li>' + esc(c) + '</li>').join('');
    const links = (g.links || [])
      .map((l) => {
        if (l.topic) {
          return (
            '<a href="#" data-learn-topic="' +
            esc(l.topic) +
            '">' +
            esc(l.label) +
            '</a>'
          );
        }
        return '<a href="' + esc(l.href) + '">' + esc(l.label) + '</a>';
      })
      .join(' · ');

    el.innerHTML =
      '<h3>' +
      esc(g.title) +
      '</h3>' +
      '<div class="cockpit-guidance">' +
      '<dl><dt>Plain English</dt><dd>' +
      esc(g.explain) +
      '</dd>' +
      '<dt>What good looks like</dt><dd>' +
      esc(g.good_looks_like) +
      '</dd>' +
      '<dt>What can go wrong</dt><dd>' +
      esc(g.can_go_wrong) +
      '</dd>' +
      '<dt>What to check</dt><dd><ul>' +
      checks +
      '</ul></dd>' +
      '<dt>Exact next action</dt><dd>' +
      esc(g.next_action) +
      '</dd></dl></div>' +
      '<p style="margin-top:1rem;font-size:var(--kyc-text-sm);">' +
      links +
      ' · <button type="button" class="btn secondary" id="learnThisStep">Learn this step</button></p>';
  }

  function renderTopicList(container, topics) {
    if (!container) return;
    if (!topics.length) {
      container.innerHTML = '<li>No topics for this phase.</li>';
      return;
    }
    container.innerHTML = topics
      .map(
        (t) =>
          '<li><a href="#" data-learn-topic="' +
          esc(t.id) +
          '">' +
          esc(t.title) +
          '</a><br><small>' +
          esc(t.summary) +
          '</small></li>'
      )
      .join('');
  }

  async function loadTopic(topicId, bodyEl, titleEl) {
    const data = await api('/api/knowledge/topic/' + encodeURIComponent(topicId));
    const t = data.topic;
    if (titleEl) titleEl.textContent = t.title;
    if (bodyEl) {
      bodyEl.innerHTML =
        '<p class="org-metric-foot">Source: ' +
        esc(t.source_path) +
        (t.missing ? ' (missing)' : '') +
        '</p>' +
        '<div class="cockpit-topic-body">' +
        mdToHtml(t.content_markdown) +
        '</div>';
    }
  }

  async function searchKnowledge(root, q, phase) {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (phase) params.set('phase', phase);
    const data = await api('/api/knowledge/search?' + params.toString());
    const list = root.querySelector('[data-cockpit="topic-list"]');
    renderTopicList(list, data.topics || []);
    const gloss = root.querySelector('[data-cockpit="glossary-hits"]');
    if (gloss && data.glossary_hits && data.glossary_hits.length) {
      gloss.innerHTML =
        '<dl class="cockpit-glossary">' +
        data.glossary_hits
          .map(
            (g) =>
              '<dt>' + esc(g.term) + '</dt><dd>' + esc(g.definition) + '</dd>'
          )
          .join('') +
        '</dl>';
    } else if (gloss) gloss.innerHTML = '';
  }

  async function refreshCockpit(root, projectId, mode) {
    const params = new URLSearchParams();
    if (projectId) params.set('project_id', projectId);
    if (mode) params.set('mode', mode);
    const data = await api('/api/operator/cockpit?' + params.toString());
    const c = data.cockpit;
    renderCommandStrip(root, c);
    renderGuidance(root, c.guidance);

    const phase = c.learn_phase || '';
    const topics = await api(
      '/api/knowledge/search?phase=' + encodeURIComponent(phase) + '&limit=12'
    );
    renderTopicList(root.querySelector('[data-cockpit="topic-list"]'), topics.topics || []);

    const sel = root.querySelector('#cockpitProject');
    if (sel && sel.dataset.loaded !== '1') {
      const pr = await api('/api/projects');
      const projects = pr.projects || [];
      sel.innerHTML =
        projects
          .slice()
          .reverse()
          .map(
            (p) =>
              '<option value="' +
              esc(p) +
              '"' +
              (p === c.project_id ? ' selected' : '') +
              '>' +
              esc(p) +
              '</option>'
          )
          .join('') || '<option value="">No projects</option>';
      sel.dataset.loaded = '1';
    } else if (sel && projectId) {
      sel.value = projectId;
    }

    const modeSel = root.querySelector('#cockpitMode');
    if (modeSel && mode) modeSel.value = mode;

    root.querySelector('#learnThisStep')?.addEventListener('click', () => {
      const first = (c.knowledge_topic_ids || [])[0];
      if (first) {
        loadTopic(
          first,
          root.querySelector('[data-cockpit="topic-body"]'),
          root.querySelector('[data-cockpit="topic-title"]')
        );
      }
    });

    root.querySelectorAll('[data-learn-topic]').forEach((a) => {
      a.addEventListener('click', (ev) => {
        ev.preventDefault();
        loadTopic(
          a.getAttribute('data-learn-topic'),
          root.querySelector('[data-cockpit="topic-body"]'),
          root.querySelector('[data-cockpit="topic-title"]')
        );
      });
    });

    return c;
  }

  function bindKnowledgeSearch(root) {
    const input = root.querySelector('#knowledgeSearchInput');
    const btn = root.querySelector('#knowledgeSearchBtn');
    const run = () => {
      const phase = root.querySelector('#cockpitMode')?.value || '';
      searchKnowledge(root, input?.value || '', phase);
    };
    btn?.addEventListener('click', run);
    input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') run();
    });
  }

  async function init(root) {
    bindKnowledgeSearch(root);
    root.querySelector('#cockpitReload')?.addEventListener('click', () => {
      refreshCockpit(
        root,
        root.querySelector('#cockpitProject')?.value,
        root.querySelector('#cockpitMode')?.value
      );
    });
    root.querySelector('#cockpitProject')?.addEventListener('change', () => {
      refreshCockpit(root, root.querySelector('#cockpitProject')?.value, root.querySelector('#cockpitMode')?.value);
    });
    root.querySelector('#cockpitMode')?.addEventListener('change', () => {
      refreshCockpit(root, root.querySelector('#cockpitProject')?.value, root.querySelector('#cockpitMode')?.value);
    });
    const catalog = await api('/api/knowledge/catalog');
    const note = root.querySelector('[data-cockpit="catalog-note"]');
    if (note) note.textContent = catalog.fragmentation_note || '';
    const glossFull = root.querySelector('[data-cockpit="glossary-full"]');
    if (glossFull && catalog.glossary) {
      glossFull.innerHTML =
        '<dl class="cockpit-glossary">' +
        catalog.glossary
          .map(
            (g) =>
              '<dt>' + esc(g.term) + '</dt><dd>' + esc(g.definition) + '</dd>'
          )
          .join('') +
        '</dl>';
    }
    await refreshCockpit(root, '', '');
  }

  global.OperatorCockpit = { init, refreshCockpit, loadTopic, api };
})(typeof window !== 'undefined' ? window : globalThis);
