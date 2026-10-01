"""Single-use credentials, shared throttles and TLS-only transactional email."""
import hashlib
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert

import models


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def throttle(db, key, maximum=5, seconds=300):
    """Atomic across processes. Keys are hashed; expired buckets are pruned."""
    current = now()
    db.query(models.AuthRateLimit).filter(models.AuthRateLimit.expires_at <= current).delete()
    statement = insert(models.AuthRateLimit).values(
        key=digest(key), attempts=1, expires_at=current + timedelta(seconds=seconds))
    expired = models.AuthRateLimit.expires_at <= current
    statement = statement.on_conflict_do_update(
        index_elements=[models.AuthRateLimit.key],
        set_={"attempts": case((expired, 1), else_=models.AuthRateLimit.attempts + 1),
              "expires_at": case((expired, current + timedelta(seconds=seconds)), else_=models.AuthRateLimit.expires_at)}
    ).returning(models.AuthRateLimit.attempts)
    attempts = db.execute(statement).scalar_one()
    db.commit()
    if attempts > maximum:
        raise HTTPException(429, "Too many attempts. Please try again later.", headers={"Retry-After": str(seconds)})


def issue_token(db, purpose, user_id=None, payload=None, minutes=30):
    db.query(models.AuthToken).filter(models.AuthToken.expires_at <= now()).delete()
    token = secrets.token_urlsafe(32)
    db.add(models.AuthToken(token_hash=digest(token), purpose=purpose, user_id=user_id,
                            payload=payload or {}, expires_at=now() + timedelta(minutes=minutes)))
    db.flush()
    return token


def consume_token(db, token, purpose):
    row = db.query(models.AuthToken).filter_by(token_hash=digest(token), purpose=purpose).with_for_update().first()
    if not row or row.expires_at <= now():
        raise HTTPException(400, "This link has expired or has already been used. Request a new one.")
    db.delete(row)
    db.flush()
    return row


def validate_password(password):
    if not 15 <= len(password) <= 128:
        raise HTTPException(400, "Use a password between 15 and 128 characters.")
    if password.casefold() in {"password123456789", "123456789012345", "qwertyuiopasdfgh", "letmeinletmein123"}:
        raise HTTPException(400, "Choose a less common password or a longer passphrase.")


def mail_configured():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send_account_email(email, token, purpose):
    if not mail_configured():
        raise HTTPException(503, "Account email delivery is not configured. Please contact the administrator.")
    # Fragments stay out of access logs and Referer headers.
    link = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/") + "/login#" + urlencode({"action": purpose, "token": token})
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = email
    message["Subject"] = "Verify your Odin email" if purpose == "verify" else "Reset your Odin password"
    message.set_content(f"Open this link to {'verify your email' if purpose == 'verify' else 'reset your password'}:\n\n{link}\n\nThis link expires in 30 minutes and can be used once. If you did not request it, ignore this email.")
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        if port == 465:
            connection = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=10, context=ssl.create_default_context())
        else:
            connection = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=10)
        with connection as smtp:
            if port != 465:
                smtp.starttls(context=ssl.create_default_context())
            if os.getenv("SMTP_USERNAME"):
                smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(503, "Could not deliver account email. Please try again later.") from None
