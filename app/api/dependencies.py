"""FastAPI dependencies for HTTP authentication boundaries."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..auth import (
    AuthorizedDevice,
    DeviceRegistry,
    DeviceRevokedError,
    InvalidDeviceTokenError,
)


bearer_scheme = HTTPBearer(auto_error=False)


def require_authorized_device(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthorizedDevice:
    """Authenticate an opaque bearer credential into a sanitized identity."""
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials.strip()
    ):
        raise _unauthorized()

    registry = cast(DeviceRegistry, request.app.state.device_registry)
    try:
        return registry.authenticate(credentials.credentials)
    except (InvalidDeviceTokenError, DeviceRevokedError) as exc:
        raise _unauthorized() from exc


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )

