"""Operator intake document access — list, view, download, cockpit visibility."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


def _pdf(name: str, content: bytes = b"%PDF-1.4 operator-doc") -> tuple:
    return ("files", (name, io.BytesIO(content), "application/pdf"))


def _upload(anon_client: TestClient, names: list[str], **extra) -> dict:
    data = {
        "email": "docs@acmecorp.com",
        "company": "Acme Docs Co",
        "expected_file_count": str(len(names)),
        **extra,
    }
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[_pdf(n) for n in names],
        data=data,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_queue_card_includes_documents_with_urls(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["policy-a.pdf", "policy-b.pdf"])
    iid = body["intake_id"]

    q = client.get("/api/operator/intake/queue").json()
    row = next(r for r in q["queue"] if r["intake_id"] == iid)
    docs = row.get("documents") or []
    assert len(docs) >= 2
    for doc in docs:
        assert doc.get("original_filename")
        assert doc.get("stored_filename")
        assert doc.get("extension")
        assert doc.get("size_human")
        assert doc.get("status")
        assert doc.get("sha256_short")
        assert doc.get("accessible") is True
        assert doc.get("previewable") is True
        assert doc.get("preview_mode") == "pdf"
        assert doc["preview_url"].startswith(f"/api/operator/intake/{iid}/files/")
        assert doc["preview_url"].endswith("/view")
        assert doc["download_url"].endswith("/download")


def test_operator_files_list_endpoint(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["list-me.pdf"])
    iid = body["intake_id"]

    r = client.get(f"/api/operator/intake/{iid}/files")
    assert r.status_code == 200
    payload = r.json()
    assert payload["ok"] is True
    assert payload["file_count"] >= 1
    assert payload["documents"][0]["download_url"]


def test_verified_file_view_and_download(fb_env, anon_client: TestClient, client: TestClient):
    content = b"%PDF-1.4 verified-download-test"
    data = {
        "email": "docs@acmecorp.com",
        "company": "Acme",
        "expected_file_count": "1",
    }
    r = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("verified-download.pdf", io.BytesIO(content), "application/pdf"))],
        data=data,
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    stored = "verified-download.pdf"

    dl = client.get(f"/api/operator/intake/{iid}/files/{stored}/download")
    assert dl.status_code == 200
    assert dl.content == content
    assert "attachment" in (dl.headers.get("content-disposition") or "").lower()

    view = client.get(f"/api/operator/intake/{iid}/files/{stored}/view")
    assert view.status_code == 200
    assert view.content == content
    assert "inline" in (view.headers.get("content-disposition") or "").lower()


def test_missing_file_shows_explicit_error(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["present.pdf"])
    iid = body["intake_id"]

    r = client.get(f"/api/operator/intake/{iid}/files/not-on-disk.pdf/download")
    assert r.status_code == 404
    detail = r.json().get("detail")
    if isinstance(detail, dict):
        assert detail.get("error") == "file_not_on_disk"
        assert "not found" in detail.get("message", "").lower()
    else:
        assert "not found" in str(detail).lower()


def test_unauthorized_file_access_fails(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["secret.pdf"])
    iid = body["intake_id"]
    stored = "secret.pdf"

    for path in (
        f"/api/operator/intake/{iid}/files",
        f"/api/operator/intake/{iid}/files/{stored}/download",
        f"/api/operator/intake/{iid}/files/{stored}/view",
    ):
        r = anon_client.get(path)
        assert r.status_code == 403, path
        assert r.json().get("detail") == "Unauthorized"


def test_no_public_document_leak(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["leak-test.pdf"])
    iid = body["intake_id"]
    stored = "leak-test.pdf"

    r = anon_client.get(f"/api/operator/intake/{iid}/files/{stored}/download")
    assert r.status_code == 403

    r2 = anon_client.get(f"/api/founding-beta/upload")
    assert r2.status_code == 405


def test_control_html_renders_documents_section(client: TestClient):
    r = client.get("/ui/control.html")
    assert r.status_code == 200
    text = r.text
    assert "fb-queue-documents" in text
    assert "buildDocumentsSection" in text
    assert "fb-doc-preview" in text
    assert "openDocumentPreview" in text
    assert "Preview</button>" in text or "Preview</button> " in text


def test_path_traversal_blocked(fb_env, anon_client: TestClient, client: TestClient):
    body = _upload(anon_client, ["safe.pdf"])
    iid = body["intake_id"]
    r = client.get(f"/api/operator/intake/{iid}/files/../../intake.json/download")
    assert r.status_code in (400, 404)
