from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]


def _resolve_data_root() -> Path:
    """Runtime data root. Production paperwork requires explicit KYC_DATA (see durable_storage)."""
    for key in ("KYC_DATA", "DATA_ROOT", "RENDER_DISK_PATH"):
        val = (os.getenv(key) or "").strip()
        if val:
            return Path(val).expanduser().resolve()
    return (ROOT / "data").resolve()


DATA = _resolve_data_root()
PROJECTS = DATA / "projects"
LOGS = DATA / "logs"
for p in (DATA, PROJECTS, LOGS):
    p.mkdir(parents=True, exist_ok=True)

class Settings(BaseModel):
    auto_night_export: bool = os.getenv('AUTO_NIGHT_EXPORT','true').lower()=='true'
    weekly_digest: bool = os.getenv('WEEKLY_DIGEST','true').lower()=='true'
    digest_email_to: str = os.getenv('DIGEST_EMAIL_TO','')
    export_keep_latest: int = int(os.getenv('EXPORT_KEEP_LATEST','5'))
    smtp_enabled: bool = os.getenv("SMTP_ENABLED", "false").lower() == "true"
    smtp_host: str = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER") or ""
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or ""
    smtp_pass: str = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD") or ""
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME", "KeepYourContracts")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_FROM") or ""
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from_email: str = os.getenv("RESEND_FROM_EMAIL", "")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL","http://127.0.0.1:8080")
    intake_token_secret: str = os.getenv("INTAKE_TOKEN_SECRET","dev-dev-dev-dev-dev")
    environment: str = os.getenv("ENVIRONMENT", "development")
    # PATCH 13A-8A: Acquisition outreach safety gate — default FALSE, must be explicitly enabled
    acquisition_auto_send_enabled: bool = os.getenv("ACQUISITION_AUTO_SEND_ENABLED", "false").lower() == "true"
    acquisition_daily_send_cap: int = int(os.getenv("ACQUISITION_DAILY_SEND_CAP", "50"))

SETTINGS = Settings()




