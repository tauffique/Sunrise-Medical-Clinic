"""Request protection: rate limiting, CSRF tokens and security headers."""
import secrets
import threading
import time
from collections import defaultdict, deque

from flask import current_app, request, session

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self' https://*.twilio.com wss://*.twilio.com; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
)


class RateLimiter:
    """Sliding-window limiter kept in memory (one process). Use Redis when running several workers."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key, limit, window):
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


def rate_allowed(bucket):
    """True if the caller (by IP) is under the limit configured as RATE_<BUCKET>."""
    limit, window = current_app.config[f"RATE_{bucket.upper()}"]
    return current_app.extensions["limiter"].allow(f"{bucket}:{request.remote_addr}", limit, window)


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def csrf_valid(submitted):
    expected = session.get("_csrf", "")
    return bool(expected) and bool(submitted) and secrets.compare_digest(submitted, expected)


def apply_security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if current_app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response