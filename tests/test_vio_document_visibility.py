"""VIO Document Visibility — operator can see every document, gap, and
finding for any company without leaving VIO.

Covers the contract for /api/operator/vio/company/{intake_id} and
the organism strip surfaced inside /api/operator/vio/overview.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _pdf(name: str, content: bytes = b"%PDF-1.4 vio-doc") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _upload(anon_client: TestClient, names: list[str], **extra) -> dict:
    data = {
        "email": "ops@vio-test.com",
        "company": "VIO Visibility Co",
        "expected_file_count": str(len(names)),
        **extra,
    }
    r = anon_client.post(
        "/api/intake/upload",
        files=[_pdf(n) for n in names],
        data=data,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_vio_overview_includes_organism_block(fb_env, client: TestClient):
    """Header-strip data is surfaced inside the single overview fetch."""
    r = client.get("/api/operator/vio/overview")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert "organism" in data, "overview must surface organism awareness block"

    org = data["organism"]
    # Either available with full payload, or explicit failure marker — never silent absence
    assert "available" in org
    if org.get("available"):
        for key in (
            "health_state",
            "queue_depth",
            "intake_count_active",
            "intake_count_total",
            "uploaded_file_count",
            "mismatch_count",
            "mismatches",
            "environment",
        ):
            assert key in org, f"organism block missing key: {key}"


def test_company_detail_returns_uploaded_documents_with_urls(
    fb_env, anon_client: TestClient, client: TestClient
):
    """Composite endpoint exposes every uploaded document with view/download URLs."""
    body = _upload(anon_client, ["mfa-policy.pdf", "training-log.pdf"])
    iid = body["intake_id"]

    r = client.get(f"/api/operator/vio/company/{iid}")
    assert r.status_code == 200, r.text
    detail = r.json()

    assert detail.get("ok") is True
    assert detail.get("intake_id") == iid
    assert detail.get("company_name")
    assert isinstance(detail.get("uploaded_documents"), list)
    assert len(detail["uploaded_documents"]) >= 2

    for doc in detail["uploaded_documents"]:
        assert doc.get("stored_name")
        assert doc.get("original_name")
        assert doc.get("view_url"), "operator must be able to view from VIO"
        assert doc.get("download_url"), "operator must be able to download from VIO"


def test_company_detail_exposes_generated_and_missing_sections(
    fb_env, anon_client: TestClient, client: TestClient
):
    """Even with no generated docs and no EI run, sections are present (not omitted)."""
    body = _upload(anon_client, ["scope-letter.pdf"])
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    assert "generated_documents" in detail  # always present, may be empty
    assert "missing_documents" in detail
    assert "evidence" in detail
    assert "findings" in detail
    assert isinstance(detail["generated_documents"], list)
    assert isinstance(detail["missing_documents"], list)
    assert isinstance(detail["findings"], list)


def test_company_detail_requires_operator_auth(
    fb_env, anon_client: TestClient, client: TestClient
):
    """Composite endpoint must not leak to anonymous callers."""
    body = _upload(anon_client, ["secret.pdf"])
    iid = body["intake_id"]
    r = anon_client.get(f"/api/operator/vio/company/{iid}")
    assert r.status_code == 403
    assert (r.json().get("detail") or "").lower() == "unauthorized"


def test_company_detail_unknown_intake_returns_not_ok(
    fb_env, client: TestClient
):
    """Unknown intake returns ok=false rather than crashing."""
    r = client.get("/api/operator/vio/company/FB-doesnotexist-0000")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is False
    assert "intake_id" in body


def test_overview_company_row_carries_intake_id_for_detail_link(
    fb_env, anon_client: TestClient, client: TestClient
):
    """The VIO row must include the intake_id VIO uses to fetch composite detail."""
    body = _upload(anon_client, ["row.pdf"])
    iid = body["intake_id"]

    overview = client.get("/api/operator/vio/overview").json()
    rows = overview.get("companies") or []
    target = next((c for c in rows if c.get("intake_id") == iid), None)
    assert target is not None, "overview must include the uploaded intake"
    assert target.get("intake_id") == iid
    assert target.get("row_id") == iid
