"""Communications evidence layer — ledger, delay attribution, forensic integrity."""
from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from server import app


def _pdf(name: str, content: bytes = b"%PDF-1.4 comm-evidence") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _upload(client: TestClient, names: list[str], **extra) -> dict:
    data = {
        "email": "comm@acmecorp.com",
        "company": "Acme Corp",
        "expected_file_count": str(len(names)),
        "expected_file_names": json.dumps(names),
        **extra,
    }
    r = client.post("/api/intake/upload", files=[_pdf(n) for n in names], data=data)
    assert r.status_code == 200, r.text
    return r.json()


def _log(client: TestClient, payload: dict) -> dict:
    r = client.post("/api/operator/communications/log", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["communication"]


@pytest.fixture
def comm_env(fb_env, monkeypatch):
    """Isolated communications ledger under KYC_DATA."""
    ledger = fb_env / "communications" / "communications_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "services.communications.ledger._data_root",
        lambda: fb_env,
    )
    return fb_env


def test_email_logged_to_intake(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-email.pdf"])
    iid = body["intake_id"]

    rec = _log(
        client,
        {
            "intake_id": iid,
            "direction": "outbound",
            "channel": "email",
            "timestamp": "2026-06-01T14:00:00Z",
            "sender": "ops@keepyourcontracts.com",
            "recipient": "comm@acmecorp.com",
            "subject": "Welcome — next steps",
            "body": "Please upload your SSP when ready.",
            "delay_relevance": "unknown",
        },
    )

    assert rec["communication_id"].startswith("comm-")
    assert rec["company_id"].startswith("co-")
    assert rec["record_hash"]
    assert rec["intake_id"] == iid

    found = client.get("/api/operator/communications/search", params={"intake_id": iid, "channel": "email"}).json()
    assert found["count"] == 1
    assert found["communications"][0]["subject"] == "Welcome — next steps"


def test_phone_transcript_logged_to_intake(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-phone.pdf"])
    iid = body["intake_id"]

    rec = _log(
        client,
        {
            "intake_id": iid,
            "direction": "inbound",
            "channel": "phone",
            "timestamp": "2026-06-02T16:30:00Z",
            "sender": "comm@acmecorp.com",
            "recipient": "ops@keepyourcontracts.com",
            "subject": "Kickoff call",
            "body": "Client confirmed scope and asked for document checklist.",
            "attachments": [{"ref": "recordings/call-20260602.wav", "kind": "audio"}],
            "delay_relevance": "no",
        },
    )

    assert rec["channel"] == "phone"
    assert rec["attachments"][0]["kind"] == "audio"

    detail = client.get(f"/api/operator/communications/{rec['communication_id']}").json()
    assert "checklist" in detail["communication"]["body"]


def test_missing_document_request_creates_delay_evidence(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-delay.pdf"])
    iid = body["intake_id"]

    rec = _log(
        client,
        {
            "intake_id": iid,
            "direction": "outbound",
            "channel": "document_request",
            "timestamp": "2026-06-01T09:00:00Z",
            "sender": "ops@keepyourcontracts.com",
            "recipient": "comm@acmecorp.com",
            "subject": "Missing SSP",
            "body": "Please provide your System Security Plan.",
            "delay_relevance": "yes",
            "delay_category": "missing_document",
            "delay_reason": "requested missing SSP",
            "related_document_ids": ["ssp-template"],
        },
    )

    assert rec["delay_event_id"].startswith("delay-")

    report = client.get(f"/api/operator/communications/delay-report/{iid}").json()
    assert report["attribution_count"] >= 1
    attr = report["attributions"][0]
    assert attr["opening_communication_id"] == rec["communication_id"]
    assert attr["closed_at_utc"] is None
    assert "SSP" in attr["narrative"] or "ssp" in attr["narrative"].lower()


def test_customer_response_closes_delay_period(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-close.pdf"])
    iid = body["intake_id"]

    opening = _log(
        client,
        {
            "intake_id": iid,
            "direction": "outbound",
            "channel": "document_request",
            "timestamp": "2026-06-01T09:00:00Z",
            "sender": "ops@keepyourcontracts.com",
            "recipient": "comm@acmecorp.com",
            "subject": "Missing SSP",
            "body": "Please provide SSP.",
            "delay_relevance": "yes",
            "delay_category": "missing_document",
            "delay_reason": "requested missing SSP",
        },
    )

    _log(
        client,
        {
            "intake_id": iid,
            "direction": "inbound",
            "channel": "customer_response",
            "timestamp": "2026-06-09T11:00:00Z",
            "sender": "comm@acmecorp.com",
            "recipient": "ops@keepyourcontracts.com",
            "subject": "SSP attached",
            "body": "SSP uploaded per request.",
            "delay_relevance": "yes",
            "delay_event_id": opening["delay_event_id"],
        },
    )

    report = client.get(f"/api/operator/communications/delay-report/{iid}").json()
    attr = report["attributions"][0]
    assert attr["closed_at_utc"] == "2026-06-09T11:00:00Z"
    assert attr["delay_days"] == 8
    assert "June 1" in attr["narrative"]
    assert "June 9" in attr["narrative"]


def test_delay_report_cites_communication(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-cite.pdf"])
    iid = body["intake_id"]

    _log(
        client,
        {
            "intake_id": iid,
            "direction": "outbound",
            "channel": "document_request",
            "timestamp": "2026-06-01T09:00:00Z",
            "sender": "ops@keepyourcontracts.com",
            "recipient": "comm@acmecorp.com",
            "subject": "Missing SSP",
            "delay_relevance": "yes",
            "delay_category": "missing_document",
            "delay_reason": "requested missing SSP",
        },
    )
    _log(
        client,
        {
            "intake_id": iid,
            "direction": "inbound",
            "channel": "customer_response",
            "timestamp": "2026-06-09T11:00:00Z",
            "sender": "comm@acmecorp.com",
            "recipient": "ops@keepyourcontracts.com",
            "subject": "SSP received",
            "delay_relevance": "yes",
        },
    )

    report = client.get(f"/api/operator/communications/delay-report/{iid}").json()
    narrative = report["attributions"][0]["narrative"]
    assert narrative.startswith("Client delay:")
    assert "8 days" in narrative
    assert "requested missing SSP" in narrative


def test_communication_hash_mismatch_creates_integrity_incident(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-hash.pdf"])
    iid = body["intake_id"]

    rec = _log(
        client,
        {
            "intake_id": iid,
            "direction": "outbound",
            "channel": "email",
            "timestamp": "2026-06-03T10:00:00Z",
            "sender": "ops@keepyourcontracts.com",
            "recipient": "comm@acmecorp.com",
            "subject": "Integrity test",
            "body": "Original body",
            "delay_relevance": "no",
        },
    )

    from services.communications.ledger import ledger_path

    path = ledger_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[-1])
    tampered["body"] = "TAMPERED body"
    lines[-1] = json.dumps(tampered, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    from services.communications.reconcile import reconcile_communications_ledger

    comm_report = reconcile_communications_ledger()
    assert comm_report["ok"] is False
    assert comm_report["hash_mismatch_count"] >= 1
    codes = {i["issue_code"] for i in comm_report["incidents"]}
    assert "communication_hash_mismatch" in codes

    reconcile = client.get("/api/operator/integrity/reconcile").json()
    subsystems = {d.get("subsystem") for d in reconcile.get("disagreements") or []}
    issue_codes = {d.get("issue_code") for d in reconcile.get("disagreements") or []}
    assert "communications_ledger" in subsystems or "communication_hash_mismatch" in issue_codes

    proof = client.get("/api/operator/integrity/proof").json()
    assert proof.get("communications_ledger_ok") is False
    assert proof.get("communications_hash_mismatches", 0) >= 1


def test_custody_timeline_includes_communication_markers(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-timeline.pdf"])
    iid = body["intake_id"]

    _log(
        client,
        {
            "intake_id": iid,
            "direction": "outbound",
            "channel": "document_request",
            "timestamp": "2026-06-01T09:00:00Z",
            "sender": "ops@keepyourcontracts.com",
            "recipient": "comm@acmecorp.com",
            "subject": "Missing SSP",
            "delay_relevance": "yes",
            "delay_category": "missing_document",
            "delay_reason": "requested missing SSP",
        },
    )

    tl = client.get(f"/api/operator/integrity/timeline/{iid}").json()
    events = tl.get("events") or []
    comm_events = [e for e in events if e.get("event") == "communication"]
    delay_events = [e for e in events if e.get("event") == "client_delay_segment"]
    assert len(comm_events) >= 1
    assert comm_events[0].get("marker_type") == "message"
    assert len(delay_events) >= 1
    assert delay_events[0].get("marker_type") == "delay"


def test_forensic_export_includes_chain_of_custody(comm_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["comm-export.pdf"])
    iid = body["intake_id"]

    _log(
        client,
        {
            "intake_id": iid,
            "direction": "internal",
            "channel": "operator_note",
            "timestamp": "2026-06-04T12:00:00Z",
            "sender": "operator",
            "recipient": "internal",
            "subject": "Follow-up scheduled",
            "body": "Call client Friday.",
            "delay_relevance": "no",
        },
    )

    export = client.get(
        "/api/operator/communications/export/forensic",
        params={"intake_id": iid},
    ).json()
    assert export["communication_count"] >= 1
    row = export["communications"][0]
    assert row.get("hash_verified") is True
    assert row["chain_of_custody"]["record_hash"]
