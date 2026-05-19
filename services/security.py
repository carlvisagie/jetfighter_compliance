import time
from itsdangerous import URLSafeSerializer
from .config import SETTINGS

_signer = URLSafeSerializer(SETTINGS.intake_token_secret, salt="intake")

def make_intake_token(project_id: str, email: str) -> str:
    return _signer.dumps({"p": project_id, "e": email, "ts": int(time.time())})

def parse_intake_token(token: str) -> dict:
    return _signer.loads(token)
