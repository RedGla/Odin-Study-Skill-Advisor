from fastapi import FastAPI, Depends, HTTPException, Response, Request, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from urllib.parse import urlparse
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, cast, Literal
from datetime import datetime
import os
from dotenv import load_dotenv

from database import SessionLocal, DatabaseOperationalError
import models
import auth
import auth_security as security
import google_oauth
from llm_service import generate_llm_response, get_chat_completion, estimate_cost, conservative_token_estimate, MAX_COMPLETION_TOKENS, _select_grounding
import usage_service
import limits
import docs_service
import personas_service
import telemetry_service
import config_service
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("advisor_console")

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Configuration based on environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
IS_PROD = os.getenv("ENVIRONMENT", "development") == "production"

# Cookie configuration - can be overridden via env vars
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true" if IS_PROD else "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "none" if IS_PROD else "lax")
SESSION_COOKIE = "session_token"
if IS_PROD and (not COOKIE_SECURE or not FRONTEND_URL.startswith("https://")):
    raise RuntimeError("Production requires HTTPS and secure session cookies")
if COOKIE_SAMESITE not in {"lax", "strict", "none"} or (COOKIE_SAMESITE == "none" and not COOKIE_SECURE):
    raise RuntimeError("Use a valid SameSite policy; SameSite=None requires secure cookies")


class OAuthAccessLogFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn access-log arguments contain the full callback query string.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            address, method, path, version, code = record.args
            if isinstance(path, str) and path.startswith("/auth/google/callback?"):
                record.args = (address, method, path.split("?", 1)[0], version, code)
        return True


logging.getLogger("uvicorn.access").addFilter(OAuthAccessLogFilter())

# CORS configuration
ALLOWED_ORIGINS = [FRONTEND_URL]
if ENVIRONMENT == "development":
    # Allow additional local dev URLs in development
    ALLOWED_ORIGINS.extend(["http://localhost:3000", "http://127.0.0.1:5173"])

