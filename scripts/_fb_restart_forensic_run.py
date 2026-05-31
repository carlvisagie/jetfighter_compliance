import json, os, sys, time, hashlib
from pathlib import Path
from datetime import datetime, timezone

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

ops_env = _REPO / ".ops_env"
if ops_env.is_file():
    for line in ops_env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and not os.environ.get(k, "").strip():
            os.environ[k] = v

from scripts.lib.ops_client import authenticate_production, OpsAuthError
from scripts.verify_restart_durability import _restart_render

INTAKE = "FB-9b02b8f7f031"
FN = "immutability-proof.pdf"
CANONICAL = f"/var/data/intakes/{INTAKE}/uploads/{FN}"

out = {
    "intake_id": INTAKE,
    "filename": FN,
    "expected_canonical_path_production": CANONICAL,
    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "render_api_key_present": bool(os.environ.get("RENDER_API_KEY", "").strip()),
}

try:
    client, headers, diag = authenticate_production()
    out["auth"] = {"ok": True, "build_commit": diag.build_info.get("git_commit")}
except OpsAuthError as e:
    out["auth"] = {"ok": False, "reason": e.reason}
    Path(_REPO / "fb-9b02b8f7f031_restart_forensic.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    sys.exit(1)


def get(path, **kw):
    r = client.get(path, headers=headers, **kw)
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:2000]}
    return r.status_code, body


def summarize_from_retention(ret_body):
    audit = ret_body.get("audit_receipt") or {}
    files_on_disk = ret_body.get("files_on_disk") or {}
    summary = {
        "write_root": ret_body.get("write_root"),
        "intake_dir_exists": ret_body.get("intake_dir_exists"),
        "upload_files_found": ret_body.get("upload_files_found"),
        "ghost_intake": ret_body.get("ghost_intake"),
        "ok": ret_body.get("ok"),
        "file_hashes_match": ret_body.get("file_hashes_match"),
        "files_on_disk": files_on_disk,
        "audit_intake_dir": audit.get("intake_dir"),
        "audit_data_root": audit.get("data_root"),
        "files_written": audit.get("files_written"),
        "file_hashes_from_receipt": audit.get("file_hashes"),
    }
    wr = ret_body.get("write_root") or "/var/data"
    summary["path"] = str(Path(wr) / "intakes" / INTAKE / "uploads" / FN)
    on_disk_hash = files_on_disk.get(FN)
    summary["sha256"] = on_disk_hash
    summary["filesystem_existence_check"] = bool(ret_body.get("upload_files_found") and on_disk_hash)
    for fw in audit.get("files_written") or []:
        if fw.get("name") == FN:
            summary["size"] = fw.get("size")
            summary["sha256_from_receipt"] = fw.get("sha256")
            summary["upload_destination_from_receipt"] = str(Path(audit.get("intake_dir", "")) / "uploads" / FN)
    return summary


paths = [
    f"/api/operator/intake/retention-check/{INTAKE}",
    "/api/operator/intake/diagnostics",
    f"/api/operator/intake/reconcile/{INTAKE}",
    f"/api/operator/intake/{INTAKE}/files",
    f"/api/operator/intake/{INTAKE}/audit",
    f"/api/operator/integrity/timeline/{INTAKE}",
]

pre = {}
for p in paths:
    st, body = get(p)
    pre[p] = {"status": st, "body": body}

st, body = get("/api/operator/intake/raw-disk-scan", params={"intake_id": INTAKE, "limit": 50})
pre["/api/operator/intake/raw-disk-scan"] = {"status": st, "body": body}

st, body = get(f"/api/operator/intake/{INTAKE}/files/{FN}/download")
pre["download"] = {
    "status": st,
    "bytes": len(body) if st == 200 else 0,
    "sha256": hashlib.sha256(body).hexdigest() if st == 200 else None,
}

r = client.get(f"/api/operator/intake/{INTAKE}/files/{FN}/view", headers=headers)
content = r.content
pre["view"] = {
    "status": r.status_code,
    "bytes": len(content),
    "content_type": r.headers.get("content-type"),
    "sha256": hashlib.sha256(content).hexdigest() if r.status_code == 200 else None,
}

ret = pre[f"/api/operator/intake/retention-check/{INTAKE}"]["body"]
pre_summary = summarize_from_retention(ret)
out["before_restart"] = {"queries": pre, "summary": pre_summary}

out["restart"] = _restart_render()

if out["restart"].get("ok"):
    for i in range(40):
        time.sleep(10)
        try:
            h = client.get("/health/ready")
            if h.status_code == 200 and h.json().get("ok"):
                out["health_ready_after_s"] = (i + 1) * 10
                break
        except Exception as ex:
            out.setdefault("health_errors", []).append(str(ex))

post = {}
for p in paths:
    st, body = get(p)
    post[p] = {"status": st, "body": body}

st, body = get("/api/operator/intake/raw-disk-scan", params={"intake_id": INTAKE, "limit": 50})
post["/api/operator/intake/raw-disk-scan"] = {"status": st, "body": body}

st, body = get(f"/api/operator/intake/{INTAKE}/files/{FN}/download")
post["download"] = {
    "status": st,
    "bytes": len(body) if st == 200 else 0,
    "sha256": hashlib.sha256(body).hexdigest() if st == 200 else None,
}

r = client.get(f"/api/operator/intake/{INTAKE}/files/{FN}/view", headers=headers)
content = r.content
post["view"] = {
    "status": r.status_code,
    "bytes": len(content),
    "content_type": r.headers.get("content-type"),
    "sha256": hashlib.sha256(content).hexdigest() if r.status_code == 200 else None,
}

ret2 = post[f"/api/operator/intake/retention-check/{INTAKE}"]["body"]
post_summary = summarize_from_retention(ret2)
out["after_restart"] = {"queries": post, "summary": post_summary}

out["comparison"] = {
    "sha256_unchanged": pre_summary.get("sha256") == post_summary.get("sha256"),
    "size_unchanged": pre_summary.get("size") == post_summary.get("size"),
    "existence_before": pre_summary.get("filesystem_existence_check"),
    "existence_after": post_summary.get("filesystem_existence_check"),
    "download_status_before": pre["download"]["status"],
    "download_status_after": post["download"]["status"],
    "survived_restart": bool(
        pre_summary.get("filesystem_existence_check")
        and post_summary.get("filesystem_existence_check")
        and pre_summary.get("sha256") == post_summary.get("sha256")
        and post["download"].get("status") == 200
    ),
}
out["verdict"] = "SURVIVED" if out["comparison"]["survived_restart"] else "NOT_PROVEN_OR_LOST"

client.close()
Path(_REPO / "fb-9b02b8f7f031_restart_forensic.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps({"verdict": out["verdict"], "restart": out["restart"], "comparison": out["comparison"], "pre": pre_summary, "post": post_summary}, indent=2))

