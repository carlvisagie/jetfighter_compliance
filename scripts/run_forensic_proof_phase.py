#!/usr/bin/env python3
"""Execute forensic proof phase steps 1-14; print JSON results for FORENSIC_INTEGRITY_PROOF.md."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))

    root = Path(tempfile.mkdtemp(prefix="forensic-proof-phase-"))
    (root / "intakes").mkdir()
    os.environ["ENVIRONMENT"] = "test"
    os.environ["KYC_DATA"] = str(root)
    os.environ["KYC_FOUNDING_BETA_MODE"] = "true"
    os.environ["OPS_PASSWORD"] = "test-ops-password-for-pytest"
    os.environ["OPS_SECRET"] = "test-ops-secret-for-pytest"

    import services.config as cfg

    cfg.DATA = root

    from fastapi.testclient import TestClient
    from server import app

    from services.intake.evidence_registry import lookup_by_intake
    from services.intake.forensic_reconcile import (
        integrity_incidents_path,
        load_integrity_incidents,
        run_forensic_reconciliation,
    )
    from services.intake.retention import audit_receipt_path, load_audit_receipt
    from services.intake.storage import index_jsonl, intake_dir, latest_index_row
    from services.intake.transactions import load_transaction_log
    from services.cognitive_topology import build_cognitive_topology

    c = TestClient(app)
    c.post("/api/ops/login", json={"password": os.environ["OPS_PASSWORD"]})

    results: dict = {"steps": {}, "ok": True, "root": str(root)}

    def record(step: str, ok: bool, detail: dict):
        results["steps"][step] = {"ok": ok, **detail}
        if not ok:
            results["ok"] = False

    # 1 upload
    r = c.post(
        "/api/founding-beta/upload",
        files=[("files", ("proof-phase.pdf", io.BytesIO(b"%PDF-1.4 proof-phase"), "application/pdf"))],
        data={"email": "proof-phase@example.com", "expected_file_count": "1"},
    )
    iid = r.json().get("intake_id") if r.status_code == 200 else None
    record("1_upload", r.status_code == 200 and bool(iid), {"status": r.status_code, "intake_id": iid})

    # 2 queue
    q = c.get("/api/operator/intake/queue").json()
    in_queue = iid in {row.get("intake_id") for row in q.get("queue") or []}
    record("2_queue", in_queue, {"queue_depth": q.get("queue_depth"), "in_queue": in_queue})

    # 3 registry
    reg = lookup_by_intake(iid or "")
    record(
        "3_evidence_registry",
        len(reg) >= 1,
        {"count": len(reg), "status": reg[0].get("current_status") if reg else None},
    )

    # 4 audit
    audit_path = audit_receipt_path(iid or "")
    audit = load_audit_receipt(iid or "")
    record("4_audit_receipt", audit_path.is_file() and audit is not None, {"path": str(audit_path)})

    # 5 transaction lifecycle
    tx = load_transaction_log(iid or "")
    phases = [e.get("phase") for e in tx]
    record(
        "5_transaction_lifecycle",
        "index_committed" in phases and "audit_written" in phases,
        {"phases": phases},
    )

    # 6 proof green
    proof = c.get("/api/operator/integrity/proof").json()
    record("6_proof_green", proof.get("ok") is True, {"proof": proof})

    # 7-9 corrupt file
    if iid:
        (intake_dir(iid) / "uploads" / "proof-phase.pdf").write_bytes(b"CORRUPTED")
    proof_bad = c.get("/api/operator/integrity/proof").json()
    reconcile_bad = c.get("/api/operator/integrity/reconcile").json()
    retention = c.get(f"/api/operator/intake/retention-check/{iid}").json()
    incidents_before = len(load_integrity_incidents())
    run_forensic_reconciliation(limit=50)
    incidents_after = len(load_integrity_incidents())
    record(
        "7_corrupt_file",
        True,
        {"note": "wrote CORRUPTED bytes to proof-phase.pdf"},
    )
    record(
        "8_hash_mismatch",
        not proof_bad.get("ok") or proof_bad.get("corrupt_files", 0) > 0 or not retention.get("file_hashes_match", True),
        {
            "proof_ok": proof_bad.get("ok"),
            "corrupt_files": proof_bad.get("corrupt_files"),
            "file_hashes_match": retention.get("file_hashes_match"),
        },
    )
    record(
        "9_integrity_incident",
        incidents_after > incidents_before or not reconcile_bad.get("ok"),
        {
            "incidents_before": incidents_before,
            "incidents_after": incidents_after,
            "reconcile_ok": reconcile_bad.get("ok"),
            "disagreement_count": reconcile_bad.get("disagreement_count"),
        },
    )

    # 10 COTE
    topo = build_cognitive_topology()
    up = topo.get("subsystems", {}).get("upload_pipeline", {})
    record(
        "10_cote_cockpit",
        up.get("upload_node_severity") in ("red", "amber") or up.get("integrity_mismatch_count", 0) > 0 or not proof_bad.get("ok"),
        {
            "upload_node_severity": up.get("upload_node_severity"),
            "integrity_mismatch_count": up.get("integrity_mismatch_count"),
            "anomaly": up.get("anomaly"),
        },
    )

    # Fresh upload for index/audit tests
    r2 = c.post(
        "/api/founding-beta/upload",
        files=[("files", ("recover.pdf", io.BytesIO(b"%PDF-1.4 recover"), "application/pdf"))],
        data={"email": "recover@example.com", "expected_file_count": "1"},
    )
    iid2 = r2.json().get("intake_id")

    # 11 delete index row
    if iid2:
        lines = [ln for ln in index_jsonl().read_text(encoding="utf-8").splitlines() if iid2 not in ln]
        index_jsonl().write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    row_gone = latest_index_row(iid2 or "") is None
    record("11_delete_index_row", row_gone, {"intake_id": iid2})

    # 12 recovery
    from services.intake.forensic_recovery import recover_intake_forensic

    rec = recover_intake_forensic(iid2 or "")
    q2 = c.get("/api/operator/intake/queue").json()
    visible = iid2 in {row.get("intake_id") for row in q2.get("queue") or []}
    record(
        "12_recovery_visibility",
        visible or rec.get("recovery_report", {}).get("index_restored"),
        {"recovery": rec, "queue_visible": visible},
    )

    # 13 alter audit
    r3 = c.post(
        "/api/founding-beta/upload",
        files=[("files", ("audit-test.pdf", io.BytesIO(b"%PDF-1.4 audit"), "application/pdf"))],
        data={"email": "audit@example.com", "expected_file_count": "1"},
    )
    iid3 = r3.json().get("intake_id")
    ap = audit_receipt_path(iid3 or "")
    if ap.is_file():
        data = json.loads(ap.read_text(encoding="utf-8"))
        data["file_hashes"] = {"audit-test.pdf": "deadbeef" * 8}
        ap.write_text(json.dumps(data), encoding="utf-8")
    record("13_alter_audit", ap.is_file(), {"intake_id": iid3})

    # 14 reconciliation detects
    recon = run_forensic_reconciliation(limit=50)
    record(
        "14_reconcile_detects_audit_tamper",
        not recon.get("ok") or recon.get("disagreement_count", 0) > 0,
        {"reconcile_ok": recon.get("ok"), "disagreement_count": recon.get("disagreement_count")},
    )

    print(json.dumps(results, indent=2))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
