from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException, Request

from .config import settings


_ROLE_WEIGHT = {"viewer": 1, "editor": 2, "admin": 3}


@dataclass
class AuthUser:
    user_id: str
    role: str
    token: str


def _parse_token_registry(raw: str) -> dict[str, AuthUser]:
    rows = [item.strip() for item in raw.split(",") if item.strip()]
    result: dict[str, AuthUser] = {}
    for row in rows:
        parts = [item.strip() for item in row.split(":")]
        if len(parts) < 2:
            continue
        token = parts[0]
        role = (parts[1] or "viewer").lower()
        user_id = parts[2] if len(parts) >= 3 and parts[2] else f"user-{token[-6:]}"
        if role not in _ROLE_WEIGHT:
            role = "viewer"
        result[token] = AuthUser(user_id=user_id, role=role, token=token)
    return result


def _resolve_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    key = request.headers.get("X-API-Key") or ""
    if key.strip():
        return key.strip()
    return None


def _is_health_path(request: Request) -> bool:
    path = request.url.path.rstrip("/")
    return path.endswith("/health")


def _ensure_role(actual: str, required: str) -> None:
    if _ROLE_WEIGHT.get(actual, 0) < _ROLE_WEIGHT.get(required, 0):
        raise HTTPException(status_code=403, detail=f"forbidden: requires role {required}")


def _current_user_from_request(request: Request) -> AuthUser:
    if not settings.auth_enabled:
        return AuthUser(user_id="local-dev", role="admin", token="local-dev")
    token = _resolve_token(request)
    registry = _parse_token_registry(settings.auth_tokens)
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized: missing token")
    user = registry.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized: invalid token")
    return user


def require_request_access(request: Request) -> AuthUser:
    if settings.auth_allow_unauthenticated_health and _is_health_path(request):
        return AuthUser(user_id="public", role="viewer", token="public")
    user = _current_user_from_request(request)
    required = "viewer" if request.method.upper() in {"GET", "HEAD", "OPTIONS"} else "editor"
    _ensure_role(user.role, required)
    return user


def require_role(role: str) -> Callable[[Request], AuthUser]:
    role_name = (role or "viewer").lower()
    if role_name not in _ROLE_WEIGHT:
        role_name = "viewer"

    def _dep(request: Request) -> AuthUser:
        user = require_request_access(request)
        _ensure_role(user.role, role_name)
        return user

    return _dep
