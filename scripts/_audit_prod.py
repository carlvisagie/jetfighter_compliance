"""
KYC SEV-1 Production Data Audit
Queries every available API endpoint for counts, records, and file listings.
"""
import httpx, json, sys
from datetime import datetime
from pathlib import Path

# Production-Is-The-Only-Truth contract: no --target / --env / --local allowed.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _prod_only import reject_target_flag  # noqa: E402
reject_target_flag()

BASE = "https://jetfighter-compliance.onrender.com"
PWD  = "IZAKviss!@34"

def login():
    r = httpx.post(f"{BASE}/api/ops/login", json={"password": PWD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code}"
    return dict(r.cookies)

def get(cookies, path, params=None):
    r = httpx.get(f"{BASE}{path}", cookies=cookies, params=params or {}, timeout=30)
    return r.status_code, r.json() if r.status_code == 200 else {"_error": r.text[:300]}

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def pp(label, value):
    print(f"  {label}: {value}")

# ─────────────────────────────────────────────────────────────
cookies = login()
print(f"  [OK] Authenticated  ({datetime.utcnow().isoformat()}Z)")

# ── INTAKE ENGINE ─────────────────────────────────────────────
section("INTAKE ENGINE")
code, diag = get(cookies, "/api/operator/intake/diagnostics")
d = diag.get("diagnostics", {})
pp("data_root",                d.get("data_root"))
pp("intake_directories_found", d.get("intake_directories_found"))
pp("upload_files_on_disk",     d.get("upload_files_on_disk"))
pp("index_exists",             d.get("index_exists"))
pp("pending_review_count",     d.get("pending_review_count"))
pp("durable_storage_configured", d.get("durable_storage_configured"))

code, q = get(cookies, "/api/operator/intake/queue", {"limit": 20, "include_archived": "true"})
queue = q.get("queue") or []
pp("queue_depth (pending)",    q.get("queue_depth"))
pp("queue_rows_generated",     q.get("queue_rows_generated"))
pp("queue_empty_reason",       q.get("queue_empty_reason"))
pp("Total intakes returned",   len(queue))

print()
print("  Last 20 intakes (from queue):")
if not queue:
    print("    (none)")
for row in queue[:20]:
    pid  = row.get("project_id") or ""
    fc   = row.get("file_count", 0)
    rs   = row.get("review_status", "?")
    co   = row.get("company", "(unnamed)")[:35]
    iid  = row.get("intake_id", "?")
    print(f"    {iid}  company={co:35}  files={fc}  status={rs}  project={pid or '(none)'}")

# ── DISK SCAN ─────────────────────────────────────────────────
section("RAW DISK SCAN")
code, scan = get(cookies, "/api/operator/intake/raw-disk-scan")
if code == 200:
    inv = (scan.get("inventory") or scan)
    pp("intake_directories",  inv.get("intake_directories"))
    pp("intake_json_files",   inv.get("intake_json_files"))
    pp("upload_files",        inv.get("upload_files"))
    pp("index_tail_unique_ids", inv.get("index_tail_unique_ids"))
    ids = inv.get("intake_ids_sample") or []
    print(f"  intake_ids_sample: {ids}")
else:
    print(f"  raw-disk-scan returned {code}")

# ── MEMORY / PROJECTS ─────────────────────────────────────────
section("MEMORY / PROJECTS")
code, mem = get(cookies, "/api/operator/memory")
if code == 200:
    pp("entity_count",   (mem.get("stats") or {}).get("entity_count"))
    pp("timeline_count", (mem.get("stats") or {}).get("timeline_count"))
    pp("signal_count",   (mem.get("stats") or {}).get("signal_count"))
else:
    print(f"  /api/operator/memory -> {code}")

# Try cognitive topology for project count
code, ct = get(cookies, "/api/cognitive-topology")
if code == 200:
    nodes = ct.get("nodes") or []
    proj_nodes = [n for n in nodes if "project" in str(n.get("type","")).lower()]
    pp("cognitive_topology nodes", len(nodes))
    pp("project-type nodes",       len(proj_nodes))

# ── VIO OVERVIEW ─────────────────────────────────────────────
section("VIO OVERVIEW")
code, vio = get(cookies, "/api/operator/vio/overview")
companies = vio.get("companies") or []
pp("companies_visible", len(companies))
pp("health_score",      (vio.get("organism_health") or {}).get("score"))
pp("state_breakdown",   (vio.get("organism_health") or {}).get("state_counts"))
for c in companies[:20]:
    print(f"    state={c.get('state','?'):18} company={c.get('company_name','?')[:40]}")

# ── EVIDENCE ─────────────────────────────────────────────────
section("EVIDENCE INTELLIGENCE")
# There is no global EI listing — per project only
code, status = get(cookies, "/api/operator/status")
if code == 200:
    pp("system_status", (status.get("status") or status.get("organism_status") or "?"))

# ── CONTROL / COCKPIT ─────────────────────────────────────────
section("OPERATOR COCKPIT SUMMARY")
code, ck = get(cookies, "/api/operator/control-room")
if code != 200:
    code, ck = get(cookies, "/api/operator/cockpit")
if code == 200:
    pp("cockpit_ok", ck.get("ok"))
    stats = ck.get("stats") or ck.get("summary") or {}
    for k, v in stats.items():
        pp(k, v)
else:
    print(f"  cockpit -> {code}")

# ── ACQUISITION ───────────────────────────────────────────────
section("ACQUISITION ENGINE")
code, acq = get(cookies, "/api/operator/acquisition/status")
if code == 200:
    pp("leads_total",    (acq.get("stats") or {}).get("total_leads"))
    pp("leads_pending",  (acq.get("stats") or {}).get("pending_approval"))
    pp("leads_approved", (acq.get("stats") or {}).get("approved"))

# ── PAYMENT ───────────────────────────────────────────────────
section("PAYMENT ENGINE")
code, pay = get(cookies, "/api/operator/payment-products")
if code == 200:
    prods = pay.get("products") or []
    pp("payment_products_configured", len(prods))
    for p in prods[:5]:
        pp(f"  product", f"{p.get('name','?')} | {p.get('price_formatted','?')} | id={p.get('product_id','?')}")

# ── HEALTHZ ───────────────────────────────────────────────────
section("HEALTHZ")
code, hz = get(cookies, "/healthz")
pp("health", hz.get("status") or hz.get("ok"))
subsystems = hz.get("subsystems") or hz.get("checks") or {}
for k, v in subsystems.items():
    pp(f"  {k}", v)

print(f"\n{'='*60}")
print("  AUDIT COMPLETE")
print(f"{'='*60}\n")
