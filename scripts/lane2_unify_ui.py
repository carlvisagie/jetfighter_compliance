# Task 12 — unify legacy KYC UI pages
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "ui"
D = "div"
STYLES = (
    '  <link rel="stylesheet" href="/ui/assets/styles/design-system.css">\n'
    '  <link rel="stylesheet" href="/ui/assets/styles/layout.css">\n'
    '  <link rel="stylesheet" href="/ui/assets/styles/components.css">\n'
)
OPS = STYLES + '  <link rel="stylesheet" href="/ui/assets/styles/ops-dashboard.css">\n'
READINESS = STYLES + '  <link rel="stylesheet" href="/ui/assets/styles/readiness-compat.css">\n'

OPS_NAV = f"""  <header class="kyc-topbar">
    <a class="kyc-brand" href="/ui/shop.html">Keep<span>YourContracts</span></a>
    <nav class="kyc-nav kyc-nav--ops" aria-label="Operations">
      <a href="/ui/control.html">Control</a>
      <a href="/ui/command.html">Command</a>
      <a href="/ui/status.html">Status</a>
      <a href="/ui/inbox.html">Inbox</a>
    </nav>
  </header>
"""


def ops_page(title: str, h1: str, main_html: str, script: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
{OPS}</head>
<body class="kyc-page kyc-surface-ops">
{OPS_NAV}
  <{D} class="kyc-ops-header"><{D}><h1>{h1}</h1></{D}></{D}>
  <main class="kyc-main kyc-main--ops">
{main_html}
  </main>
  <footer class="kyc-footer">KeepYourContracts.com · Operations</footer>
{script}
</body>
</html>
"""


# inbox
(UI / "inbox.html").write_text(
    ops_page(
        "KeepYourContracts | Order Inbox",
        "Order inbox",
        f"""    <{D} class="card">
      <span class="kyc-label-overline">Operations queue</span>
      <h2>Projects <span id="count" class="badge">0</span></h2>
      <{D} class="kyc-table-wrap">
        <table class="table" id="tbl">
          <thead><tr><th>Project</th><th>Phase</th><th>RAG</th><th>Required Open</th><th>Overdue</th><th>Actions</th></tr></thead>
          <tbody></tbody>
        </table>
      </{D}>
    </{D}>
    <{D} id="toast" class="toast">NEW ORDER</{D}>""",
        """  <script>
const S = { lastSeen: +localStorage.getItem('lastSeenTs')||0 };
const $ = s=>document.querySelector(s);
function toast(msg){ const t=$('#toast'); t.textContent=msg||'NEW ORDER'; t.style.display='block'; setTimeout(()=>t.style.display='none', 3500); }
function ragCls(r){ return r==='green'?'ragG':(r==='red'?'ragR':'ragA'); }
async function fetchProjects(){ const r=await fetch('/api/projects'); return (await r.json()).projects||[]; }
async function fetchStatus(pid){ const r=await fetch('/api/project/'+pid+'/status'); return (await r.json()).status; }
async function refresh(){
  const projs = await fetchProjects();
  $('#count').textContent = projs.length;
  const body = $('#tbl tbody'); body.innerHTML='';
  let newestTs = S.lastSeen;
  for (const pid of projs.sort()){
    const st = await fetchStatus(pid);
    const ts = Date.now(); if (ts>newestTs) newestTs = ts;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${pid}</td><td>${st.phase}</td><td><span class="badge ${ragCls(st.rag)}">${st.rag}</span></td><td>${st.counts.required_open}</td><td>${st.counts.overdue}</td><td><a class="btn" href="/ui/status.html" target="_blank" rel="noopener">Status</a> <a class="btn secondary" href="/api/project/${pid}/export" target="_blank" rel="noopener">Export</a></td>`;
    body.appendChild(tr);
  }
  const prevList = JSON.parse(localStorage.getItem('prevProjects')||'[]');
  const newOnes = projs.filter(p=>!prevList.includes(p));
  if (newOnes.length){ toast('NEW ORDER: '+newOnes[newOnes.length-1]); try{ new AudioContext().resume(); }catch(_){ } }
  localStorage.setItem('prevProjects', JSON.stringify(projs));
  localStorage.setItem('lastSeenTs', String(newestTs));
}
refresh(); setInterval(refresh, 10000);
  </script>""",
    ),
    encoding="utf-8",
)

# event
(UI / "event.html").write_text(
    ops_page(
        "KeepYourContracts | Chain of Custody Event",
        "Chain-of-custody event",
        f"""    <{D} class="card">
      <span class="kyc-label-overline">Event entry</span>
      <form id="f" class="kyc-form">
        <{D} class="row">
          <{D} class="kyc-field"><label>Project<select name="project_id" id="project_id" required></select></label></{D}>
          <{D} class="kyc-field"><label>Event Type<select name="event_type" id="event_type">
            <option>ATTEST</option><option>COMMISSION</option><option>PACK</option><option>SHIP</option>
            <option>RECEIVE</option><option>INSPECT</option><option>TRANSFORM</option><option>EXCEPTION</option>
            <option>CORRECT</option><option>DISPOSE</option>
          </select></label></{D}>
        </{D}>
        <{D} class="row">
          <{D} class="kyc-field"><label>Quantity<input type="number" name="qty" value="1" min="0" step="1" required></label></{D}>
          <{D} class="kyc-field"><label>Address/Location<input type="text" name="address" placeholder="Warehouse A"></label></{D}>
        </{D}>
        <{D} class="kyc-field"><label>Why / Notes<textarea name="why" rows="3" placeholder="Short note..."></textarea></label></{D}>
        <button type="submit" class="btn">Submit Event</button>
        <span id="msg" class="kyc-status"></span>
      </form>
    </{D}>
    <h2>Recent events</h2>
    <button type="button" class="btn secondary" id="refresh">Refresh</button>
    <{D} class="card kyc-table-wrap" style="margin-top:1rem;">
      <table id="tbl"><thead><tr><th>Time (UTC)</th><th>Project</th><th>Type</th><th>Why</th><th>Qty</th><th>Where</th></tr></thead><tbody></tbody></table>
    </{D}>""",
        """  <script>
async function api(u,opts){ const r=await fetch(u,opts||{}); return r.json() }
async function loadProjects(){
  const r = await api('/api/projects');
  const sel = document.getElementById('project_id');
  sel.innerHTML = (r.projects||[]).map(p=>`<option value="${p}">${p}</option>`).join('');
}
async function submitForm(e){
  e.preventDefault();
  const fd = new FormData(document.getElementById('f'));
  const res = await fetch('/api/coc/event/form',{method:'POST', body:fd});
  const j = await res.json();
  document.getElementById('msg').textContent = j.ok ? 'Saved.' : ('Error: '+(j.detail||j.error||res.status));
  if(j.ok) loadRecent();
}
async function loadRecent(){
  const pid = document.getElementById('project_id').value;
  const r = await api('/api/events/recent?project_id='+encodeURIComponent(pid));
  const tb = document.querySelector('#tbl tbody'); tb.innerHTML='';
  (r.events||[]).forEach(ev=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${ev.when_utc||''}</td><td>${ev.project_id||''}</td><td>${ev.event_type||''}</td><td>${ev.why||''}</td><td>${(ev.what&&ev.what[0]&&ev.what[0].qty)||''}</td><td>${(ev.where&&ev.where.address)||''}</td>`;
    tb.appendChild(tr);
  });
}
document.getElementById('f').addEventListener('submit', submitForm);
document.getElementById('refresh').addEventListener('click', loadRecent);
loadProjects().then(loadRecent);
  </script>""",
    ),
    encoding="utf-8",
)

# scan — preserve all IDs and camera logic from original
scan_body = Path(UI / "scan.html").read_text(encoding="utf-8", errors="replace")
scan_script_start = scan_body.find("<script>")
scan_script = scan_body[scan_script_start:] if scan_script_start >= 0 else ""
(UI / "scan.html").write_text(
    ops_page(
        "KeepYourContracts | Scan & Log",
        "Evidence scan & log",
        f"""    <{D} class="card">
      <p class="kyc-status">Tip: Add this page to your phone home screen for one-tap logging.</p>
      <{D} id="support" class="pill">Detecting camera</{D}>
      <video id="cam" playsinline muted></video>
      <p id="scanValue"><b>Last code:</b> <span id="code"></span></p>
      <form id="f" class="kyc-form">
        <{D} class="row">
          <{D} class="kyc-field"><label>Project<select name="project_id" id="project_id" required></select></label></{D}>
          <{D} class="kyc-field"><label>Event Type<select name="event_type" id="event_type">
            <option>RECEIVE</option><option>SHIP</option><option>INSPECT</option><option>ATTEST</option>
            <option>EXCEPTION</option><option>CORRECT</option><option>COMMISSION</option><option>PACK</option>
            <option>TRANSFORM</option><option>DISPOSE</option>
          </select></label></{D}>
        </{D}>
        <{D} class="row">
          <{D} class="kyc-field"><label>Quantity<input type="number" min="0" step="1" name="qty" id="qty" value="1"></label></{D}>
          <{D} class="kyc-field"><label>Address/Location<input type="text" name="address" id="address" placeholder="Dock 3"></label></{D}>
        </{D}>
        <{D} class="kyc-field"><label>Why / Notes<textarea name="why" id="why" rows="3"></textarea></label></{D}>
        <{D} class="kyc-btn-row">
          <button type="button" class="btn secondary" id="useCode">Use scanned code as note</button>
          <button type="button" class="btn secondary" id="geo">Use my location</button>
          <button type="submit" class="btn" id="submit">Submit Event</button>
        </{D}>
        <{D} id="msg"></{D}>
      </form>
    </{D}>""",
        scan_script,
    ),
    encoding="utf-8",
)

# new_client
(UI / "new_client.html").write_text(
    ops_page(
        "KeepYourContracts | New Client",
        "New client",
        f"""    <{D} class="card">
      <p>Fill fields, choose SKU(s), click <b>Create Project</b>. Intake opens automatically.</p>
      <form id="f" class="kyc-form">
        <{D} class="row">
          <{D} class="kyc-field"><label>Order/Ref ID<input id="ref" required placeholder="ORD-1001"></label></{D}>
          <{D} class="kyc-field"><label>Client Email<input id="email" type="email" required></label></{D}>
        </{D}>
        <{D} class="row">
          <{D} class="kyc-field"><label>Client Name<input id="name" required></label></{D}>
          <{D} class="kyc-field"><label>SKU(s)
            <label><input type="checkbox" id="sku_l1"> CMMC-L1</label>
            <label><input type="checkbox" id="sku_l2"> CMMC-L2</label>
            <label><input type="checkbox" id="sku_dpp"> DPP-ESPR</label>
          </label></{D}>
        </{D}>
        <button type="submit" class="btn">Create Project</button>
        <{D} id="msg" class="kyc-status"></{D}>
      </form>
    </{D}>""",
        """  <script>
