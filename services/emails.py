import smtplib
from email.message import EmailMessage
from .config import SETTINGS

def send_email(to_email: str, subject: str, html_body: str):
    """Send HTML email when SMTP is enabled; otherwise no-op (used in tests)."""
    if not (getattr(SETTINGS, "smtp_enabled", False) and SETTINGS.smtp_host and SETTINGS.smtp_user and SETTINGS.smtp_pass):
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SETTINGS.smtp_from_name} <{SETTINGS.smtp_from_email or SETTINGS.smtp_user}>"
    msg["To"] = to_email
    msg.set_content("HTML email. Please view in an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(SETTINGS.smtp_host, SETTINGS.smtp_port) as s:
        s.starttls()
        s.login(SETTINGS.smtp_user, SETTINGS.smtp_pass)
        s.send_message(msg)
