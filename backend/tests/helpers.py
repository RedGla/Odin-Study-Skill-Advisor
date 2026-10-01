import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import auth
import models
from database import SessionLocal


def create_user(db: Session, *, role: str = "user") -> models.User:
    user = models.User(
        email=f"test-{uuid.uuid4().hex}@example.com",
        hashed_password=auth.hash_password("password123"),
        role=role,
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_client(client: TestClient, user: models.User) -> TestClient:
    client.cookies.set("session_token", session_token(str(user.id)))
    client.headers["Origin"] = "http://localhost:5173"
    return client


def cleanup_user(user_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(models.Message).filter(
            models.Message.conversation_id.in_(
                db.query(models.Conversation.id).filter(models.Conversation.user_id == user_id)
            )
        ).delete(synchronize_session=False)
        db.query(models.Conversation).filter(models.Conversation.user_id == user_id).delete()
        db.query(models.UsageCounter).filter(models.UsageCounter.user_id == user_id).delete()
        db.query(models.User).filter(models.User.id == user_id).delete()
        db.commit()
    finally:
        db.close()


def session_token(user_id):
    with SessionLocal() as db:
        return auth.create_session(db, str(user_id))
