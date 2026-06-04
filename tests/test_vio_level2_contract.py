"""VIO Level 2 contract — the composite endpoint MUST surface every payload
key the landscape renderer reads, for both clean and complex intakes.

The Level 2 SVG renderer (ui/assets/js/vio-level2.js) walks the response
shape directly. If the backend drops a key the renderer reads, the
landscape collapses silently — so we lock the contract here.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient


# ── shared upload helper ─────────────────────────────────────────────────
def _pdf(name: str, content: bytes = b"%PDF-1.4 l2-doc") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _upload(anon_client: TestClient, names: list[str], **extra) -> dict:
    data = {
        "email": "l2@vio-test.com",
        "company": "Level Two Co",
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


# ── 1. Intake-context block ──────────────────────────────────────────────
def test_level2_intake_context_block_is_present(fb_env, anon_client, client):
    """vio-level2.js reads detail.intake_context.{context, phone, deadline,
    urgent, expected_file_count} — the keys must exist on every response."""
    body = _upload(
        anon_client,
        ["scope.pdf"],
        context="Need CMMC Level 2 readiness for DoD subcontract.",
        phone="555-555-1234",
        deadline="2026-08-01",
    )
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    assert detail.get("ok") is True
    ictx = detail.get("intake_context")
    assert isinstance(ictx, dict), "intake_context block is required for L2 intake branch"
    for key in ("context", "phone", "deadline", "urgent", "expected_file_count"):
        assert key in ictx, f"intake_context missing key: {key}"
    # And the customer's free-text context must round-trip
    assert "CMMC" in ictx["context"]


# ── 2. Document leaf shape ──────────────────────────────────────────────
def test_level2_document_leaves_have_all_fields_renderer_uses(
    fb_env, anon_client, client
):
    """Every document object must carry the fields vio-level2.js reads
    when rendering and when opening the leaf detail panel."""
    body = _upload(anon_client, ["mfa.pdf", "training.pdf"])
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    docs = detail.get("uploaded_documents") or []
    assert len(docs) >= 2

    required_keys = {
        "stored_name", "original_name", "extension", "size_bytes",
        "status", "view_url", "download_url",
    }
    for d in docs:
        missing = required_keys - set(d.keys())
        assert not missing, f"document leaf missing keys for L2 render: {missing}"


# ── 3. Findings / gaps / generated arrays are always present ────────────
def test_level2_arrays_are_always_present_even_when_empty(
    fb_env, anon_client, client
):
    """L2 renders branches conditionally on `len(array) > 0`. Arrays must
    exist (possibly empty) so the renderer doesn't crash on undefined."""
    body = _upload(anon_client, ["one.pdf"])
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    for key in (
        "uploaded_documents",
        "generated_documents",
        "missing_documents",
        "findings",
        "next_actions",
    ):
        assert key in detail, f"missing top-level array: {key}"
        assert isinstance(detail[key], list), f"{key} must be a list"


# ── 4. Evidence block surfaces the profile used by identifier branch ────
def test_level2_evidence_profile_is_present(fb_env, anon_client, client):
    """vio-level2.js reads detail.evidence.profile.{technologies, vendors,
    compliance_references, company_names} to build the identifier
    cluster. The block must exist even when EI hasn't run."""
    body = _upload(anon_client, ["a.pdf"])
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    ev = detail.get("evidence")
    assert isinstance(ev, dict), "evidence block required"
    assert "profile" in ev, "evidence.profile required (may be empty dict)"
    assert isinstance(ev["profile"], dict)


# ── 5. Stage/state fields used by L2 spine come from L1 overview ────────
def test_level2_stage_fields_present_on_overview_row(fb_env, anon_client, client):
    """The L2 module receives the company object from the L1 overview row.
    It reads {stage, stage_index, stage_state, initials, company_name,
    contact_email, intake_id} — all must be present."""
    body = _upload(anon_client, ["alpha.pdf"])
    iid = body["intake_id"]

    overview = client.get("/api/operator/vio/overview").json()
    rows = overview.get("companies") or []
    target = next((c for c in rows if c.get("intake_id") == iid), None)
    assert target is not None

    for key in (
        "stage", "stage_index", "stage_state",
        "initials", "company_name", "contact_email", "intake_id",
    ):
        assert key in target, f"L1 row missing field needed by L2: {key}"


# ── 6. Bottleneck + next_actions feed the side panel overview ───────────
def test_level2_side_panel_overview_fields_exist(fb_env, anon_client, client):
    body = _upload(anon_client, ["gamma.pdf"])
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    assert "bottleneck" in detail
    assert "next_actions" in detail
    assert "review_status" in detail
    assert "age_hours" in detail


# ── 7. Classification block feeds the "category" branch (above classify) ─
def test_level2_classification_block_is_present(fb_env, anon_client, client):
    """vio-level2.js reads detail.classification.{primary_category,
    secondary_category, scope_label} to render the category cluster above
    the classification stage anchor. Block must exist (may be empty)."""
    body = _upload(anon_client, ["delta.pdf"])
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    cls = detail.get("classification")
    assert isinstance(cls, dict), "classification block required for L2 category branch"
    for key in ("primary_category", "secondary_category", "scope_label"):
        assert key in cls, f"classification missing key: {key}"


# ── 8. Confirmation-needed list feeds the "confirmation" branch ─────────
def test_level2_confirmation_needed_is_a_list(fb_env, anon_client, client):
    """vio-level2.js renders a confirmation cluster from detail.confirmation_needed.
    The key must exist as a list (possibly empty) so the renderer never
    crashes on `undefined.length`."""
    body = _upload(anon_client, ["epsilon.pdf"])
    iid = body["intake_id"]

    detail = client.get(f"/api/operator/vio/company/{iid}").json()
    assert "confirmation_needed" in detail
    assert isinstance(detail["confirmation_needed"], list)