class OriginProtectionMiddleware(BaseHTTPMiddleware):
    """Reject cross-site mutations, including unauthenticated login CSRF."""
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            # Origin, when present, is authoritative.  Referer is only a
            # browser fallback for requests that do not send Origin.
            valid_origin = origin in ALLOWED_ORIGINS if origin else False
            valid_referer = False
            if not origin and referer:
                parsed = urlparse(referer)
                valid_referer = f"{parsed.scheme}://{parsed.netloc}" in ALLOWED_ORIGINS
            if not (valid_origin if origin is not None else valid_referer):
                return JSONResponse(status_code=403, content={"detail": "CSRF origin validation failed"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if IS_PROD:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

app.add_middleware(OriginProtectionMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_or_503():
    """Like get_db, but converts SQLAlchemy OperationalErrors (connection drops,
    DB restarts, Supabase blips) into HTTP 503 with a user-friendly message
    instead of a raw 500 stack trace."""
    db = SessionLocal()
    try:
        yield db
    except DatabaseOperationalError:
        logger.exception("db_connection_error")
        raise HTTPException(
            status_code=503,
            detail="The database is temporarily unavailable. Please try again in a moment.",
        )
    finally:
        db.close()

# Auth Schemas
class EmailSchema(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value):
        return auth.normalize_email(value) if isinstance(value, str) else value

class RegisterSchema(EmailSchema):
    password: str = Field(max_length=128)

class LoginSchema(EmailSchema):
    password: str = Field(max_length=128)

class ChangePasswordSchema(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

class TokenSchema(BaseModel):
    token: str = Field(min_length=20, max_length=200)

class ResetSchema(TokenSchema):
    password: str = Field(max_length=128)

# Chat Schemas
class CreateConversationSchema(BaseModel):
    title: Optional[str] = "New Conversation"
    persona_id: Optional[str] = Field(default=None, min_length=1, max_length=128)

class RenameConversationSchema(BaseModel):
    title: str

class SendMessageSchema(BaseModel):
    content: str = Field(min_length=1, max_length=16000)

class TemporaryMessageSchema(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=16000)

class TemporaryChatSchema(BaseModel):
    messages: list[TemporaryMessageSchema] = Field(min_length=1, max_length=50)

    @field_validator("messages")
    @classmethod
    def bounded_history(cls, messages):
        if sum(len(message.content) for message in messages) > 64000:
            raise ValueError("Temporary chat context is too long. Start a new temporary chat.")
        if messages[-1].role != "user":
            raise ValueError("The final message must be from the user")
        return messages

class AdminConfigSchema(BaseModel):
    daily_message_cap: int = Field(ge=1, le=100000)
    daily_token_cap: int = Field(ge=1, le=100000000)
    rate_limit_requests: int = Field(ge=1, le=1000)
    rate_limit_window_seconds: int = Field(ge=1, le=86400)
    registration_enabled: bool = True
    chat_enabled: bool = True

class AdminUserSchema(BaseModel):
    is_active: bool

# Serializers
def serialize_conversation(c: models.Conversation) -> dict:
    return {"id": c.id, "user_id": c.user_id, "title": c.title, "persona_id": c.persona_id or "odin", "created_at": c.created_at, "updated_at": c.updated_at}

def serialize_message(m: models.Message) -> dict:
    """Serialize a Message object. Ensures 'sender' is always lowercase ('user' or 'assistant')."""
    sender = cast(Optional[str], m.sender)
    created_at = cast(Optional[datetime], m.created_at)
    sender_role = "user" if sender and sender.lower() == "user" else "assistant"
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "sender": sender_role,
        "content": m.content,
        "status": m.status,
        "prompt_tokens": m.prompt_tokens,
        "completion_tokens": m.completion_tokens,
        "est_cost": m.est_cost,
        "created_at": created_at.isoformat() if created_at else None
    }

# Helper to get active user from session cookie
def get_current_user(request: Request, db: Session = Depends(get_db_or_503)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        user = auth.get_session_user(db, token)
    else:
        user = None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

# Role Guard Dependency
def require_admin(current_user: models.User = Depends(get_current_user)):
    if cast(str, current_user.role) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

@app.get("/health")
@app.head("/health")
def health_check():
    return {"status": "ok"}

def set_session(response, db, user, request):
    old_token = request.cookies.get(SESSION_COOKIE)
    if old_token:
        auth.revoke_session(db, old_token)
    token = auth.create_session(db, str(user.id))
    response.set_cookie(SESSION_COOKIE, token, httponly=True,
                        samesite=COOKIE_SAMESITE, secure=COOKIE_SECURE,
                        max_age=int(auth.SESSION_TTL.total_seconds()))


def auth_throttle(db, request, email=None):
    security.throttle(db, f"auth-ip:{request.client.host}", maximum=30)
    if email:
        security.throttle(db, f"auth-email:{auth.normalize_email(email)}")


@app.get("/auth/options")
def auth_options():
    return {"google_enabled": google_oauth.configured(), "email_enabled": security.mail_configured()}


@app.post("/auth/register")
def register(data: RegisterSchema, request: Request, db: Session = Depends(get_db_or_503)):
    auth_throttle(db, request, data.email)
    if not config_service.get(db)["registration_enabled"]:
        raise HTTPException(403, "New registrations are currently paused.")
    email = auth.normalize_email(data.email)
    if auth.is_reserved_email_domain(email):
        raise HTTPException(400, "Use a real email address; example and test domains are not allowed.")
    security.validate_password(data.password)
    # Hash even for duplicates to avoid an obvious timing difference.
    hashed = auth.hash_password(data.password)
    user = auth.get_user_by_email(db, email)
    if not user:
        user = models.User(email=email, hashed_password=hashed, role="user", email_verified=False)
        db.add(user)
        try:
            db.flush()
            db.commit()
        except IntegrityError:
            db.rollback()
    return {"message": "You can now sign in with your email and password. If you already have an account, use your existing password."}


_DUMMY_HASH = auth.hash_password("timing-only-not-an-account-password")

@app.post("/auth/login")
def login(data: LoginSchema, request: Request, response: Response, db: Session = Depends(get_db_or_503)):
    auth_throttle(db, request, data.email)
    user = auth.get_user_by_email(db, data.email)
    valid = auth.verify_password(data.password, user.hashed_password if user else _DUMMY_HASH)
    if not user or not valid or not user.is_active:
        raise HTTPException(400, "Invalid email or password.")
    set_session(response, db, user, request)
    return {"message": "Logged in successfully", "email": user.email, "role": user.role}


@app.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db_or_503)):
    if request.cookies.get(SESSION_COOKIE):
        auth.revoke_session(db, request.cookies[SESSION_COOKIE])
    response.delete_cookie(SESSION_COOKIE, secure=COOKIE_SECURE, httponly=True, samesite=COOKIE_SAMESITE)
    return {"message": "Logged out successfully"}


@app.get("/auth/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role,
            "google_linked": bool(current_user.google_subject)}



@app.get("/usage/me")
def get_my_usage(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db_or_503)):
    """Return only this user's completed usage for the current UTC day."""
    today = usage_service._today_str()
    counter = db.query(models.UsageCounter).filter_by(user_id=current_user.id, date_str=today).first()
    return {
        "date": today,
        "messages_today": int(counter.messages_today or 0) if counter else 0,
        "daily_message_cap": config_service.get(db)["daily_message_cap"],
    }

@app.post("/auth/change-password")
def change_password(data: ChangePasswordSchema, request: Request, response: Response,
                    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db_or_503)):
    auth_throttle(db, request, current_user.email)
    if not auth.verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    security.validate_password(data.new_password)
    current_user.hashed_password = auth.hash_password(data.new_password)
    db.query(models.Session).filter_by(user_id=current_user.id).delete()
    db.query(models.AuthToken).filter_by(user_id=current_user.id).delete()
    db.commit()
    set_session(response, db, current_user, request)
    return {"message": "Password updated; other sessions have been signed out."}


