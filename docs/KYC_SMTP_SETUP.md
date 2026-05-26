# KYC SMTP setup (production)

## Required environment variables

The app reads **canonical** names first; **aliases** are supported for compatibility:

| Canonical | Alias | Required | Notes |
|-----------|-------|----------|-------|
| `SMTP_ENABLED` | — | **Yes** | Must be `true` |
| `SMTP_HOST` | `SMTP_SERVER` | **Yes** | e.g. `smtp.sendgrid.net` |
| `SMTP_PORT` | — | No (default `587`) | STARTTLS on connect |
| `SMTP_USER` | `SMTP_USERNAME` | **Yes** | SMTP auth user |
| `SMTP_PASS` | `SMTP_PASSWORD` | **Yes** | Secret — never log |
| `SMTP_FROM_EMAIL` | `SMTP_FROM` | Recommended | From address |
| `SMTP_FROM_NAME` | — | No | Default `KeepYourContracts` |

TLS: the code uses `smtplib.SMTP` + `starttls()` (typical port 587). No separate SSL flag.

## Render (`kyc-backend`)

Set in Dashboard → Environment:

```
SMTP_ENABLED=true
SMTP_HOST=<your-smtp-host>
SMTP_PORT=587
SMTP_USER=<username>
SMTP_PASS=<password>
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=KeepYourContracts
```

## Verify

1. `GET /health/ready` → `checks.smtp_configured: true`
2. Operator login → Control → **Send SMTP test email**
3. `POST /api/operator/test-email` with `{"to":"your@email.com"}` (session or `X-Ops-Key`)
4. Telemetry: `email/send_attempted` then `email/send_success` or `email/send_failed`

## Customer paths that send email

- `kickoff()` — welcome + intake link after project creation
- `POST /api/inquiry/submit` — optional notify to `DIGEST_EMAIL_TO`
