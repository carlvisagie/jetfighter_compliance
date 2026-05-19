# Task 14 — platform UI quality (shop.html standard)
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "ui"
D = "div"

STYLES = (
    '  <link rel="stylesheet" href="/ui/assets/styles/design-system.css">\n'
    '  <link rel="stylesheet" href="/ui/assets/styles/layout.css">\n'
    '  <link rel="stylesheet" href="/ui/assets/styles/components.css">\n'
)
OPS = STYLES + '  <link rel="stylesheet" href="/ui/assets/styles/ops-dashboard.css">\n'

OPS_NAV = f"""  <header class="kyc-topbar">
    <a class="kyc-brand" href="/ui/shop.html">Keep<span>YourContracts</span></a>
    <nav class="kyc-nav kyc-nav--ops" aria-label="Operations">
      <a href="/ui/control.html">Control</a>
      <a href="/ui/command.html">Command</a>
      <a href="/ui/status.html">Status</a>
      <a href="/ui/inbox.html">Inbox</a>
      <a href="/ui/shop.html">Public site</a>
    </nav>
  </header>
"""

PUBLIC_NAV = f"""  <header class="kyc-topbar">
    <a class="kyc-brand" href="/ui/shop.html">Keep<span>YourContracts</span></a>
    <nav class="kyc-nav" aria-label="Primary">
      <a href="/ui/shop.html">Services</a>
      <a href="/ui/inquiry.html">Contact</a>
    </nav>
  </header>
"""

CHECKS = """
                <div class="kyc-check"><label><input type="checkbox" name="ext_cmmc_l2_c3pao"> CMMC L2 (C3PAO) required</label></div>
                <motion class="kyc-check"><label><input type="checkbox" name="ext_gs1"> GS1 GTIN/GLN needed</label></motion>
                <div class="kyc-check"><label><input type="checkbox" name="ext_docusign"> DocuSign/Adobe envelopes required</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_eidas"> Qualified eSignature (eIDAS)</label></motion>
                <div class="kyc-check"><label><input type="checkbox" name="ext_lab_tests"> Lab tests (CE/EMC/Radio)</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_pentest"> External penetration test</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_vuln_scans"> External vulnerability scans</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_iso27001"> ISO 27001 certificate</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_soc2"> SOC 2 report</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_pci"> PCI DSS (ASV/ROC)</label></motion>
                <div class="kyc-check"><label><input type="checkbox" name="ext_legal"> Privacy/legal counsel</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_background"> Background checks</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_worm"> WORM / immutable retention</label></div>
                <motion class="kyc-check"><label><input type="checkbox" name="ext_translation"> Certified translation</label></motion>
                <div class="kyc-check"><label><input type="checkbox" name="ext_timestamp"> Qualified timestamp / notarization</label></div>
                <div class="kyc-check"><label><input type="checkbox" name="ext_rohs"> Material tests (RoHS/REACH)</label></div>
""".replace("<motion", "<" + D).replace("</motion>", "</" + D + ">")

# Fix CHECKS - I made errors in template. Build checks properly
CHECKS = ""
for name, label in [
    ("ext_cmmc_l2_c3pao", "CMMC L2 (C3PAO) required"),
    ("ext_gs1", "GS1 GTIN/GLN needed"),
    ("ext_docusign", "DocuSign/Adobe envelopes required"),
    ("ext_eidas", "Qualified eSignature (eIDAS)"),
    ("ext_lab_tests", "Lab tests (CE/EMC/Radio)"),
    ("ext_pentest", "External penetration test"),
    ("ext_vuln_scans", "External vulnerability scans"),
    ("ext_iso27001", "ISO 27001 certificate"),
    ("ext_soc2", "SOC 2 report"),
    ("ext_pci", "PCI DSS (ASV/ROC)"),
    ("ext_legal", "Privacy/legal counsel"),
    ("ext_background", "Background checks"),
    ("ext_worm", "WORM / immutable retention"),
    ("ext_translation", "Certified translation"),
    ("ext_timestamp", "Qualified timestamp / notarization"),
    ("ext_rohs", "Material tests (RoHS/REACH)"),
]:
    CHECKS += f'                <{D} class="kyc-check"><label><input type="checkbox" name="{name}"> {label}</label></{D}>\n'

