"""Shared per-IP rate limiter (in-memory). Routers import `limiter` for decorators;
main.py attaches it to app.state and registers the 429 handler."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(key_func=get_remote_address, enabled=settings.RATE_LIMIT_ENABLED)