const f = document.getElementById('f'); const M = document.getElementById('msg');
const ok=(t)=>{M.textContent=t;M.className='kyc-status kyc-status--ok'}; const bad=(t)=>{M.textContent=t;M.className='kyc-status kyc-status--error'};
f.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const ref = document.getElementById('ref').value.trim();
  const email = document.getElementById('email').value.trim();
  const name = document.getElementById('name').value.trim();
  const skus = [];
  if (document.getElementById('sku_l1').checked) skus.push('CMMC-L1');
  if (document.getElementById('sku_l2').checked) skus.push('CMMC-L2');
  if (document.getElementById('sku_dpp').checked) skus.push('DPP-ESPR');
  if (!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email)) return bad('Invalid email.');
  if (!ref || !name || skus.length===0) return bad('Fill all fields and choose at least one SKU.');
  try{
    const L = await fetch('/api/projects').then(r=>r.json()).catch(()=>({projects:[]}));
    if ((L.projects||[]).some(p=>p.includes(ref))) return bad('Ref ID already used.');
    const res = await fetch('/events/payment/test',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ order_id: ref, email, name, skus })});
    const j = await res.json();
    if (j.ok){ ok('Project created. Opening intake'); if (j.intake_url) window.open(j.intake_url,'_blank'); }
    else bad('Error: '+(j.detail||j.error||res.status));
  }catch(_){ bad('Network error'); }
});
  </script>""",
    ),
    encoding="utf-8",
)

# vendor_quote
(UI / "vendor_quote.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KeepYourContracts | Submit Quote</title>
{STYLES}</head>
<body class="kyc-page">
  <header class="kyc-topbar">
    <a class="kyc-brand" href="/ui/shop.html">Keep<span>YourContracts</span></a>
    <nav class="kyc-nav"><a href="/ui/shop.html">Services</a><a href="/ui/inquiry.html">Contact</a></nav>
  </header>
  <main class="kyc-main kyc-main--narrow">
    <{D} class="kyc-card kyc-card--flat">
      <h1>Submit quote</h1>
      <form id="f" class="kyc-form">
        <input type="hidden" id="token" name="token" />
        <{D} class="kyc-field"><label>Vendor Name<input name="vendor_name" required></label></{D}>
        <{D} class="kyc-field"><label>Email<input name="vendor_email" type="email" required></label></{D}>
        <{D} class="kyc-field"><label>Price (EUR)<input name="price_eur" type="number" min="0" step="0.01" required></label></{D}>
        <{D} class="kyc-field"><label>Delivery (days)<input name="delivery_days" type="number" min="1" step="1" required></label></{D}>
        <{D} class="kyc-check"><label><input type="checkbox" name="accreditation"> Accredited / Authorized</label></{D}>
        <{D} class="kyc-field"><label>Notes<textarea name="notes"></textarea></label></{D}>
        <button type="submit" class="kyc-btn kyc-btn--primary">Submit Quote</button>
      </form>
    </{D}>
  </main>
  <footer class="kyc-footer">KeepYourContracts.com</footer>
  <script>
(async () => {{
  const p = new URLSearchParams(location.search);
  document.getElementById("token").value = p.get("token")||"";
  document.getElementById("f").addEventListener("submit", async (e)=>{{
    e.preventDefault();
    const fd = new FormData(document.getElementById("f"));
    const r = await fetch("/api/rfq/submit", {{method:"POST", body:fd}});
    const j = await r.json();
    alert(j.ok ? "Quote submitted. Thank you!" : "Error: " + j.error);
  }});
}})();
  </script>
</body>
</html>
""",
    encoding="utf-8",
)

