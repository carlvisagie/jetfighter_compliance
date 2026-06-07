#!/usr/bin/env python3
"""Adversarial inline proof of founding-pilot intake invariants. Exit 1 on any failure."""
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

    root = Path(tempfile.mkdtemp(prefix="fb-proof-"))
    (root / "intakes").mkdir()
    os.environ["ENVIRONMENT"] = "test"
    os.environ["KYC_DATA"] = str(root)
    os.environ["KYC_FOUNDING_PILOT_MODE"] = "true"
    os.environ["OPS_PASSWORD"] = "test-ops-password-for-pytest"
    os.environ["OPS_SECRET"] = "test-ops-secret-for-pytest"

    import services.config as cfg

    cfg.DATA = root

    from fastapi.testclient import TestClient
    from server import app

    from services.founding_pilot.retention import audit_receipt_path
    from services.founding_pilot.storage import canonical_intake_dir
    from services.founding_pilot.transactions import load_transaction_log

    c = TestClient(app)
    assert c.post("/api/ops/login", json={"password": os.environ["OPS_PASSWORD"]}).status_code == 200

    def pdf(name: str):
        return ("files", (name, io.BytesIO(b"%PDF-1.4 proof"), "application/pdf"))

    errors: list[str] = []

    # 1) Upload batch commit order: audit before index (per batch, not empty-intake bootstrap)
    r = c.post(
        "/api/founding-pilot/upload",
        files=[pdf("proof.pdf")],
        data={"email": "proof@example.com", "expected_file_count": "1"},
    )
    if r.status_code != 200:
        errors.append(f"single upload failed: {r.status_code} {r.text}")
    else:
        iid = r.json()["intake_id"]
        phases = [e["phase"] for e in load_transaction_log(iid)]
        upload_idx = max(i for i, p in enumerate(phases) if p == "upload_received")
        batch = phases[upload_idx:]
        if "audit_written" not in batch or "index_committed" not in batch:
            errors.append(f"missing audit/index in batch phases: {batch}")
        elif batch.index("audit_written") >= batch.index("index_committed"):
            errors.append(f"audit not before index in batch: {batch}")
        if not audit_receipt_path(iid).is_file():
            errors.append("audit receipt missing after upload")

    # 2) Multi-batch 30 files
    names = [f"p{i}.pdf" for i in range(30)]
    r1 = c.post(
        "/api/founding-pilot/upload",
        files=[pdf(n) for n in names[:15]],
        data={
            "email": "multi@example.com",
            "expected_file_count": "30",
            "expected_file_names": json.dumps(names),
            "upload_manifest": json.dumps({"client_selected_count": 30, "batch_complete": False}),
        },
    )
    if r1.status_code != 200:
        errors.append(f"batch1 failed: {r1.text}")
    else:
        b1 = r1.json()
        if b1.get("verified_file_count") != 15:
            errors.append(f"batch1 verified={b1.get('verified_file_count')} expected 15")
        if b1.get("customer_may_show_success"):
            errors.append("batch1 must not show customer success")
        r2 = c.post(
            "/api/founding-pilot/upload",
            files=[pdf(n) for n in names[15:]],
            data={
                "intake_id": b1["intake_id"],
                "token": b1["token"],
                "expected_file_count": "30",
                "expected_file_names": json.dumps(names),
                "upload_manifest": json.dumps({"client_selected_count": 30, "batch_complete": True}),
            },
        )
        if r2.status_code != 200:
            errors.append(f"batch2 failed: {r2.text}")
        else:
            b2 = r2.json()
            if b2.get("verified_file_count") != 30:
                errors.append(f"batch2 verified={b2.get('verified_file_count')} expected 30")
            if not b2.get("customer_may_show_success"):
                errors.append("batch2 must show customer success when complete")
            if b2.get("custody_status") != "verified_complete":
                errors.append(f"batch2 custody={b2.get('custody_status')}")

    # 3) No fake success on 9/10 single POST
    r = c.post(
        "/api/founding-pilot/upload",
        files=[pdf(f"n{i}.pdf") for i in range(9)],
        data={
            "email": "partial@example.com",
            "expected_file_count": "10",
            "expected_file_names": json.dumps([f"n{i}.pdf" for i in range(10)]),
        },
    )
    if r.status_code != 200:
        errors.append(f"9/10 upload failed: {r.text}")
    else:
        b = r.json()
        if b.get("customer_may_show_success"):
            errors.append("9/10 must not allow customer success")
        if b.get("custody_status") != "partial_upload":
            errors.append(f"9/10 custody={b.get('custody_status')} expected partial_upload")

    # 4) Hash mismatch detected
    r = c.post(
        "/api/founding-pilot/upload",
        files=[pdf("h.pdf")],
        data={"email": "hash@example.com", "expected_file_count": "1"},
    )
    if r.status_code != 200:
        errors.append(f"hash upload failed: {r.text}")
    else:
        hiid = r.json()["intake_id"]
        (canonical_intake_dir(hiid) / "uploads" / "h.pdf").write_bytes(b"CORRUPTED")
        chk = c.get(f"/api/operator/founding-pilot/retention-check/{hiid}").json()
        if not chk.get("hash_mismatch_detected"):
            errors.append("retention-check must detect hash mismatch after corruption")

    if errors:
        print("PROOF FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("PROOF PASSED: commit order, multi-batch 30, partial 9/10, hash mismatch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
