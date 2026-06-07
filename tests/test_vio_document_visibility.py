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


def test_company_detail_loads_evidence_via_intake_id_fallback(
    fb_env, anon_client: TestClient, client: TestClient
):
    """REGRESSION GUARD — operator drill-down must surface evidence for
    founding-pilot intakes that have no kickoff project yet.

    Doctrine alignment: L1 overview loads EI as `project_id or
    intake_id`. L2 detail used to gate on `project_id` only, so freshly
    uploaded founding-pilot intakes (no kickoff yet) drilled in to an
    empty evidence block despite EI artifacts being written under
    `intake_id` by the upload hook. This test pins the fallback so
    the bug cannot return silently.
    """
    from services.evidence_intelligence import storage as ei_storage
    from services.intake.intake import _load_intake, _save_intake

    body = _upload(anon_client, ["mfa-policy.pdf"])
    iid = body["intake_id"]

    # Sanity: this is an intake-only customer (no kickoff project).
    rec = _load_intake(iid)
    assert not rec.get("project_id"), (
        "this guard probes the intake-only case; remove project_id "
        "from the record to keep the scenario honest"
    )

    # Seed a profile under the intake_id key the way EI does after the
    # upload hook runs — independent of whether the hook ran fully in
    # this test environment. The bucket name is `company_name_candidates`
    # (see services/evidence_intelligence/profile.py); the operator
    # endpoint flattens that to `company_names` for the UI.
    profile = ei_storage.load_profile(iid)
    profile["project_id"] = iid
    profile.setdefault("company_name_candidates", []).append({
        "value": "VIO Visibility Co",
        "confidence": 0.9,
        "status": "confirmed",
    })
    ei_storage.write_profile(iid, profile)

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    assert detail.get("ok") is True
    ev = detail.get("evidence") or {}
    assert ev.get("available") is True, (
        "evidence block must load via intake_id when project_id is "
        "absent; got %r" % (ev,)
    )
    prof = ev.get("profile") or {}
    names = prof.get("company_names") or []
    assert "VIO Visibility Co" in names, (
        "evidence profile must come back keyed on intake_id; got %r"
        % (names,)
    )


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