# webhook_test
(UI / "webhook_test.html").write_text(
    ops_page(
        "KeepYourContracts | Webhook Test",
        "Webhook test",
        f"""    <{D} class="card">
      <span class="kyc-label-overline">Ops only</span>
      <h2>Test kickoff()</h2>
      <button type="button" class="btn" onclick="send()">Send</button>
      <pre id="out" class="codebox" style="margin-top:1rem;white-space:pre-wrap;"></pre>
    </{D}>""",
        """  <script>
async function send() {
  const payload = {
    id: "test_order_" + Math.random().toString(36).slice(2),
    email: "admin@keepyourcontracts.com",
    name: "Test User",
    line_items: [{ title: "CMMC Level 1 Fast-Track Assessment", sku: "CMMC-L1-FAST" }]
  };
  const res = await fetch("/api/test-webhook", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  document.getElementById("out").textContent = await res.text();
}
  </script>""",
    ),
    encoding="utf-8",
)

# healthz + index
(UI / "healthz.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>System Health</title>
{STYLES}</head>
<body class="kyc-page kyc-surface-ops">
{OPS_NAV}
  <main class="kyc-main kyc-main--narrow">
    <{D} class="card">
      <h1>System health</h1>
      <p>Status: <span id="status" class="kyc-pill">Loading...</span></p>
      <pre id="json" class="codebox" style="white-space:pre-wrap;"></pre>
    </{D}>
  </main>
  <script>
    fetch("/healthz").then(r => r.json()).then(data => {{
      document.getElementById("status").textContent = data.ok ? "OK" : "Error";
      document.getElementById("status").className = data.ok ? "kyc-pill kyc-pill--ok" : "kyc-pill kyc-pill--bad";
      document.getElementById("json").textContent = JSON.stringify(data, null, 2);
    }}).catch(e => {{
      document.getElementById("status").textContent = "API Error";
      document.getElementById("json").textContent = e.toString();
    }});
  </script>
</body>
</html>
""",
    encoding="utf-8",
)

(UI / "index.html").write_text(
    f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>KeepYourContracts UI</title>
{STYLES}</head>
<body class="kyc-page">
  <header class="kyc-topbar">
    <a class="kyc-brand" href="/ui/shop.html">Keep<span>YourContracts</span></a>
  </header>
  <main class="kyc-main kyc-main--narrow">
    <{D} class="kyc-card kyc-card--flat" style="text-align:center;">
      <h1>UI route active</h1>
      <p>The <code>/ui</code> static mount is serving files correctly.</p>
      <a class="kyc-btn kyc-btn--primary" href="/ui/shop.html">Open services</a>
    </{D}>
  </main>
</body>
</html>
""",
    encoding="utf-8",
)

