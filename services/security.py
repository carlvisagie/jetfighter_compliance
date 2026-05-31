import time
from itsdangerous import URLSafeSerializer, BadSignature, SignatureExpired
from .config import SETTINGS

_signer = URLSafeSerializer(SETTINGS.intake_token_secret, salt="intake")
_continuation_signer = URLSafeSerializer(SETTINGS.intake_token_secret, salt="kyc-continuation")

# Magic continuation links (90 days)
CONTINUATION_MAX_AGE_SECONDS = 90 * 24 * 3600


def make_intake_token(project_id: str, email: str) -> str:
    return _signer.dumps({"p": project_id, "e": email, "ts": int(time.time())})


def parse_intake_token(token: str) -> dict:
    return _signer.loads(token)


def make_continuation_token(project_id: str, email: str) -> str:
    """Signed continuation token — same project/email, expiring magic link."""
    return _continuation_signer.dumps({"p": project_id, "e": email, "ts": int(time.time())})


def parse_continuation_token(token: str) -> dict:
    try:
        return _continuation_signer.loads(token, max_age=CONTINUATION_MAX_AGE_SECONDS)
    except SignatureExpired as e:
        raise ValueError("continuation_expired") from e
    except BadSignature as e:
        raise ValueError("continuation_invalid") from e


_session_signer = URLSafeSerializer(SETTINGS.intake_token_secret, salt="kyc-customer-session")
SESSION_TOKEN_MAX_AGE_SECONDS = 7 * 24 * 3600


def make_session_token(session_id: str) -> str:
    return _session_signer.dumps({"s": session_id, "ts": int(time.time())})


def parse_session_token(token: str) -> dict:
    try:
        return _session_signer.loads(token, max_age=SESSION_TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired as e:
        raise ValueError("session_expired") from e
    except BadSignature as e:
        raise ValueError("session_invalid") from e


_intake_token_signer = URLSafeSerializer(SETTINGS.intake_token_secret, salt="kyc-founding-beta")
INTAKE_TOKEN_MAX_AGE_SECONDS = 90 * 24 * 3600


def make_founding_beta_token(intake_id: str) -> str:
    """Upload magic-link token for founding-beta / intake paperwork (FB-* ids)."""
    return _intake_token_signer.dumps({"i": intake_id, "ts": int(time.time())})


def parse_founding_beta_token(token: str) -> dict:
    try:
        return _intake_token_signer.loads(token, max_age=INTAKE_TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired as e:
        raise ValueError("intake_token_expired") from e
    except BadSignature as e:
        raise ValueError("intake_token_invalid") from e
