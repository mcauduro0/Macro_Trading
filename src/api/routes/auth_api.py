"""Authentication endpoints.

Provides:
- POST /auth/token     -- Issue JWT access + refresh tokens
- POST /auth/refresh   -- Exchange refresh token for new access token
- GET  /auth/me        -- Return current user info from token
"""

from __future__ import annotations

import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import (
    CurrentUser,
    create_access_token,
    create_refresh_token,
    verify_jwt,
)
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class TokenRequest(BaseModel):
    """Login request. In production, replace with OAuth2 / LDAP integration."""

    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Hard-coded users for bootstrap. Replace with DB lookup in production.
# ---------------------------------------------------------------------------
_BOOTSTRAP_USERS: dict[str, dict] = {
    "admin": {"password": "admin", "role": "ADMIN"},
    "manager": {"password": "manager", "role": "MANAGER"},
    "risk": {"password": "risk", "role": "RISK_OFFICER"},
    "viewer": {"password": "viewer", "role": "VIEWER"},
}


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------
@router.post("/token", response_model=TokenResponse)
async def login(body: TokenRequest):
    """Issue JWT access + refresh tokens.

    In production this should validate against a user database or
    external identity provider (LDAP, OAuth2, SAML).
    """
    user = _BOOTSTRAP_USERS.get(body.username)
    if user is None or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = create_access_token(subject=body.username, role=user["role"])
    refresh = create_refresh_token(subject=body.username, role=user["role"])

    return TokenResponse(access_token=access, refresh_token=refresh)


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Not a refresh token")

        subject = payload["sub"]
        role = payload.get("role", "VIEWER")

        access = create_access_token(subject=subject, role=role)
        refresh = create_refresh_token(subject=subject, role=role)
        return TokenResponse(access_token=access, refresh_token=refresh)

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------
@router.get("/me")
async def get_current_user(user: CurrentUser):
    """Return current user info from the JWT token."""
    return {
        "username": user.get("sub"),
        "role": user.get("role"),
    }
