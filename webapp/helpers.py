"""Shared request helpers for OpenGlaze route blueprints."""

from typing import Optional

from core.auth import get_simple_user


def get_current_user_id() -> Optional[str]:
    """User ID from the request's simple-auth Bearer token, or None."""
    simple = get_simple_user()
    return simple["user_id"] if simple else None
