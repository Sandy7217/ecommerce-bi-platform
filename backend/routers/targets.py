from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.db.supabase_client import table_select_all, table_upsert

router = APIRouter(prefix="/targets", tags=["targets"])
DEFAULT_TARGET_VALUE = 50000000


class TargetPayload(BaseModel):
    month: str
    channel: str = "ALL"
    target_value: int = Field(gt=0)
    target_qty: int | None = 0
    created_by: str | None = None


def _month_start(value: str) -> str:
    text = value.strip()
    if len(text) == 7:
        text = f"{text}-01"
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM or YYYY-MM-01") from exc
    return parsed.replace(day=1).isoformat()


def _target_setup_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Targets table is not available. Run backend/db/migrations/002_targets.sql in Supabase SQL Editor. {exc}")


def _is_missing_targets_table(exc: Exception) -> bool:
    text = str(exc).lower()
    return "targets" in text and ("pgrst205" in text or "could not find the table" in text or "404" in text)


def _default_target_row(month: str) -> dict[str, Any]:
    return {
        "id": None,
        "month": month,
        "channel": "ALL",
        "target_value": DEFAULT_TARGET_VALUE,
        "target_qty": 0,
        "created_by": None,
        "created_at": None,
        "setup_required": True,
    }


def _target_rows(month: str) -> list[dict[str, Any]]:
    try:
        return table_select_all(
            "targets",
            columns="id,month,channel,target_value,target_qty,created_by,created_at",
            filters=[("month", f"eq.{month}")],
            max_rows=1000,
        )
    except Exception as exc:
        raise _target_setup_error(exc) from exc


@router.get("")
def get_targets(month: str):
    month_start = _month_start(month)
    try:
        rows = _target_rows(month_start)
    except HTTPException as exc:
        if _is_missing_targets_table(exc):
            return {"month": month_start, "items": [_default_target_row(month_start)], "setup_required": True}
        raise
    return {"month": month_start, "items": sorted(rows, key=lambda row: str(row.get("channel") or "")), "setup_required": False}


@router.post("")
def upsert_target(payload: TargetPayload):
    month_start = _month_start(payload.month)
    row = {
        "month": month_start,
        "channel": payload.channel.strip().upper() or "ALL",
        "target_value": payload.target_value,
        "target_qty": payload.target_qty or 0,
        "created_by": payload.created_by,
    }
    try:
        table_upsert("targets", [row], on_conflict="month,channel")
    except Exception as exc:
        raise _target_setup_error(exc) from exc
    rows = _target_rows(month_start)
    return next((item for item in rows if str(item.get("channel") or "").upper() == row["channel"]), row)


@router.put("/{target_id}")
def update_target(target_id: int, payload: TargetPayload):
    month_start = _month_start(payload.month)
    row = {
        "id": target_id,
        "month": month_start,
        "channel": payload.channel.strip().upper() or "ALL",
        "target_value": payload.target_value,
        "target_qty": payload.target_qty or 0,
        "created_by": payload.created_by,
    }
    try:
        table_upsert("targets", [row], on_conflict="id")
    except Exception as exc:
        raise _target_setup_error(exc) from exc
    rows = _target_rows(month_start)
    return next((item for item in rows if int(item.get("id") or 0) == target_id), row)
