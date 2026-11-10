"""Owner-only authentication helpers, signed session cookies, and rate limiting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from collections import deque
from threading import Lock

from fastapi import Request

from sdlc_app.config import WorkbenchSettings

MIN_PASSWORD_LENGTH = 12
HTTP_SESSION_COOKIE = "sdlc_session"
HTTPS_SESSION_COOKIE = "__Host-sdlc_session"


def constant_time_equal(candidate: str, expected: str) -> bool:
    """Compare two secrets in constant time using SHA-256 pre-hashing."""
    if not candidate or not expected:
        return False
    left = hashlib.sha256(candidate.encode("utf-8")).digest()
    right = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(left, right)


def _derive_signing_key(settings: WorkbenchSettings) -> bytes:
    secret_src = settings.session_secret.strip()
    if secret_src:
        return hashlib.sha256(b"sdlc-session-hmac-v1:" + secret_src.encode("utf-8")).digest()
    return hashlib.sha256(
        b"sdlc-session-fallback-v1:" + settings.owner_password.encode("utf-8")
    ).digest()


def create_session_token(settings: WorkbenchSettings, *, now: int | None = None) -> str:
    """Mint an HMAC-SHA256 signed session token bound to owner settings and expiry."""
    issued_at = int(time.time()) if now is None else int(now)
    exp = issued_at + max(60, settings.session_ttl_seconds)
    nonce = secrets.token_hex(16)
    payload = f"{exp}.{nonce}".encode("ascii")
    sig_bytes = hmac.new(_derive_signing_key(settings), payload, hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(sig_bytes).decode("ascii").rstrip("=")
    return f"{exp}.{nonce}.{sig}"


def verify_session_token(
    token: str,
    settings: WorkbenchSettings,
    *,
    now: int | None = None,
) -> bool:
    """Verify HMAC signature and expiry of a signed session token."""
    parts = token.split(".")
    if len(parts) != 3:
        return False
    exp_str, nonce, actual_sig = parts
    if not exp_str.isdigit() or not nonce or not actual_sig:
        return False

    current = int(time.time()) if now is None else int(now)
    if int(exp_str) < current:
        return False

    payload = f"{exp_str}.{nonce}".encode("ascii")
    expected_bytes = hmac.new(_derive_signing_key(settings), payload, hashlib.sha256).digest()
    expected_sig = base64.urlsafe_b64encode(expected_bytes).decode("ascii").rstrip("=")
    return hmac.compare_digest(actual_sig, expected_sig)


def is_https_request(request: Request) -> bool:
    """Detect HTTPS either directly or behind Render's TLS-terminating proxy."""
    if request.url.scheme == "https":
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    protos = [p.strip().lower() for p in forwarded_proto.split(",") if p.strip()]
    return "https" in protos


def extract_client_ip(request: Request) -> str:
    """Determine client IP safely using Render's rightmost proxy hop when behind proxy."""
    host = request.client.host if request.client else "unknown"
    if os.environ.get("RENDER", "").strip().lower() in {"1", "true", "yes"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return host


def is_request_authenticated(request: Request, settings: WorkbenchSettings) -> bool:
    """Verify request carries a valid owner session cookie or Bearer token."""
    if not settings.auth_required:
        return True
    if not settings.auth_configured:
        return False

    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        candidate = auth_header[7:].strip()
        if constant_time_equal(candidate, settings.owner_password):
            return True

    cookie_token = request.cookies.get(HTTPS_SESSION_COOKIE) or request.cookies.get(
        HTTP_SESSION_COOKIE
    )
    if cookie_token and verify_session_token(cookie_token, settings):
        return True

    return False


class LoginRateLimiter:
    """Bounded in-memory sliding-window brute-force limiter for owner login attempts."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: float = 60.0,
        lockout_seconds: float = 60.0,
        global_max_failures: int = 30,
        max_tracked_ips: int = 1024,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.global_max_failures = global_max_failures
        self.max_tracked_ips = max_tracked_ips
        self._lock = Lock()
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._global_failures: deque[float] = deque()
        self._global_locked_until: float = 0.0

    def _prune(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def _gc_stale(self, now: float) -> None:
        for ip in list(self._failures):
            bucket = self._failures[ip]
            self._prune(bucket, now)
            if not bucket and self._locked_until.get(ip, 0.0) <= now:
                self._failures.pop(ip, None)
                self._locked_until.pop(ip, None)
        for ip in list(self._locked_until):
            if self._locked_until[ip] <= now:
                self._locked_until.pop(ip, None)
        while len(self._failures) > self.max_tracked_ips:
            oldest_ip = next(iter(self._failures))
            self._failures.pop(oldest_ip, None)
            self._locked_until.pop(oldest_ip, None)

    def check_locked(self, client_key: str) -> int | None:
        now = time.monotonic()
        with self._lock:
            self._gc_stale(now)
            if self._global_locked_until > now:
                return max(1, int(self._global_locked_until - now))
            until = self._locked_until.get(client_key, 0.0)
            if until > now:
                return max(1, int(until - now))
        return None

    def record_failure(self, client_key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._gc_stale(now)
            bucket = self._failures.setdefault(client_key, deque())
            self._prune(bucket, now)
            bucket.append(now)
            if len(bucket) >= self.max_failures:
                self._locked_until[client_key] = now + self.lockout_seconds

            self._prune(self._global_failures, now)
            self._global_failures.append(now)
            if len(self._global_failures) >= self.global_max_failures:
                self._global_locked_until = now + self.lockout_seconds

    def reset(self, client_key: str) -> None:
        with self._lock:
            self._failures.pop(client_key, None)
            self._locked_until.pop(client_key, None)
