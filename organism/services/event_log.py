import uuid
from organism.database import SessionLocal
from organism.models import EventLog

def write_event(event_type, client_id="unknown", project_id="unknown", artifact_id="unknown", details=""):
    db = SessionLocal()
    event_id = str(uuid.uuid4())

    event = EventLog(
        id=event_id,
        event_type=event_type,
        client_id=client_id,
        project_id=project_id,
        artifact_id=artifact_id,
        details=details
    )

    db.add(event)
    db.commit()
    db.close()

    return event_id