(UI / "intake.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KeepYourContracts | Compliance Intake</title>
{STYLES}
</head>
<body class="kyc-page">
{PUBLIC_NAV}
  <main class="kyc-main">
    <section class="kyc-hero">
      <span class="kyc-badge">Client intake</span>
      <h1>Structured compliance intake</h1>
      <p>Complete the form below so our workflow engine can prepare your onboarding path, requirements map, and evidence collection structure.</p>
    </section>
    <div class="kyc-flow-steps" aria-label="Onboarding flow">
      <{D} class="kyc-flow-step"><strong>Step 1</strong> Inquiry</{D}>
      <{D} class="kyc-flow-step kyc-flow-step--active"><strong>Step 2</strong> Intake</{D}>
      <{D} class="kyc-flow-step"><strong>Step 3</strong> Evidence upload</{D}>
    </{D}>
    <section class="kyc-grid kyc-grid--intake">
      <article class="kyc-card kyc-card--flat">
        <span class="kyc-label-overline">Secure intake form</span>
        <h2>Organization details</h2>
        <form id="f" class="kyc-form">
          <input type="hidden" id="token" name="token" />
          <{D} class="kyc-form-grid">
            <{D} class="kyc-field"><label>Company Name</label><input name="company" required></{D}>
            <{D} class="kyc-field"><label>Primary Contact</label><input name="contact" required></{D}>
            <{D} class="kyc-field"><label>Phone</label><input name="phone"></{D}>
            <{D} class="kyc-field"><label>Email</label><input name="email" type="email"></{D}>
            <{D} class="kyc-field kyc-field--full"><label>Notes</label><textarea name="notes"></textarea></{D}>
          </{D}>
          <span class="kyc-label-overline" style="margin-top:2rem;display:block;">External requirements</span>
          <{D} class="kyc-check-grid">
{CHECKS}          </{D}>
          <button class="kyc-btn kyc-btn--primary kyc-btn--block" type="submit">Start compliance intake</button>
        </form>
      </article>
      <aside class="kyc-card kyc-card--flat">
        <span class="kyc-label-overline">Mobile &amp; trust</span>
        <h2>Continue on mobile</h2>
        <p>Scan to upload evidence and supporting documents from your phone.</p>
        <{D} class="kyc-qr-block">
          <img src="/ui/assets/qr/kyc_upload_qr.png" alt="Compliance upload QR">
        </{D}>
        <{D} class="kyc-step"><span class="kyc-step-num">1</span><span class="kyc-step-text">Open the secure upload portal with your phone camera.</span></{D}>
        <{D} class="kyc-step"><span class="kyc-step-num">2</span><span class="kyc-step-text">Upload contracts, policies, certifications, and supporting documentation.</span></{D}>
        <{D} class="kyc-step"><span class="kyc-step-num">3</span><span class="kyc-step-text">Your workflow updates as evidence is received.</span></{D}>
        <{D} class="kyc-trust-grid" style="margin-top:1.5rem;">
          <{D} class="kyc-trust-item"><strong>Evidence-centric workflow</strong><p>Traceability and audit-ready operations.</p></{D}>
          <{D} class="kyc-trust-item"><strong>Operational simplicity</strong><p>Reduce friction while improving accountability.</p></{D}>
          <{D} class="kyc-trust-item"><strong>Enterprise readiness</strong><p>Built for regulated environments.</p></{D}>
        </{D}>
      </aside>
    </section>
  </main>
  <footer class="kyc-footer">KeepYourContracts.com · Enterprise Compliance Workflow Platform</footer>
  <script src="/ui/intake.js"></script>
</body>
</html>
""".replace("<motion", "<" + D).replace("</motion>", "</" + D + ">"),
    encoding="utf-8",
)
print("wrote intake.html")

# Fix status.html
(UI / "status.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KeepYourContracts | Project Status</title>
{OPS}
</head>
<body class="kyc-page kyc-surface-ops">
{OPS_NAV}
  <{D} class="kyc-ops-header">
    <{D}>
      <h1>Project status</h1>
      <p class="kyc-ops-subtitle">Workflow steps · external costs · vendor RFQ</p>
    </{D}>
  </{D}>
  <main class="kyc-main kyc-main--ops">
    <section class="kyc-section" style="padding-top:0;">
      <article class="card kyc-project-list">
        <span class="kyc-label-overline">Active projects</span>
        <h2>Select a project</h2>
        <{D} id="list" class="kyc-loading">Loading…</{D}>
      </article>
    </section>
    <section class="kyc-section">
      <header class="kyc-section-head">
        <span class="kyc-label-overline">Detail</span>
        <h2>Project detail</h2>
      </header>
      <article id="detail" class="card kyc-table-wrap"></article>
    </section>
  </main>
  <footer class="kyc-footer">KeepYourContracts.com · Project status</footer>
  <script>
  async function api(p, opts) {{ const r = await fetch(p, opts || {{}}); return r.json(); }}
  function badge(c) {{ return '<span class="badge ' + c + '">' + c + '</span>'; }}
  async function load() {{
    const l = await api('/api/projects');
    const list = document.getElementById('list');
    if (!l.ok || !l.projects.length) {{ list.innerHTML = '<p class="kyc-empty">No projects yet.</p>'; return; }}
    list.innerHTML = '<ul>' + l.projects.map(p => '<li><a href="#" onclick="show(\\'' + p + '\\');return false;">' + p + '</a></li>').join('') + '</ul>';
  }}
  async function show(pid) {{
    const d = await api('/api/project/' + pid + '/status');
    const s = d.status;
    const det = document.getElementById('detail');
    det.innerHTML = '<p><b>' + pid + '</b> · Phase: ' + s.phase + ' · RAG: ' + badge(s.rag) + ' <span id="ecost" class="badge amber">External costs: checking…</span></p>' +
      '<table><tr><th>Step</th><th>Required</th><th>Status</th><th>Due</th><th>Action</th></tr>' +
      s.steps.map(x => '<tr><td>' + x.title + '</td><td>' + (x.required ? 'Yes' : 'No') + '</td><td>' + x.status + '</td><td>' + (x.due_utc || '') + '</td>' +
        '<td>' + (x.status === 'todo' ? '<button class="btn" type="button" onclick="advance(\\'' + pid + '\\',\\'' + x.id + '\\')">Mark done</button>' : '') + '</td></tr>').join('') +
      '</table><div id="vendors"></motion><div id="rfq"></motion>';
    const c = await api('/api/project/' + pid + '/costs');
    const tag = document.getElementById('ecost');
    if (c.costs && c.costs.requires_external) {{
      tag.className = 'badge red';
      tag.textContent = 'External costs: ' + c.costs.items.map(i => i.title).join(', ');
      const blocks = await Promise.all(c.costs.items.map(async it => {{
        const v = await api('/api/vendors?category=' + it.code);
        if (!v.vendors || !v.vendors.length) return '';
        return '<h4>Vendor suggestions — ' + it.title + '</h4><ul>' + v.vendors.map(x => '<li><a target="_blank" rel="noopener" href="' + x.url + '">' + x.name + '</a></li>').join('') + '</ul>';
      }}));
      document.getElementById('vendors').innerHTML = blocks.join('');
    }} else {{
      tag.className = 'badge green';
      tag.textContent = 'External costs: none';
      document.getElementById('vendors').innerHTML = '';
    }}
    document.getElementById('rfq').innerHTML = '<p><button class="btn" type="button" onclick="launchRFQ(\\'' + pid + '\\')">Launch RFQ</button></p>';
  }}
  async function advance(pid, sid) {{
    await api('/api/project/' + pid + '/advance', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ step_id: sid }}) }});
    show(pid);
  }}
  async function launchRFQ(pid) {{
    const cat = prompt('Category code (e.g., gs1, pentest):', 'gs1');
    if (!cat) return;
    const v = await api('/api/vendors?category=' + encodeURIComponent(cat));
    const invitees = (v.vendors || []).filter(x => x.url).slice(0, 5).map(x => ({{ name: x.name, email: '', url: x.url }}));
    const r = await fetch('/api/rfq/create', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ project_id: pid, category: cat, title: 'RFQ for ' + cat.toUpperCase(), spec: {{}}, invitees }}) }});
    const j = await r.json();
    alert(j.ok ? 'RFQ created: ' + j.rfq_id : 'Error: ' + j.error);
  }}
  load();
  </script>
</body>
</html>
""".replace("<motion", "<" + D).replace("</motion>", "</" + D + ">"),
    encoding="utf-8",
)
print("wrote status.html")

