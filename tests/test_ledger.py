from pathlib import Path
from services.ledger import append_ledger, register_artifact, file_sha256

def test_hash_chain(tmp_path, monkeypatch):
    from services import ledger as L
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(L, "LEDGER_FILE", tmp_path / "ledger.log")
    r1 = append_ledger({"kind":"event","event_type":"ATTEST"})
    r2 = append_ledger({"kind":"event","event_type":"PACK"})
    assert r2["prev_hash"] == r1["hash"]

def test_register_artifact(tmp_path, monkeypatch):
    from services import ledger as L
    monkeypatch.setattr(L, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(L, "LEDGER_FILE", tmp_path / "ledger.log")
    f = tmp_path / "doc.txt"; f.write_text("hello")
    rec = register_artifact("P-1", f, "text/plain", "QA")
    assert rec["sha256"] == file_sha256(f)