@app.post("/auth/verify-email")
def verify_email(data: TokenSchema, request: Request, db: Session = Depends(get_db_or_503)):
    auth_throttle(db, request)
    token = security.consume_token(db, data.token, "verify")
    user = db.get(models.User, token.user_id)
    user.email_verified = True
    db.query(models.AuthToken).filter_by(user_id=user.id, purpose="verify").delete()
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@app.post("/auth/resend-verification")
@app.post("/auth/forgot-password")
def request_account_email(data: EmailSchema, request: Request, db: Session = Depends(get_db_or_503)):
    auth_throttle(db, request, data.email)
    if not security.mail_configured():
        raise HTTPException(503, "Account email delivery is not configured. Please contact the administrator.")
    purpose = "reset" if request.url.path.endswith("forgot-password") else "verify"
    user = auth.get_user_by_email(db, data.email)
    if user and user.is_active and (purpose == "reset" or not user.email_verified):
        token = security.issue_token(db, purpose, str(user.id))
        security.send_account_email(user.email, token, purpose)
        db.commit()
    return {"message": "If this address is eligible, an email has been sent. Check your inbox and spam folder."}


@app.post("/auth/reset-password")
def reset_password(data: ResetSchema, request: Request, db: Session = Depends(get_db_or_503)):
    auth_throttle(db, request)
    security.validate_password(data.password)
    token = security.consume_token(db, data.token, "reset")
    user = db.get(models.User, token.user_id)
    if not user.is_active:
        raise HTTPException(400, "This account is unavailable.")
    user.hashed_password = auth.hash_password(data.password)
    user.email_verified = True
    db.query(models.Session).filter_by(user_id=user.id).delete()
    db.query(models.AuthToken).filter_by(user_id=user.id).delete()
    db.commit()
    return {"message": "Password reset. Sign in with your new password."}


@app.post("/auth/google/start")
def google_start(request: Request, link: bool = False, db: Session = Depends(get_db_or_503)):
    user = get_current_user(request, db) if link else None
    url, binding = google_oauth.begin(db, request, link_user=user)
    response = JSONResponse({"url": url})
    response.set_cookie(google_oauth.COOKIE, binding, httponly=True, secure=COOKIE_SECURE,
                        samesite="none" if COOKIE_SECURE else "lax", max_age=600, path="/auth/google")
    return response


