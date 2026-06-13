import json, hashlib, io, zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .defensive_wiring import safe_write_text
from typing import List, Dict
from .config import DATA, SETTINGS
from .emails import send_email

def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def _project_dir(pid: str) -> Path:
    return DATA / "projects" / pid

def list_projects() -> List[str]:
    p = DATA / "projects"
    if not p.exists(): return []
    return sorted([d.name for d in p.iterdir() if d.is_dir() and d.name.startswith("P-")])

def project_changed_within(pid: str, hours: int) -> bool:
    p = _project_dir(pid)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    latest = max((f.stat().st_mtime for f in p.rglob("*") if f.is_file()), default=0)
    return datetime.fromtimestamp(latest, tz=timezone.utc) >= cutoff

def export_binder(pid: str) -> Path:
    used_entity_context = False
    try:
        from services.memory.central_memory import find_entity_id

        used_entity_context = bool(find_entity_id(project_id=pid))
    except Exception:
        pass
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "reports",
            "report_generated",
            project_id=pid,
            metadata={"binder": True, "used_entity_context": used_entity_context},
        )
    except Exception:
        pass
    pdir = _project_dir(pid)
    if not pdir.exists():
        try:
            from services.memory.telemetry import emit_telemetry

            emit_telemetry(
                "reports",
                "export_failed",
                severity="error",
                success=False,
                project_id=pid,
                message="Project directory missing",
            )
        except Exception:
            pass
        raise FileNotFoundError(f"Project not found: {pid}")
    if not used_entity_context:
        try:
            from services.memory.telemetry import emit_telemetry

            emit_telemetry(
                "reports",
                "binder_missing_context",
                severity="warning",
                success=True,
                project_id=pid,
                message="Binder generated without central entity context",
            )
        except Exception:
            pass
    expdir = pdir / "exports"; expdir.mkdir(parents=True, exist_ok=True)
    files: List[Path] = []
    for rel in ["meta.json","checklist.json"]:
        f = pdir / rel
        if f.exists(): files.append(f)
    for sub in ["communications","evidence"]:
        d = pdir / sub
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file(): files.append(f)

    manifest = [{"path": f.relative_to(pdir).as_posix(), "sha256": _sha256_file(f)} for f in files]
    leaves = [bytes.fromhex(m["sha256"]) for m in sorted(manifest, key=lambda x: x["path"])]
    if leaves:
        nodes = leaves[:]
        while len(nodes) > 1:
            nxt = []
            for i in range(0,len(nodes),2):
                a = nodes[i]; b = nodes[i+1] if i+1 < len(nodes) else nodes[i]
                nxt.append(hashlib.sha256(a+b).digest())
            nodes = nxt
        merkle = nodes[0].hex()
    else:
        merkle = hashlib.sha256(b"EMPTY").hexdigest()

    zname = f"{pid}_binder_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    zpath = expdir / zname
    with zipfile.ZipFile(str(zpath), "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, arcname=f.relative_to(pdir).as_posix())
        z.writestr("manifest.json", json.dumps({
            "project_id": pid, "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": manifest, "merkle_root_sha256": merkle
        }, indent=2))
    # retention
    keep = max(1, SETTINGS.export_keep_latest)
    old = sorted(expdir.glob(f"{pid}_binder_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)[keep:]
    for f in old:
        try: f.unlink()
        except Exception: pass
    try:
        from services.memory.telemetry import emit_telemetry

        emit_telemetry(
            "reports",
            "binder_generated",
            project_id=pid,
            artifact_id=zpath.name,
            success=True,
            metadata={"used_entity_context": used_entity_context, "file_count": len(files)},
        )
    except Exception:
        pass

    # Custody capture: binder export is the *delivery* moment — the
    # operator handed the customer a sealed artifact. Merkle root + file
    # count + zip name go into the chain of custody so the binder can
    # be reconstructed and proven years later. The transaction ledger
    # is keyed on intake_id (FB-...), so resolve the owning intake when
    # the export is for a legacy P-... project. Best-effort write.
    try:
        from services.intake.transactions import append_transaction_event

        intake_id = _resolve_intake_for_project(pid)
        if intake_id:
            append_transaction_event(
                intake_id,
                "binder_exported",
                metadata={
                    "project_id":         pid,
                    "binder_zip":         zpath.name,
                    "file_count":         len(files),
                    "merkle_root_sha256": merkle,
                    "generated_utc":      datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
    except Exception:
        pass

    return zpath


def _resolve_intake_for_project(pid: str) -> str:
    """Find the intake_id this project belongs to.

    * Intake-as-project case (our new pipeline writes intake_id as the
      project key): `pid` already starts with `FB-` → use directly.
    * Legacy kickoff case: `pid` is `P-…` and the link lives in the
      project `meta.json` under `canonical_intake_id`.
    """
    if pid.startswith("FB-"):
        return pid
    try:
        meta = _project_dir(pid) / "meta.json"
        if meta.is_file():
            data = json.loads(meta.read_text(encoding="utf-8"))
            iid = str(data.get("canonical_intake_id") or "").strip()
            if iid.startswith("FB-"):
                return iid
    except Exception:
        return ""
    return ""

def build_digest_html(rows: List[Dict]) -> str:
    head = "<h2>Weekly Compliance Digest</h2>"
    tbl = "<table border='1' cellpadding='6' cellspacing='0'><tr><th>Project</th><th>Phase</th><th>RAG</th><th>Req Open</th><th>Overdue</th></tr>"
    for r in rows:
        tbl += f"<tr><td>{r['pid']}</td><td>{r['phase']}</td><td>{r['rag']}</td><td>{r['req_open']}</td><td>{r['overdue']}</td></tr>"
    tbl += "</table>"
    return head + tbl

def send_digest(rows: List[Dict]):
    html = build_digest_html(rows)
    if SETTINGS.smtp_enabled and SETTINGS.digest_email_to:
        send_email(SETTINGS.digest_email_to, "Weekly Compliance Digest", html)
    else:
        repdir = DATA / "reports"; repdir.mkdir(parents=True, exist_ok=True)
        (repdir / f"digest_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.html").write_text(html, encoding="utf-8")
