from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.models.schemas import Role


ALL_ROLES: tuple[Role, ...] = ("super_admin", "admin", "manager", "analyst", "md", "viewer")
ADMIN_ROLES: tuple[Role, ...] = ("super_admin", "admin")
MANAGER_ROLES: tuple[Role, ...] = ("super_admin", "admin", "manager")

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str | None
    role: Role
    is_active: bool


def _auth_headers(access_token: str) -> dict[str, str]:
    settings = get_settings()
    api_key = settings.supabase_anon_key or settings.supabase_service_key
    if not settings.supabase_url or not api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase Auth is not configured")
    return {"apikey": api_key, "Authorization": f"Bearer {access_token}"}


def _load_user(access_token: str) -> dict:
    settings = get_settings()
    response = httpx.get(f"{settings.supabase_url}/auth/v1/user", headers=_auth_headers(access_token), timeout=15)
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to validate authentication")
    payload = response.json()
    if not payload.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return payload


def _load_role(user_id: str, email: str | None) -> dict | None:
    rows = table_select_all("user_roles", max_rows=5000)
    normalized_email = (email or "").lower()
    for row in rows:
        if row.get("user_id") == user_id:
            return row
    if normalized_email:
        for row in rows:
            if str(row.get("email") or "").lower() == normalized_email:
                return row
    return None


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> CurrentUser:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    auth_user = _load_user(credentials.credentials)
    role_row = _load_role(str(auth_user["id"]), auth_user.get("email"))
    if not role_row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role is not configured")
    if role_row.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    role = str(role_row.get("role") or "viewer")
    if role not in ALL_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role is not allowed")
    return CurrentUser(
        user_id=str(auth_user["id"]),
        email=auth_user.get("email"),
        role=role,  # type: ignore[arg-type]
        is_active=role_row.get("is_active") is not False,
    )


def require_roles(*allowed_roles: Role):
    allowed = set(allowed_roles)

    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user

    return dependency


def role_dependency(roles: Iterable[Role]):
    return Depends(require_roles(*tuple(roles)))
