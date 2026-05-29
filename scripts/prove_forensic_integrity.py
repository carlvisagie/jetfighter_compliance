#!/usr/bin/env python3
"""Adversarial proof of forensic evidence integrity engine. Exit 1 on any failure."""
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

    root = Path(tempfile.mkdtemp(prefix="forensic-proof-"))
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
    from services.intake.storage import intake_dir

    c = TestClient(app)
    assert c.post("/api/ops/login", json={"password": os.environ["OPS_PASSWORD"]}).status_code == 200

    def pdf(name: str):
        return ("files", (name, io.BytesIO(b"%PDF-1.4 forensic-proof"), "application/pdf"))

    errors: list[str] = []

    # 1) Upload registers evidence
    r = c.post(
        "/api/founding-beta/upload",
        files=[pdf("proof.pdf")],
        data={"email": "proof@example.com", "expected_file_count": "1"},
    )
    if r.status_code != 200:
        errors.append(f"upload failed: {r.status_code} {r.text}")
    else:
        iid = r.json()["intake_id"]
        rows = lookup_by_intake(iid)
        if not rows:
            errors.append("evidence registry empty after upload")
        elif rows[0].get("current_status") != "verified":
            errors.append(f"registry status={rows[0].get('current_status')} expected verified")

    # 2) Proof ok on clean fleet
    proof = c.get("/api/operator/integrity/proof").json()
    if not proof.get("ok"):
        errors.append(f"proof not ok on clean upload: {proof}")
    if proof.get("verified_files", 0) < 1:
        errors.append("proof verified_files < 1 after upload")

    # 3) Corruption detected
    if r.status_code == 200:
        iid = r.json()["intake_id"]
        (intake_dir(iid) / "uploads" / "proof.pdf").write_bytes(b"CORRUPTED")
        proof_bad = c.get("/api/operator/integrity/proof").json()
        if proof_bad.get("ok"):
            errors.append("proof still ok after disk corruption")
        reconcile = c.get("/api/operator/integrity/reconcile").json()
        if reconcile.get("ok"):
            errors.append("reconcile ok after corruption")

    # 4) Timeline has custody events
    if r.status_code == 200:
        iid = r.json()["intake_id"]
        tl = c.get(f"/api/operator/integrity/timeline/{iid}").json()
        events = {e.get("event") for e in tl.get("events") or []}
        if not events:
            errors.append("timeline empty")
        elif not ({"hash_verified", "audit_written"} & events or "upload_received" in events):
            errors.append(f"timeline missing expected events: {events}")

    # 5) Partial upload — no fake success
    r = c.post(
        "/api/founding-beta/upload",
        files=[pdf(f"p{i}.pdf") for i in range(3)],
        data={
            "email": "partial@example.com",
            "expected_file_count": "5",
            "expected_file_names": json.dumps([f"p{i}.pdf" for i in range(5)]),
        },
    )
    if r.status_code != 200:
        errors.append(f"partial upload failed: {r.text}")
    elif r.json().get("customer_may_show_success"):
        errors.append("partial upload must not show customer success")

    # 6) Ops auth on proof
    c2 = TestClient(app)
    if c2.get("/api/operator/integrity/proof").status_code not in (401, 403, 302):
        errors.append("unauthenticated proof must be blocked")

    if errors:
        print("FORENSIC PROOF FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("FORENSIC PROOF PASSED: registry, proof, corruption, timeline, partial, ops auth")
    return 0


if __name__ == "__main__":
    sys.exit(main())
