from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROJECTS = DATA / "projects"
LOGS = DATA / "logs"
for p in (DATA, PROJECTS, LOGS):
    p.mkdir(parents=True, exist_ok=True)

class Settings(BaseModel):
    auto_night_export: bool = os.getenv('AUTO_NIGHT_EXPORT','true').lower()=='true'
    weekly_digest: bool = os.getenv('WEEKLY_DIGEST','true').lower()=='true'
    digest_email_to: str = os.getenv('DIGEST_EMAIL_TO','')
    export_keep_latest: int = int(os.getenv('EXPORT_KEEP_LATEST','5'))
    smtp_enabled: bool = os.getenv('SMTP_ENABLED','false').lower()=='true'
    shopify_webhook_secret: str = Field(default=os.getenv("SHOPIFY_WEBHOOK_SECRET",""))
    smtp_host: str = os.getenv("SMTP_HOST","")
    smtp_port: int = int(os.getenv("SMTP_PORT","587"))
    smtp_user: str = os.getenv("SMTP_USER","")
    smtp_pass: str = os.getenv("SMTP_PASS","")
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME","KeepYourContracts")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL","")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL","http://127.0.0.1:8080")
    intake_token_secret: str = os.getenv("INTAKE_TOKEN_SECRET","dev-dev-dev-dev-dev")

SETTINGS = Settings()




