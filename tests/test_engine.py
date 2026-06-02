from services.engine import enqueue, sweep_queue
from services import projects as P
import json

def test_post_payment_job(tmp_path, monkeypatch):
    # Redirect paths
    from services import engine as E
    monkeypatch.setattr(E, "JOBS", tmp_path / "jobs"); E.JOBS.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(P, "PROJECTS", tmp_path / "projects")
    j = enqueue("post_payment", {"order_id":"T-ENG","email":"demo@example.com","name":"Test","skus":["CMMC-L1"]})
    sweep_queue()
    job = json.loads(j.read_text())
    assert job["status"] in ("done","retry")
    if job["status"] == "done":
        pid = job["result"]["project_id"]
        assert (tmp_path / "projects" / pid / "meta.json").exists()
