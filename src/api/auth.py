"""JWT authentication and RBAC middleware for API endpoints.

Provides:
- create_access_token(): Issue JWT tokens with role claims
- verify_jwt(): FastAPI dependency that validates JWT Bearer tokens
- require_role(): Factory that returns a dependency enforcing role-based access
- Role enum: MANAGER, RISK_OFFICER, VIEWER, ADMIN

In development mode (DEBUG=true), authentication is bypassed and all
requests are treated as the "dev-user" with ADMIN role.
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
class Role(str, Enum):
    """User roles for the Macro Trading PMS.

    ADMIN       — Full access including user management.
    MANAGER     — Can approve/reject trades, open/close positions, trigger MTM.
    RISK_OFFICER — Can view risk data and trigger emergency stop.
    VIEWER      — Read-only access to book, PnL, briefings, and risk.
    """

    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    RISK_OFFICER = "RISK_OFFICER"
    VIEWER = "VIEWER"


# Role hierarchy: higher roles inherit permissions from lower ones
_ROLE_HIERARCHY: dict[Role, set[Role]] = {
    Role.ADMIN: {Role.ADMIN, Role.MANAGER, Role.RISK_OFFICER, Role.VIEWER},
    Role.MANAGER: {Role.MANAGER, Role.VIEWER},
    Role.RISK_OFFICER: {Role.RISK_OFFICER, Role.VIEWER},
    Role.VIEWER: {Role.VIEWER},
}


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------
def create_access_token(
    subject: str,
    role: str = "VIEWER",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token with role claim.

    Args:
        subject: User identifier (email or username).
        role: User role (ADMIN, MANAGER, RISK_OFFICER, VIEWER).
        expires_delta: Custom expiry. Defaults to settings.jwt_expiry_minutes.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expiry_minutes)
    )
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(
    subject: str,
    role: str = "VIEWER",
    expires_delta: timedelta | None = None,
) -> str:
    """Create a long-lived refresh token (7 days default).

    Args:
        subject: User identifier.
        role: User role.
        expires_delta: Custom expiry. Defaults to 7 days.

    Returns:
        Encoded JWT string with type=refresh claim.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=7)
    )
    payload = {
        "sub": subject,
        "role": role,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


# ---------------------------------------------------------------------------
# Token verification dependency
# ---------------------------------------------------------------------------
async def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Validate JWT Bearer token. Bypassed when DEBUG=true.

    Returns the decoded payload dict with at least {"sub": ..., "role": ...}.
    """
    if settings.debug:
        return {"sub": "dev-user", "role": "ADMIN"}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        # Ensure role claim is present (backward compat: default to VIEWER)
        if "role" not in payload:
            payload["role"] = "VIEWER"
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Typed alias for use in route signatures
CurrentUser = Annotated[dict, Depends(verify_jwt)]


# ---------------------------------------------------------------------------
# Role-based access control dependency
# ---------------------------------------------------------------------------
def require_role(*allowed_roles: Role):
    """Factory that returns a FastAPI dependency enforcing role membership.

    Usage::

        @router.post("/approve", dependencies=[Depends(require_role(Role.MANAGER))])
        async def approve_trade(...): ...

    Or inject the user payload::

        @router.get("/book")
        async def get_book(user: dict = Depends(require_role(Role.VIEWER))):
            print(user["sub"])  # "alice@fund.com"
    """

    async def _check_role(
        user: dict = Depends(verify_jwt),
    ) -> dict:
        user_role_str = user.get("role", "VIEWER")
        try:
            user_role = Role(user_role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown role: {user_role_str}",
            )

        # Check if user's role (or any role it inherits) matches allowed_roles
        effective_roles = _ROLE_HIERARCHY.get(user_role, {user_role})
        if not effective_roles.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. Required: "
                    f"{', '.join(r.value for r in allowed_roles)}. "
                    f"Your role: {user_role.value}."
                ),
            )
        return user

    return _check_role