# Fix upload motion tags
p = UI / "upload.html"
t = p.read_text(encoding="utf-8", errors="replace")
t = t.replace("<motion", "<" + D).replace("</motion>", "</" + D + ">")
t = t.replace("Step 2</" + D + "> Intake</motion>", "Step 2</" + D + "> Intake</" + D + ">")
p.write_text(t, encoding="utf-8")
print("fixed upload.html")

# Polish control.html structure
(UI / "control.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KeepYourContracts | Operations Control</title>
{OPS}
</head>
<body class="kyc-page kyc-surface-ops">
{OPS_NAV.replace('<a href="/ui/control.html">', '<a href="/ui/control.html" aria-current="page">')}
  <{D} class="kyc-ops-header">
    <{D}>
      <h1>Operations control panel</h1>
      <p class="kyc-ops-subtitle">Monitoring · project actions · system health</p>
    </{D}>
    <{D} class="kyc-ops-badges"><span class="kyc-pill" id="health">checking</span></{D}>
  </{D}>
  <main class="kyc-main kyc-main--ops">
    <section class="kyc-section" style="padding-top:0;">
      <article id="meta" class="card">
        <span class="kyc-label-overline">Runtime status</span>
        <p><strong>Latest project:</strong> <span id="pid">—</span></p>
        <{D} class="kyc-btn-row" style="margin-top:1rem;">
          <a id="openStatus" class="btn secondary" href="/ui/status.html" target="_blank" rel="noopener">Open status</a>
          <a id="exportBtn" class="btn secondary" href="#" target="_blank" rel="noopener">Export binder</a>
          <button id="demo" class="btn" type="button">Create demo project</button>
        </{D}>
      </article>
    </section>
    <section class="kyc-section">
      <header class="kyc-section-head">
        <span class="kyc-label-overline">Tools</span>
        <h2>Operational actions</h2>
        <p>Quick access to workflow, events, scanning, and onboarding utilities.</p>
      </header>
      <{D} class="grid">
        <article class="card"><h4>Status board</h4><p>Projects and workflow steps.</p><a class="btn" href="/ui/status.html" target="_blank" rel="noopener">Open status</a></article>
        <article class="card"><h4>Order inbox</h4><p>Live queue with new-order alerts.</p><a class="btn" href="/ui/inbox.html" target="_blank" rel="noopener">Open inbox</a></article>
        <article class="card"><h4>Event helper</h4><p>Chain-of-custody event entry.</p><a class="btn" href="/ui/event.html" target="_blank" rel="noopener">Open events</a></article>
        <article class="card"><h4>Scan &amp; log</h4><p>QR/barcode capture for mobile.</p><a class="btn" href="/ui/scan.html" target="_blank" rel="noopener">Open scan</a></article>
        <article class="card"><h4>New client</h4><p>Manual kickoff without webhooks.</p><a class="btn" href="/ui/new_client.html" target="_blank" rel="noopener">New client</a></article>
        <article class="card"><h4>Webhook test</h4><p>Diagnostic kickoff payload.</p><a class="btn" href="/ui/webhook_test.html" target="_blank" rel="noopener">Open verifier</a></article>
        <article class="card"><h4>Public host</h4><p>Tunnel / hostname check.</p>
          <{D} class="kyc-row"><{D} class="kyc-field"><label for="pubHost">Hostname</label><input id="pubHost" placeholder="subdomain.yourdomain.tld"></{D}>
          <button class="btn secondary" id="saveCheck" type="button">Save &amp; check</button></{D}>
          <p><strong>Status:</strong> <span id="pubBadge" class="pill">unknown</span> <small id="pubWhen"></small></p>
        </article>
        <article class="card"><h4>Command center</h4><p>Consolidated health and events.</p><a class="btn" href="/ui/command.html" target="_blank" rel="noopener">Open command</a></article>
      </{D}>
    </section>
    <section class="kyc-section">
      <header class="kyc-section-head"><span class="kyc-label-overline">Registry</span><h2>Recent projects</h2></header>
      <article id="table" class="card kyc-table-wrap"><p class="kyc-loading">Loading…</p></article>
    </section>
  </main>
  <footer class="kyc-footer">KeepYourContracts.com · Operations</footer>
  <script>
  async function api(u, opts) {{ const r = await fetch(u, opts || {{}}); return r.json(); }}
  async function init() {{
    try {{
      const h = await api('/healthz');
      const el = document.getElementById('health');
      el.textContent = h.ok ? 'OK' : 'Check';
      el.className = h.ok ? 'kyc-pill kyc-pill--ok' : 'kyc-pill kyc-pill--warn';
    }} catch {{
      document.getElementById('health').textContent = 'Down';
      document.getElementById('health').className = 'kyc-pill kyc-pill--bad';
    }}
    let projects = [];
    try {{ projects = (await api('/api/projects')).projects || []; }} catch {{}}
    const pid = projects.slice(-1)[0] || '';
    document.getElementById('pid').textContent = pid || '—';
    document.getElementById('exportBtn').href = pid ? '/api/project/' + pid + '/export' : '#';
    const tableEl = document.getElementById('table');
    if (!projects.length) tableEl.innerHTML = '<p class="kyc-empty">No projects yet. Create a demo project to begin.</p>';
    else {{
      const rows = projects.slice(-10).reverse().map(p =>
        '<tr><td>' + p + '</td><td><a href="/ui/status.html" target="_blank" rel="noopener">Open</a></td>' +
        '<td><a href="/api/project/' + p + '/export" target="_blank" rel="noopener">Export</a></td></tr>').join('');
      tableEl.innerHTML = '<table><thead><tr><th>Project</th><th>Status</th><th>Export</th></tr></thead><tbody>' + rows + '</tbody></table>';
    }}
    document.getElementById('demo').onclick = async () => {{
      const body = {{ order_id: 'CP-DEMO-' + Date.now(), email: 'you@keepyourcontracts.com', name: 'Carl', skus: ['CMMC-L1'] }};
      const r = await fetch('/events/payment/test', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
      const j = await r.json();
      alert(j.ok ? 'Demo project created.' : 'Error: ' + (j.detail || j.error || r.status));
      location.reload();
    }};
  }}
  init();
  </script>
</body>
</html>
""".replace("<motion", "<" + D).replace("</motion>", "</" + D + ">"),
    encoding="utf-8",
)
print("wrote control.html")

# Readiness polish: remove duplicate back link, add badge before h1
for rp in (UI / "readiness").glob("*.html"):
    lines = rp.read_text(encoding="utf-8", errors="replace").splitlines()
    seen_back = 0
    out = []
    for line in lines:
        if "back-button kyc-back" in line and "control.html" in line:
            seen_back += 1
            if seen_back > 1:
                continue
        out.append(line)
    raw = "\n".join(out)
    if "Readiness operations" not in raw and "<h1>" in raw:
        raw = raw.replace("<h1>", '<span class="kyc-badge">Readiness operations</span>\n<h1>', 1)
    rp.write_text(raw, encoding="utf-8")
    print("polished readiness", rp.name)

print("task14 quality done")