@app.get("/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db_or_503)):
    try:
        user = google_oauth.complete(db, request, code, state, config_service.get(db)["registration_enabled"])
        response = RedirectResponse(FRONTEND_URL.rstrip("/") + ("/admin" if user.role == "admin" else "/"), status_code=303)
        set_session(response, db, user, request)
    except (HTTPException, IntegrityError):
        db.rollback()
        response = RedirectResponse(FRONTEND_URL.rstrip("/") + "/login?google_error=1", status_code=303)
    response.delete_cookie(google_oauth.COOKIE, path="/auth/google", secure=COOKIE_SECURE,
                           httponly=True, samesite="none" if COOKIE_SECURE else "lax")
    return response


@app.get("/admin/usage")
def get_admin_usage(
    db: Session = Depends(get_db_or_503),
    _: models.User = Depends(require_admin),
):
    today = usage_service._today_str()
    rows = (
        db.query(
            models.User,
            func.coalesce(func.sum(case((models.UsageCounter.date_str == today, models.UsageCounter.messages_today), else_=0)), 0).label("messages_today"),
            func.coalesce(func.sum(case((models.UsageCounter.date_str == today, models.UsageCounter.tokens_today), else_=0)), 0).label("tokens_today"),
            func.coalesce(func.sum(case((models.UsageCounter.date_str == today, models.UsageCounter.est_spend_today), else_=0.0)), 0.0).label("est_spend_today"),
            func.coalesce(func.sum(models.UsageCounter.messages_today), 0).label("messages_all_time"),
            func.coalesce(func.sum(models.UsageCounter.tokens_today), 0).label("tokens_all_time"),
            func.coalesce(func.sum(models.UsageCounter.est_spend_today), 0.0).label("est_spend_all_time"),
            func.max(models.UsageCounter.date_str).label("last_usage_date"),
        )
        .outerjoin(models.UsageCounter, models.UsageCounter.user_id == models.User.id)
        .group_by(models.User.id)
        .order_by(models.User.created_at.desc())
        .all()
    )

    return [
        {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "email_verified": user.email_verified,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "messages_today": int(messages_today or 0),
            "tokens_today": int(tokens_today or 0),
            "est_spend_today": float(spend_today or 0.0),
            "messages_all_time": int(messages_all_time or 0),
            "tokens_all_time": int(tokens_all_time or 0),
            "est_spend_all_time": float(spend_all_time or 0.0),
            "last_usage_date": last_usage_date,
        }
        for user, messages_today, tokens_today, spend_today, messages_all_time, tokens_all_time, spend_all_time, last_usage_date in rows
    ]

@app.get("/admin/conversations")
def get_admin_conversations(
    db: Session = Depends(get_db_or_503),
    _: models.User = Depends(require_admin),
):
    conversations = (
        db.query(models.Conversation, models.User.email)
        .join(models.User, models.User.id == models.Conversation.user_id)
        .order_by(models.Conversation.created_at.desc())
        .all()
    )
    return [
        {
            "id": conversation.id,
            "user_email": email,
            "title": conversation.title,
            "message_count": len(conversation.messages),
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        }
        for conversation, email in conversations
    ]

@app.get("/admin/config")
def get_admin_config(db: Session = Depends(get_db_or_503), _: models.User = Depends(require_admin)):
    return config_service.get(db)

@app.put("/admin/config")
def update_admin_config(data: AdminConfigSchema, db: Session = Depends(get_db_or_503), _: models.User = Depends(require_admin)):
    values = data.model_dump()
    config_service.update(db, values, actor_id=str(_.id))
    return config_service.get(db)

@app.get("/admin/conversations/{conversation_id}/messages")
def get_admin_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db_or_503),
    _: models.User = Depends(require_admin),
):
    conversation = db.query(models.Conversation).filter_by(id=conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [serialize_message(message) for message in conversation.messages]

@app.get("/admin/events")
def get_admin_events(
    event: Optional[str] = Query(default=None),
    event_status: Optional[str] = Query(default=None, alias="status"),
    user_id: Optional[str] = Query(default=None),
    conversation_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db_or_503),
    _: models.User = Depends(require_admin),
):
    query = db.query(models.TelemetryEvent, models.User.email).outerjoin(
        models.User, models.User.id == models.TelemetryEvent.user_id
    )
    if event:
        query = query.filter(models.TelemetryEvent.event == event)
    if event_status:
        query = query.filter(models.TelemetryEvent.status == event_status)
    if user_id:
        query = query.filter(models.TelemetryEvent.user_id == user_id)
    if conversation_id:
        query = query.filter(models.TelemetryEvent.conversation_id == conversation_id)
    rows = query.order_by(models.TelemetryEvent.created_at.desc(), models.TelemetryEvent.id.desc()).limit(limit).all()
    return [
        {
            "id": event_row.id,
            "created_at": event_row.created_at.isoformat() if event_row.created_at else None,
            "event": event_row.event,
            "status": event_row.status,
            "user_id": event_row.user_id,
            "user_email": email,
            "conversation_id": event_row.conversation_id,
            "prompt_tokens": event_row.prompt_tokens,
            "completion_tokens": event_row.completion_tokens,
            "estimated_cost": event_row.estimated_cost,
            "reason": event_row.reason,
        }
        for event_row, email in rows
    ]

