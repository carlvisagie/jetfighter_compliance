import io
import json
from fastapi.testclient import TestClient

def test_json_upload(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("test.json", io.BytesIO(b'{"hello": "world"}'), "application/json"))],
        data={
            "email": "test@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["test.json"])
        }
    )
    assert r.status_code == 200
    res = r.json()
    assert res["verified_file_count"] == 1
    assert res["rejected_file_count"] == 0

def test_xlsx_upload(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("test.xlsx", io.BytesIO(b'dummy'), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
        data={
            "email": "test@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["test.xlsx"])
        }
    )
    assert r.status_code == 200
    res = r.json()
    assert res["verified_file_count"] == 1

def test_xml_upload(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("test.xml", io.BytesIO(b'<test></test>'), "application/xml"))],
        data={
            "email": "test@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["test.xml"])
        }
    )
    assert r.status_code == 200
    res = r.json()
    assert res["verified_file_count"] == 1

def test_unsupported_extension(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("test.exe", io.BytesIO(b'MZ...'), "application/x-msdownload"))],
        data={
            "email": "test@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["test.exe"])
        }
    )
    assert r.status_code == 400
    res = r.json()
    assert "File type not allowed: .exe. Allowed formats:" in res["detail"]

def test_ground_truth_classification(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("ground_truth.json", io.BytesIO(b'{"test": 1}'), "application/json"))],
        data={
            "email": "test@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["ground_truth.json"])
        }
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    from services.intake.classification import classify_intake
    clf = classify_intake(iid)
    assert clf["primary_category"] == "Test artifact"

def test_company_profile_classification(fb_env, anon_client: TestClient):
    r = anon_client.post(
        "/api/intake/upload",
        files=[("files", ("company_profile.json", io.BytesIO(b'{"test": 1}'), "application/json"))],
        data={
            "email": "test@example.com",
            "expected_file_count": "1",
            "expected_file_names": json.dumps(["company_profile.json"])
        }
    )
    assert r.status_code == 200
    iid = r.json()["intake_id"]
    from services.intake.classification import classify_intake
    clf = classify_intake(iid)
    assert clf["primary_category"] == "Structured metadata"
