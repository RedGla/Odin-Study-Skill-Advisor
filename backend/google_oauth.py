"""Google authorization-code login with PKCE, nonce and browser-bound state."""
import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

import auth
import auth_security as security
import models

COOKIE = "google_oauth_state"


def configured():
    return all(os.getenv(key) for key in ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REDIRECT_URI"))


def begin(db, request, *, link_user=None):
    if not configured():
        raise HTTPException(503, "Google sign-in is not configured yet.")
    security.throttle(db, f"oauth:{request.client.host}", maximum=20)
    verifier = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(32)
    binding = secrets.token_urlsafe(32)
    state = security.issue_token(db, "google", payload={
        "verifier": verifier, "nonce": nonce, "binding": security.digest(binding),
        "link_user_id": str(link_user.id) if link_user else None,
        "session_hash": security.digest(request.cookies.get("session_token", "")) if link_user else None,
    }, minutes=10)
    db.commit()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({"client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
                       "redirect_uri": os.environ["GOOGLE_OAUTH_REDIRECT_URI"],
                       "response_type": "code", "scope": "openid email profile",
                       "state": state, "nonce": nonce, "code_challenge": challenge,
                       "code_challenge_method": "S256", "prompt": "select_account"})
    return "https://accounts.google.com/o/oauth2/v2/auth?" + query, binding


def complete(db, request, code, state, registration_enabled):
    row = security.consume_token(db, state, "google")
    payload = row.payload
    binding = request.cookies.get(COOKIE, "")
    if not binding or not secrets.compare_digest(payload["binding"], security.digest(binding)):
        db.rollback()
        raise HTTPException(400, "Google sign-in expired. Please start again.")
    # Consume before any provider I/O, so a code/state cannot be replayed.
    db.commit()
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
                "redirect_uri": os.environ["GOOGLE_OAUTH_REDIRECT_URI"],
                "grant_type": "authorization_code", "code_verifier": payload["verifier"]})
            response.raise_for_status()
        claims = id_token.verify_oauth2_token(response.json()["id_token"], GoogleRequest(), os.environ["GOOGLE_OAUTH_CLIENT_ID"])
        if claims.get("nonce") != payload["nonce"] or claims.get("email_verified") is not True or not claims.get("sub"):
            raise ValueError("Invalid Google identity")
        email = auth.normalize_email(claims["email"])
    except Exception:
        # Never include provider responses, codes or tokens in errors/logs.
        raise HTTPException(400, "Google sign-in could not be verified. Please try again.") from None

    user = db.query(models.User).filter_by(google_subject=claims["sub"]).first()
    if payload.get("link_user_id"):
        current = auth.get_session_user(db, request.cookies.get("session_token", ""))
        if (not current or str(current.id) != payload["link_user_id"]
                or security.digest(request.cookies.get("session_token", "")) != payload["session_hash"]):
            raise HTTPException(401, "Sign in again before linking Google.")
        if email != auth.normalize_email(current.email) or (user and user.id != current.id):
            raise HTTPException(400, "Choose the Google account matching your account email.")
        if current.google_subject and current.google_subject != claims["sub"]:
            raise HTTPException(400, "A different Google account is already linked.")
        user = current
        user.google_subject = claims["sub"]
        user.email_verified = True
    elif not user:
        if auth.get_user_by_email(db, email):
            raise HTTPException(400, "Sign in with your password, then link Google in account settings.")
        if not registration_enabled:
            raise HTTPException(403, "New registrations are currently paused.")
        user = models.User(email=email, hashed_password=auth.hash_password(secrets.token_urlsafe(48)),
                           google_subject=claims["sub"], email_verified=True, role="user")
        db.add(user)
    if user.is_active is False:
        raise HTTPException(403, "This account is unavailable. Contact the administrator.")
    db.commit()
    db.refresh(user)
    return user
