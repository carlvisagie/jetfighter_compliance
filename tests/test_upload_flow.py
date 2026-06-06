import io
from services.security import make_intake_token


def test_intake_resolve_and_evidence_register(client):
    kick = client.post(
        "/events/payment/test",
        json={"order_id": "UPLOAD-T1", "email": "upload@example.com", "name": "Up", "skus": ["TEST"]},
    )
    assert kick.status_code == 200
    project_id = kick.json()["project_id"]

    res = client.get(f"/api/intake/resolve?token=invalid")
    assert res.status_code == 401

    # Token is required since SEC-003 fix — generate a valid signed token for this project
    token = make_intake_token(project_id, "upload@example.com")
    file_content = b"evidence sample"
    r = client.post(
        f"/api/evidence/register?project_id={project_id}&media_type=document&owner=upload@example.com&token={token}",
        files={"file": ("sample.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_evidence_register_rejects_without_token(client):
    """SEC-003 guard: unauthenticated uploads must be rejected."""
    r = client.post(
        "/api/evidence/register?project_id=P-FAKE-001&media_type=document&owner=anon@test.com",
        files={"file": ("x.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert r.status_code == 403
