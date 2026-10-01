from passlib.context import CryptContext
from sqlalchemy.orm import Session
from models import User
from sqlalchemy import func
import hashlib, secrets
from datetime import datetime, timedelta, timezone

pw_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pw_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pw_context.verify(plain_password, hashed_password)

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(func.lower(func.trim(User.email)) == normalize_email(email)).first()

SESSION_TTL = timedelta(hours=12)

RESERVED_EMAIL_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
    "invalid",
    "localhost",
    "test",
}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_reserved_email_domain(email: str) -> bool:
    """Reject documentation and local-only domains that cannot receive email."""
    domain = email.rsplit("@", 1)[-1]
    return any(
        domain == reserved or domain.endswith(f".{reserved}")
        for reserved in RESERVED_EMAIL_DOMAINS
    )


def create_session(db: Session, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.add(__import__('models').Session(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user_id,
                                        created_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) + SESSION_TTL))
    db.commit()
    return token
def get_session_user(db: Session, token: str):
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.query(__import__('models').Session).filter_by(token_hash=digest).first()
    expires_at = row.expires_at.replace(tzinfo=timezone.utc) if row and row.expires_at.tzinfo is None else (row.expires_at if row else None)
    if not row or expires_at <= datetime.now(timezone.utc):
        if row: db.delete(row); db.commit()
        return None
    return db.query(User).filter_by(id=row.user_id, is_active=True).first()
def revoke_session(db: Session, token: str) -> None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    db.query(__import__('models').Session).filter_by(token_hash=digest).delete()
    db.commit()
