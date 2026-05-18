from organism.database import engine, Base
from organism.services.event_log import write_event

Base.metadata.create_all(bind=engine)

event_id = write_event(
    event_type="UPLOAD_RECEIVED",
    client_id="client_001",
    details="First organism event"
)

print(event_id)
