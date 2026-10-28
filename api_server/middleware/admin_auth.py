"""
Admin authentication middleware.

Protects /admin endpoints with:
- Bearer token validation (constant-time compare)
- Optional localhost-only restriction
"""

from __future__ import annotations

import hmac
from functools import wraps

from flask import current_app, jsonify, request


def _as_bool(value, default: bool) -> bool:
    """Parse flexible bool values from app config/environment."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _is_localhost(remote_addr: str | None) -> bool:
    """Best-effort localhost detection for IPv4/IPv6 loopback."""
    if not remote_addr:
        return False
    return remote_addr in {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}


def require_admin_auth(f):
    """Decorator that enforces admin auth policy for protected endpoints."""

    @wraps(f)
    def decorated(*args, **kwargs):
        require_token = _as_bool(current_app.config.get("ADMIN_REQUIRE_TOKEN"), True)
        localhost_only = _as_bool(current_app.config.get("ADMIN_LOCALHOST_ONLY"), False)

        if localhost_only and not _is_localhost(request.remote_addr):
            return jsonify(
                {
                    "error": "Forbidden",
                    "message": "Admin endpoints are restricted to localhost",
                }
            ), 403

        if require_token:
            auth_header = request.headers.get("Authorization", "")
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return jsonify(
                    {
                        "error": "Unauthorized",
                        "message": "Expected Authorization: Bearer <admin_token>",
                    }
                ), 401

            provided_token = parts[1]
            expected_token = str(current_app.config.get("ADMIN_TOKEN", ""))

            if not expected_token or not hmac.compare_digest(provided_token, expected_token):
                return jsonify(
                    {
                        "error": "Unauthorized",
                        "message": "Invalid admin token",
                    }
                ), 401

        return f(*args, **kwargs)

    return decorated

