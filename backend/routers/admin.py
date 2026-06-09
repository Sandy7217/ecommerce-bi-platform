from __future__ import annotations

from collections import Counter
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from backend.config import get_settings
from backend.db.supabase_client import table_select, table_select_all, table_upsert
from backend.models.schemas import PipelineStatus, UserCreate, UserUpdate
from backend.services.category_rebuild import rebuild_sku_master_categories

router = APIRouter(prefix="/admin", tags=["admin"])


def _auth_admin_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    return {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
    }


def _auth_admin_url(path: str) -> str:
    settings = get_settings()
    if not settings.supabase_url:
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    return f"{settings.supabase_url}/auth/v1{path}"


def _find_auth_user_by_email(email: str) -> dict[str, Any] | None:
    response = httpx.get(
        _auth_admin_url("/admin/users"),
        headers=_auth_admin_headers(),
        params={"page": "1", "per_page": "1000"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    users = payload.get("users") if isinstance(payload, dict) else payload
    normalized_email = email.lower()
    for user in users or []:
        if str(user.get("email") or "").lower() == normalized_email:
            return user
    return None


def _invite_auth_user(payload: UserCreate) -> dict[str, Any]:
    body = {"email": str(payload.email), "data": {"name": payload.name, "role": payload.role}}
    response = httpx.post(_auth_admin_url("/invite"), headers=_auth_admin_headers(), json=body, timeout=60)
    if response.status_code in {400, 422}:
        existing = _find_auth_user_by_email(str(payload.email))
        if existing:
            return existing
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    data = response.json()
    return data.get("user") if isinstance(data.get("user"), dict) else data


def _delete_auth_user(user_id: str) -> None:
    response = httpx.delete(_auth_admin_url(f"/admin/users/{user_id}"), headers=_auth_admin_headers(), timeout=60)
    if response.status_code not in {200, 204, 404}:
        raise HTTPException(status_code=response.status_code, detail=response.text)


def _find_user_role(user_id: str) -> dict[str, Any] | None:
    for row in table_select_all("user_roles", max_rows=5000):
        if row.get("user_id") == user_id:
            return row
    return None


def _source_sale_grade_map() -> dict[str, str]:
    for column in ("sale_grade_old", "sale_grade", "grade"):
        try:
            source_rows = table_select_all(
                "sales_fact",
                columns=f"style_color,{column}",
                max_rows=500000,
            )
        except Exception:
            continue
        grades: dict[str, str] = {}
        for row in source_rows:
            style_color = row.get("style_color")
            grade = str(row.get(column) or "").strip()
            if style_color and grade:
                grades.setdefault(str(style_color), grade)
        if grades:
            return grades
    return {}


@router.get("/users")
def users():
    return table_select("user_roles") or []


@router.post("/users")
def create_user(payload: UserCreate):
    try:
        auth_user = _invite_auth_user(payload)
        user_id = auth_user.get("id")
        if not user_id:
            raise HTTPException(status_code=502, detail="Supabase Auth did not return a user id")
        row = {"user_id": user_id, "email": str(payload.email), "name": payload.name, "role": payload.role, "is_active": True}
        persisted = table_upsert("user_roles", [row], on_conflict="email")
        return {"status": "success", "user": row, "persisted": persisted}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate):
    current = _find_user_role(user_id)
    if not current:
        raise HTTPException(status_code=404, detail="User role not found")
    row = {"user_id": user_id, **current, **payload.model_dump(exclude_none=True)}
    persisted = table_upsert("user_roles", [row], on_conflict="user_id")
    return {"status": "success", "user": row, "persisted": persisted}


@router.delete("/users/{user_id}")
def deactivate_user(user_id: str):
    current = _find_user_role(user_id)
    if not current:
        raise HTTPException(status_code=404, detail="User role not found")
    _delete_auth_user(user_id)
    return {"status": "success", "user_id": user_id}


@router.get("/upload_log")
def upload_log():
    return table_select("upload_log", limit=200) or []


@router.get("/pipeline_status", response_model=PipelineStatus)
def pipeline_status():
    uploads = table_select("upload_log", limit=20)
    last_refresh = uploads[0].get("created_at") if uploads else None
    return PipelineStatus(status="ready" if uploads else "waiting_for_uploads", last_refresh=last_refresh, uploads=uploads)


@router.post("/rebuild_categories")
def rebuild_categories():
    return rebuild_sku_master_categories()


@router.post("/backfill_sale_grades")
def backfill_sale_grades():
    rows = table_select_all(
        "sku_master",
        columns="style_color,sale_grade_old",
        max_rows=500000,
    )
    source_grades = _source_sale_grade_map()
    updates: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for row in rows:
        style_color = row.get("style_color")
        if not style_color:
            continue
        existing = str(row.get("sale_grade_old") or "").strip()
        sale_grade_old = existing or source_grades.get(str(style_color)) or "Unknown"
        updates.append({"style_color": str(style_color), "sale_grade_old": sale_grade_old})
        counts[sale_grade_old] += 1
    updated = table_upsert("sku_master", updates, on_conflict="style_color") if updates else 0
    return {
        "status": "success",
        "rows_read": len(rows),
        "rows_updated": updated,
        "source_grades_found": len(source_grades),
        "breakdown": dict(sorted(counts.items())),
    }