# readiness pages
READINESS_NAV = f"""<nav class="kyc-readiness-nav" aria-label="Readiness sections">
  <a href="index.html">Master</a>
  <a href="script.html">Script</a>
  <a href="questions.html">Questions</a>
  <a href="scoring.html">Scoring</a>
  <a href="report.html">Report</a>
  <a href="outreach.html">Outreach</a>
  <a href="pre-call.html">Pre-call</a>
  <a href="follow-up.html">Follow-up</a>
</nav>
"""

for rp in (UI / "readiness").glob("*.html"):
    raw = rp.read_text(encoding="utf-8", errors="replace")
    if "design-system.css" in raw:
        continue
    s = raw.find("<style>")
    e = raw.find("</style>") + len("</style>") if s >= 0 else 0
    head_end = raw.find("</head>")
    if s >= 0:
        new_head = raw[:s] + READINESS + raw[e:head_end]
    else:
        new_head = raw[:head_end]
    body = raw[raw.find("<body>") + len("<body>") : raw.find("</body>")]
    body = body.replace('class="back-button"', 'class="back-button kyc-back"')
    title_match = raw.find("<title>")
    title_end = raw.find("</title>")
    title = raw[title_match + 7 : title_end] if title_match >= 0 else rp.stem
    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
{READINESS}
</head>
<body class="kyc-page kyc-readiness">
{OPS_NAV}
<main class="kyc-main">
<a href="../control.html" class="back-button kyc-back">← Control panel</a>
{READINESS_NAV}
{body.strip()}
</main>
<footer class="kyc-footer">KeepYourContracts.com · Readiness ops</footer>
</body>
</html>
"""
    rp.write_text(out, encoding="utf-8")
    print("readiness", rp.name)

print("lane2 unified pages written")
