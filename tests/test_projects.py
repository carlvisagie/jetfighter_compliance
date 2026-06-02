from services.projects import new_project
from pathlib import Path
from services.config import PROJECTS

def test_new_project(tmp_path, monkeypatch):
    monkeypatch.setattr("services.projects.PROJECTS", tmp_path)
    meta = new_project("1001","buyer@example.com","Buyer Name",["CMMC-L1"])
    pid = meta["project_id"]
    assert (tmp_path/pid/"meta.json").exists()
    assert (tmp_path/pid/"checklist.json").exists()
    assert (tmp_path/pid/"evidence").exists()
