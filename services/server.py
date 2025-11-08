from fastapi import UploadFile, File
from services.ledger import register_artifact, record_event

@app.post("/api/coc/event")
async def coc_event(event: dict):
    # expects event JSON per schema; server stamps ts and hash-chain
    rec = record_event(event)
    return {"ok": True, "event": rec}

@app.post("/api/evidence/register")
async def evidence_register(project_id: str, media_type: str, owner: str, file: UploadFile = File(...)):
    pdir = DATA / "projects" / project_id / "evidence"
    pdir.mkdir(parents=True, exist_ok=True)
    dest = pdir / file.filename
    dest.write_bytes(await file.read())
    rec = register_artifact(project_id, dest, media_type, owner)
    return {"ok": True, "artifact": rec}
