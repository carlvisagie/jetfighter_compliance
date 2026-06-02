from services.process import init_workflow, compute_status, mark_done, set_phase
from services import process as PR
from pathlib import Path
import json

def test_workflow_required_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(PR, "WF_DIR", tmp_path/"wf"); PR.WF_DIR.mkdir(parents=True, exist_ok=True)
    pid = "P-T-1"
    init_workflow(pid, ["CMMC-L1"])
    st = compute_status(pid)
    assert st["counts"]["required_open"] > 0
    set_phase(pid, "SCOPE")
    st2 = compute_status(pid)
    assert st2["phase"] == "SCOPE"
    # mark a known step done
    mark_done(pid, "intake_received")
    st3 = compute_status(pid)
    assert st3["counts"]["done"] >= 1
