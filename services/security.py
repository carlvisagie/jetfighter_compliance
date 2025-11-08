import hmac, hashlib, base64, time
from itsdangerous import URLSafeSerializer
from .config import SETTINGS

def verify_shopify_hmac(raw_body: bytes, hmac_header: str) -> bool:
    digest = hmac.new(SETTINGS.shopify_webhook_secret.encode(), raw_body, hashlib.sha256).digest()
    calc_hmac = base64.b64encode(digest).decode()
    return hmac.compare_digest(calc_hmac, hmac_header or "")

_signer = URLSafeSerializer(SETTINGS.intake_token_secret, salt="intake")

def make_intake_token(project_id: str, email: str) -> str:
    return _signer.dumps({"p": project_id, "e": email, "ts": int(time.time())})

def parse_intake_token(token: str) -> dict:
    return _signer.loads(token)