@app.patch("/admin/users/{user_id}")
def update_admin_user(user_id: str, data: AdminUserSchema, db: Session = Depends(get_db_or_503),
                      admin: models.User = Depends(require_admin)):
    user = db.query(models.User).filter_by(id=user_id).with_for_update().first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.role == "admin":
        raise HTTPException(400, "Administrator accounts cannot be suspended from this dashboard.")
    user.is_active = data.is_active
    if not data.is_active:
        db.query(models.Session).filter_by(user_id=user.id).delete()
        db.query(models.AuthToken).filter_by(user_id=user.id).delete()
    telemetry_service.record(db, "admin_user_updated", user_id=admin.id, status="completed",
                             reason=f"target={user.id}; active={data.is_active}")
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@app.post("/admin/users/{user_id}/revoke-sessions")
def revoke_user_sessions(user_id: str, db: Session = Depends(get_db_or_503),
                         admin: models.User = Depends(require_admin)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    count = db.query(models.Session).filter_by(user_id=user_id).delete()
    telemetry_service.record(db, "admin_sessions_revoked", user_id=admin.id, status="completed", reason=f"target={user_id}")
    db.commit()
    return {"revoked": count}


@app.get("/admin/status")
def admin_status(db: Session = Depends(get_db_or_503), _: models.User = Depends(require_admin)):
    return {"database": "connected", "active_sessions": db.query(models.Session).filter(models.Session.expires_at > security.now()).count(),
            "google_configured": google_oauth.configured(), "email_configured": security.mail_configured(),
            "secure_cookies": COOKIE_SECURE, "email_verification_required": False}


def require_chat_user(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db_or_503)):
    if current_user.role == "admin":
        raise HTTPException(403, "Administrators use the dashboard; chat access is disabled.")
    return current_user


def check_chat_enabled(db):
    if not config_service.get(db)["chat_enabled"]:
        raise HTTPException(503, "Chat is paused by the administrator. Please try again later.")


# Chat Endpoints
@app.get("/personas")
async def list_personas(current_user: models.User = Depends(require_chat_user)):
    return [{key: p[key] for key in ("persona_id", "display_name", "is_default")}
            for p in await personas_service.get_personas()]

@app.post("/conversations")
async def create_conversation(
    data: CreateConversationSchema,
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(require_chat_user)
):
    check_chat_enabled(db)
    try:
        persona = (await personas_service.get_persona(data.persona_id)
                   if data.persona_id is not None else await personas_service.get_default_persona())
    except personas_service.PersonasServiceError:
        raise HTTPException(503, "No enabled personas are available. Please contact the administrator.") from None
    if persona is None:
        raise HTTPException(400, "Unknown or disabled persona")
    conv = models.Conversation(user_id=current_user.id, title=data.title, persona_id=persona["persona_id"])
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return serialize_conversation(conv)

@app.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(require_chat_user)
):
    convs = db.query(models.Conversation).filter(models.Conversation.user_id == current_user.id).all()
    return [serialize_conversation(c) for c in convs]

