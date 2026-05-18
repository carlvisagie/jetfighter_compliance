from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from organism.database import Base

class EventLog(Base):
    __tablename__ = "event_log"
    id = Column(String, primary_key=True, index=True)
    event_type = Column(String, index=True)
    client_id = Column(String, index=True)
    project_id = Column(String, index=True)
    artifact_id = Column(String, index=True)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class ContinuityState(Base):
    __tablename__ = "continuity_state"
    id = Column(String, primary_key=True, index=True)
    client_id = Column(String, index=True)
    current_stage = Column(String)
    last_action = Column(String)
    next_action = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)
