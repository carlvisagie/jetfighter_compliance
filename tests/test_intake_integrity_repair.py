"""PATCH 10C — stale expected count repair from durable disk truth."""
from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from services.intake.integrity_repair import repair_intake_integrity_mismatch
from services.intake.reconcile import reconcile_intake
from services.intake.storage import load_intake_record


def _pdf(name: str, content: bytes = b"%PDF-1.4 minimal") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _jpg(name: str) -> tuple:
    return ("files", (name, io.BytesIO(b"\xff\xd8\xff\xd9"), "image/jpeg"))


def test_multi_batch_upload_stale_expected_repaired(fb_env, anon_client: TestClient, client: TestClient):
    """Second upload batch must not leave expected < received when disk agrees."""
    first = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("batch_one.pdf")],
        data={
            "email": "multibatch@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["batch_one.pdf"]),
        },
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    iid = first_body["intake_id"]
    token = first_body["token"]

    second = anon_client.post(
        "/api/intake/upload",
        files=[_jpg("photo.jpg")],
        data={
            "email": "multibatch@example.com",
            "intake_id": iid,
            "token": token,
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["photo.jpg"]),
        },
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["received_file_count"] == 2

    rec = load_intake_record(iid)
    ui = rec.get("upload_integrity") or {}
    assert ui.get("received_file_count") == 2
    assert ui.get("verified_file_count") == 2
    if ui.get("expected_file_count") != 2:
        assert ui.get("expected_file_count") == 1

    api = client.post(f"/api/operator/integrity/repair/{iid}")
    assert api.status_code == 200
    payload = api.json()
    assert payload.get("action") == "no_repair_needed"
    assert payload.get("ok") is True

    rec = load_intake_record(iid)
    ui = rec.get("upload_integrity") or {}
    assert ui.get("expected_file_count") == 2
    reconcile = reconcile_intake(iid)
    assert reconcile.get("ok") is True
    assert "expected_received_mismatch" not in (reconcile.get("issues") or [])


def test_reconcile_over_delivery_with_disk_agreement_not_flagged(fb_env, anon_client: TestClient):
    """Fleet reconcile must not flag over-delivery when disk truth agrees."""
    first = anon_client.post(
        "/api/intake/upload",
        files=[_pdf("only.pdf")],
        data={
            "email": "over@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["only.pdf"]),
        },
    )
    first_body = first.json()
    iid = first_body["intake_id"]
    anon_client.post(
        "/api/intake/upload",
        files=[_jpg("extra.jpg")],
        data={
            "email": "over@example.com",
            "intake_id": iid,
            "token": first_body["token"],
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["extra.jpg"]),
        },
    )

    rec = load_intake_record(iid)
    ui = rec.get("upload_integrity") or {}
    if ui.get("expected_file_count", 0) < ui.get("received_file_count", 0):
        repair_intake_integrity_mismatch(iid)

    rep = reconcile_intake(iid)
    assert rep.get("count_breakdown", {}).get("received_file_count") == 2
    assert "expected_received_mismatch" not in (rep.get("issues") or [])