@app.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    data: RenameConversationSchema,
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(require_chat_user)
):
    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Conversation title cannot be empty")

    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    setattr(conv, "title", title)
    db.commit()
    db.refresh(conv)
    return serialize_conversation(conv)

@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(require_chat_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted successfully"}

@app.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(require_chat_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [serialize_message(m) for m in conv.messages]

def prepare_reserved_turn(db: Session, conv: models.Conversation, user_id: str, content: str):
    """Commit admission and both initial message rows together, or roll back all."""
    try:
        runtime_config = config_service.get(db)
        reservation = limits.reserve_daily_quota(db, user_id,
                                                 daily_message_cap=runtime_config["daily_message_cap"],
                                                 daily_token_cap=runtime_config["daily_token_cap"])
        history = [
            {"role": "user" if str(m.sender).lower() == "user" else "assistant",
             "content": m.content}
            for m in conv.messages
            if m.content and m.status == models.MessageStatus.COMPLETED.value
        ]
        history.append({"role": "user", "content": content})
        max_history = int(os.getenv("MAX_HISTORY_MESSAGES", "50"))
        if len(history) > max_history:
            # Stored/displayed history remains complete. The model receives a
            # bounded working context with older turns represented compactly.
            recent_count = max_history - 1
            older = history[:-recent_count]
            summary_lines = [f"{item['role']}: {item['content']}" for item in older]
            summary = "Earlier conversation summary:\n" + "\n".join(summary_lines)
            # Keep the summary itself bounded by characters (~4 chars/token).
            summary = summary[: max(1000, int(os.getenv("MAX_HISTORY_SUMMARY_CHARS", "6000")))]
            history = [{"role": "assistant", "content": summary}, *history[-recent_count:]]

        user_msg = models.Message(conversation_id=conv.id, sender="user", content=content,
                                  status=models.MessageStatus.COMPLETED.value)
        db.add(user_msg)
        db.flush()
        assistant_msg = models.Message(conversation_id=conv.id, sender="assistant", content="",
                                       status=models.MessageStatus.PENDING.value)
        db.add(assistant_msg)
        if conv.title == "New Conversation":
            conv.title = content.strip().replace("\n", " ")[:60] or "New Conversation"
        db.flush()
        assistant_id = str(assistant_msg.id)
        db.commit()
        return reservation, assistant_id, history
    except BaseException:
        db.rollback()
        raise


def finish_reserved_turn(db: Session, reservation: usage_service.QuotaReservation,
                         assistant_id: str, *, result: dict | None = None,
                         release: bool = False,
                         token_reservation: usage_service.TokenReservation | None = None) -> dict:
    """Atomically reconcile/release quota and transition a pending assistant row.

    Locking the pending row makes retries of this finalization a no-op after
    the first committed transition. Provider/DB uncertainty retains the slot.
    """
    try:
        assistant = (db.query(models.Message).filter_by(id=assistant_id)
                     .populate_existing().with_for_update().one())
        if assistant.status == models.MessageStatus.PENDING.value:
            if result is not None:
                cost = estimate_cost(result["prompt_tokens"], result["completion_tokens"])
                usage_service.reconcile_reservation(
                    db, reservation, prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"], est_cost=cost,
                    token_reservation=token_reservation,
                    daily_cap=config_service.get(db)["daily_token_cap"],
                )
                assistant.content = result["content"]
                assistant.status = models.MessageStatus.COMPLETED.value
                assistant.prompt_tokens = result["prompt_tokens"]
                assistant.completion_tokens = result["completion_tokens"]
                assistant.est_cost = cost
            else:
                if release:
                    usage_service.release_reservation(db, reservation)
                    if token_reservation is not None:
                        usage_service.release_token_budget(db, reservation, token_reservation)
                assistant.content = "Sorry, I couldn't reach the advisor model right now. Please try again in a moment."
                assistant.status = models.MessageStatus.ERROR.value
        # Serialize before commit so no post-commit refresh opens a new transaction.
        response = serialize_message(assistant)
        db.commit()
        return response
    except BaseException:
        db.rollback()
        raise


@app.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: str,
    data: SendMessageSchema,
    db: Session = Depends(get_db_or_503),
    current_user: models.User = Depends(require_chat_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    check_chat_enabled(db)
    persona = await personas_service.get_persona(conv.persona_id or "odin", include_disabled=True)
    if persona is None:
        raise HTTPException(503, "This conversation persona is unavailable. Please try again later.")
    user_id = cast(str, current_user.id)
    runtime_config = config_service.get(db)

    # Rate rejection must not create a counter or reserve a daily message slot.
    try:
        limits.check_rate_limit(user_id, max_requests=runtime_config["rate_limit_requests"],
                                window_seconds=runtime_config["rate_limit_window_seconds"])
    except limits.RateLimitedError as exc:
        logger.warning("request_blocked reason=rate user_id=%s", user_id)
        telemetry_service.emit("request_blocked", user_id=user_id, conversation_id=conversation_id, status="blocked", reason="rate")
        retry_after = int(exc.retry_after_seconds)
        raise HTTPException(status_code=429, detail={
            "reason": "rate",
            "message": f"You're sending messages too quickly. Try again in {retry_after}s.",
            "retry_after_seconds": retry_after,
        })

    try:
        # All lock-waiting DB work runs off the event loop; no lock spans the LLM await.
        reservation, assistant_id, history = await run_in_threadpool(
            prepare_reserved_turn, db, conv, user_id, data.content,
        )
    except limits.CapExceededError:
        logger.warning("request_blocked reason=cap user_id=%s", user_id)
        telemetry_service.emit("request_blocked", user_id=user_id, conversation_id=conversation_id, status="blocked", reason="cap")
        raise HTTPException(status_code=429, detail={
            "reason": "cap",
            "message": "You've reached today's usage limit. Please try again tomorrow.",
        })
    logger.info("message_sent conversation_id=%s user_id=%s", conversation_id, user_id)
    telemetry_service.emit("message_sent", user_id=user_id, conversation_id=conversation_id,
                           status="accepted", user_input=data.content)

    token_reservation = None
    try:
        # Reserve a worst-case prompt envelope (including up to two 400-word
        # grounding chunks) before the provider call. This is deliberately
        # conservative so actual provider tokenization cannot exceed the cap.
        # Fetch the same cached context used by generation so the reservation
        # reflects the actual prompt envelope rather than a guessed constant.
        context = await docs_service.get_advisor_context(persona=persona, user_id=user_id, conversation_id=conversation_id)
        grounding = _select_grounding(context["grounding_document"], history[-1]["content"] if history else "")
        system_content = f"{context['system_prompt']}\n\n" + (f"Relevant grounding context:\n{grounding}" if grounding else "")
        prompt_estimate = conservative_token_estimate([{"role": "system", "content": system_content}, *history])
        try:
            token_reservation = await run_in_threadpool(
                usage_service.reserve_token_budget, db, reservation,
                prompt_tokens=prompt_estimate,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                daily_cap=runtime_config["daily_token_cap"],
            )
        except ValueError:
            await run_in_threadpool(finish_reserved_turn, db, reservation, assistant_id, release=True)
            telemetry_service.emit("request_blocked", user_id=user_id, conversation_id=conversation_id,
                                   status="blocked", reason="cap")
            raise HTTPException(status_code=429, detail={
                "reason": "token_cap",
                "message": "You've reached today's token limit. Please try again tomorrow.",
            })
        result = await generate_llm_response(history, token_reservation.completion_tokens,
                                             persona=persona, advisor_context=context)
    except DatabaseOperationalError:
        # Unknown outcome: keep the reservation; the DB dependency returns 503.
        raise
    except HTTPException:
        raise
    except Exception as exc:
        pre_provider_failure = isinstance(exc, docs_service.DocsServiceError)
        event = "doc_fetch_error" if pre_provider_failure else "provider_error"
        logger.exception("%s conversation_id=%s", event, conversation_id)
        telemetry_service.emit(event, user_id=user_id, conversation_id=conversation_id,
                               status="error", reason=str(exc)[:500])
        await run_in_threadpool(
            finish_reserved_turn, db, reservation, assistant_id, release=pre_provider_failure,
            token_reservation=token_reservation,
        )
        raise HTTPException(status_code=502, detail="LLM generation failed")

    # A persistence failure after a successful provider call must not release quota
    # or be mistaken for a provider failure. Rollback leaves a pending reservation.
    response = await run_in_threadpool(
        finish_reserved_turn, db, reservation, assistant_id, result=result,
        token_reservation=token_reservation,
    )
    logger.info(
        "llm_call_completed conversation_id=%s user_id=%s prompt_tokens=%s "
        "completion_tokens=%s est_cost=%s docs_fetch_ms=%s llm_call_ms=%s",
        conversation_id, user_id, result["prompt_tokens"], result["completion_tokens"],
        response["est_cost"], result.get("docs_fetch_ms", 0), result.get("llm_call_ms", 0),
    )
    telemetry_service.emit("llm_call_completed", user_id=user_id, conversation_id=conversation_id,
                           status="completed", user_input=data.content,
                           assistant_response=response["content"],
                           prompt_tokens=result["prompt_tokens"],
                           completion_tokens=result["completion_tokens"],
                           estimated_cost=response["est_cost"])
    return response


@app.post("/temporary-chat/messages")
async def temporary_chat(data: TemporaryChatSchema, db: Session = Depends(get_db_or_503),
                         user: models.User = Depends(require_chat_user)):
    """Persist only quota totals and content-free operational metadata."""
    check_chat_enabled(db)
    config = config_service.get(db)
    try:
        limits.check_rate_limit(str(user.id), max_requests=config["rate_limit_requests"],
                                window_seconds=config["rate_limit_window_seconds"])
    except limits.RateLimitedError as exc:
        raise HTTPException(429, {"reason": "rate", "message": "Too many messages. Please wait before trying again.",
                                  "retry_after_seconds": int(exc.retry_after_seconds)})
    history = [message.model_dump() for message in data.messages]
    try:
        context = await docs_service.get_advisor_context()
    except docs_service.DocsServiceError:
        raise HTTPException(503, "Advisor context is temporarily unavailable.") from None
    grounding = _select_grounding(context["grounding_document"], history[-1]["content"])
    system_content = f"{context['system_prompt']}\n\n" + (f"Relevant grounding context:\n{grounding}" if grounding else "")
    prompt = [{"role": "system", "content": system_content}, *history]

    def reserve():
        try:
            reservation = limits.reserve_daily_quota(db, str(user.id), daily_message_cap=config["daily_message_cap"],
                                                      daily_token_cap=config["daily_token_cap"])
            # The token reservation refreshes the same locked counter. Flush the
            # message increment first so populate_existing cannot discard it.
            db.flush()
            budget = usage_service.reserve_token_budget(db, reservation,
                prompt_tokens=conservative_token_estimate(prompt), max_completion_tokens=MAX_COMPLETION_TOKENS,
                daily_cap=config["daily_token_cap"])
            db.commit()
            return reservation, budget
        except BaseException:
            db.rollback()
            raise

    try:
        reservation, budget = await run_in_threadpool(reserve)
    except (limits.CapExceededError, ValueError):
        raise HTTPException(429, {"reason": "cap", "message": "You have reached today's usage limit."})
    try:
        result = await get_chat_completion(prompt, max_completion_tokens=budget.completion_tokens)
    except Exception:
        # Keep uncertain provider spend reserved. Never log exception text or content.
        logger.warning("temporary_chat_provider_failure user_id=%s", user.id)
        raise HTTPException(502, "The advisor service is temporarily unavailable.") from None

    def finalize():
        usage_service.reconcile_reservation(db, reservation, prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"], est_cost=estimate_cost(result["prompt_tokens"], result["completion_tokens"]),
            token_reservation=budget, daily_cap=config["daily_token_cap"])
        telemetry_service.record(db, "temporary_chat_completed", user_id=user.id, status="completed",
            prompt_tokens=result["prompt_tokens"], completion_tokens=result["completion_tokens"],
            estimated_cost=estimate_cost(result["prompt_tokens"], result["completion_tokens"]))
        db.commit()
    await run_in_threadpool(finalize)
    return {"content": result["content"]}
