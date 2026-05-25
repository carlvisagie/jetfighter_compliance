import io


def test_intake_resolve_and_evidence_register(client):
    kick = client.post(
        "/events/payment/test",
        json={"order_id": "UPLOAD-T1", "email": "upload@example.com", "name": "Up", "skus": ["TEST"]},
    )
    assert kick.status_code == 200
    project_id = kick.json()["project_id"]

    res = client.get(f"/api/intake/resolve?token=invalid")
    assert res.status_code == 401

    file_content = b"evidence sample"
    r = client.post(
        f"/api/evidence/register?project_id={project_id}&media_type=document&owner=upload@example.com",
        files={"file": ("sample.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
