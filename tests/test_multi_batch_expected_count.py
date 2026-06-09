import pytest
import asyncio
from typing import List, Dict, Any

from fastapi import UploadFile
from fastapi.testclient import TestClient

def test_single_batch_upload(fb_env, anon_client: TestClient):
    r1 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("test1.pdf", b"test1", "application/pdf")),
            ("files", ("test2.pdf", b"test2", "application/pdf")),
        ],
        data={
            "email": "single@example.com",
            "expected_file_count": "2",
        }
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["expected_file_count"] == 2
    assert d1["received_file_count"] == 2
    assert d1["verified_file_count"] == 2
    assert d1["integrity_mismatch"] == False


def test_multi_batch_upload(fb_env, anon_client: TestClient):
    r1 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("test1.pdf", b"test1", "application/pdf")),
            ("files", ("test2.pdf", b"test2", "application/pdf")),
        ],
        data={
            "email": "batch@example.com",
            "expected_file_count": "2",
        }
    )
    assert r1.status_code == 200
    d1 = r1.json()
    
    iid = d1["intake_id"]
    token = d1.get("token") or "dummy"
    
    r2 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("test3.pdf", b"test3", "application/pdf")),
        ],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "1",
        }
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["expected_file_count"] == 3
    assert d2["received_file_count"] == 3
    assert d2["verified_file_count"] == 3
    assert d2["integrity_mismatch"] == False


def test_resume_upload_expected_count(fb_env, anon_client: TestClient):
    # Same as multi-batch but explicit resume token naming if applicable
    r1 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("test1.pdf", b"test1", "application/pdf")),
        ],
        data={
            "email": "resume@example.com",
            "expected_file_count": "5",
        }
    )
    assert r1.status_code == 200
    d1 = r1.json()
    iid = d1["intake_id"]
    token = d1.get("token") or "dummy"
    
    r2 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("test2.pdf", b"test2", "application/pdf")),
        ],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "2", # Suppose they added 2 files in this resume batch
        }
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["expected_file_count"] == 7
    assert d2["received_file_count"] == 2
    assert d2["integrity_mismatch"] == True # Because we received 2, expected 7 total, so expected > received


def test_phone_camera_continuation(fb_env, anon_client: TestClient):
    # Simulate magic-link / phone-camera continuation where a previous batch is uploaded and then from phone we upload another
    r1 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("desktop.pdf", b"test1", "application/pdf")),
        ],
        data={
            "email": "phone@example.com",
            "expected_file_count": "1",
        }
    )
    assert r1.status_code == 200
    d1 = r1.json()
    iid = d1["intake_id"]
    token = d1.get("token") or "dummy"
    
    # Upload from phone
    r2 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("photo.jpg", b"image", "image/jpeg")),
        ],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "1",
            "upload_manifest": '{"upload_session_id": "phone123"}'
        }
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["expected_file_count"] == 2
    assert d2["received_file_count"] == 2
    assert d2["verified_file_count"] == 2
    assert d2["integrity_mismatch"] == False


def test_integrity_report_no_false_mismatch(fb_env, anon_client: TestClient):
    # This was the core issue
    import json
    
    expected_names1 = ["test1.pdf", "test2.pdf"] + [f"test{i}.pdf" for i in range(3, 11)]
    r1 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", ("test1.pdf", b"test1", "application/pdf")),
            ("files", ("test2.pdf", b"test2", "application/pdf")),
        ],
        data={
            "email": "integrity@example.com",
            "expected_file_count": "10",
            "expected_file_names": json.dumps(expected_names1)
        }
    )
    assert r1.status_code == 200
    d1 = r1.json()
    iid = d1["intake_id"]
    token = d1.get("token") or "dummy"
    
    expected_names2 = ["test11.pdf"]
    r2 = anon_client.post(
        "/api/intake/upload",
        files=[
            ("files", (f"test{i}.pdf", b"test", "application/pdf")) for i in range(3, 12)
        ],
        data={
            "intake_id": iid,
            "token": token,
            "expected_file_count": "1", # Say they expected 10 in batch 1, but then added 1 more in batch 2
            "expected_file_names": json.dumps(expected_names2)
        }
    )
    assert r2.status_code == 200
    d2 = r2.json()
    print("MISSING FILES:", d2.get("missing_files"))
    print("REJECTED FILES:", d2.get("rejected_files"))
    print("FAILED FILES:", d2.get("failed_file_count"))
    
    # Total expected: 11
    # Total received: 11
    assert d2["expected_file_count"] == 11
    assert d2["received_file_count"] == 11
    assert d2["verified_file_count"] == 11
    assert d2["integrity_mismatch"] == False
