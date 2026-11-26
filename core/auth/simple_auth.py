"""
Simple Auth: lightweight display-name sessions for studio features.
Tokens are random and held in memory, so they reset when the server restarts.
"""

import secrets
import time
import logging
from typing import Optional, Dict
from datetime import timedelta

logger = logging.getLogger(__name__)

# In-memory session store. For production, use SQLite or Redis.
_sessions: Dict[str, dict] = {}

TOKEN_LIFETIME_DAYS = 30


def generate_user_id() -> str:
    """Generate a unique user ID."""
    return f"u_{secrets.token_urlsafe(12)}"


def create_session(display_name: str) -> dict:
    """
    Create a simple auth session.

    Returns:
        {user_id, display_name, token}
    """
    user_id = generate_user_id()
    token = secrets.token_urlsafe(32)
    expires = time.time() + timedelta(days=TOKEN_LIFETIME_DAYS).total_seconds()

    _sessions[token] = {
        "user_id": user_id,
        "display_name": display_name,
        "expires": expires,
    }

    return {
        "user_id": user_id,
        "display_name": display_name,
        "token": token,
    }


def validate_session(token: str) -> Optional[dict]:
    """
    Validate a simple auth token.

    Returns:
        {user_id, display_name} or None if invalid/expired.
    """
    session = _sessions.get(token)
    if not session:
        return None
    if time.time() > session["expires"]:
        del _sessions[token]
        return None
    return {
        "user_id": session["user_id"],
        "display_name": session["display_name"],
    }


def cleanup_expired():
    """Remove expired sessions (call periodically)."""
    now = time.time()
    expired = [t for t, s in _sessions.items() if now > s["expires"]]
    for t in expired:
        del _sessions[t]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired simple auth sessions")


def get_simple_user() -> Optional[dict]:
    """Return {user_id, display_name} for the request's Bearer token, or None."""
    from flask import request

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    return validate_session(token) if token else None
