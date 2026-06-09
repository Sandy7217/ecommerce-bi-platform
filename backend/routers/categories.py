from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.db.supabase_client import table_select_all, table_upsert
from backend.models.schemas import CategoryApprovalRequest, DiscontinueRequest
from backend.routers.common import DEMO_SKUS, exclude_unicommerce_myntra_sales, paginate, rows_or_demo
from backend.security import MANAGER_ROLES, require_roles
from backend.services.category_engine import assign_category, finalize_category_new, flag_potential_noos

router = APIRouter(prefix="/categories", tags=["categories"])


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _style_sales_metrics() -> dict[str, dict[str, float]]:
    today = date.today()
    start_30d = today - timedelta(days=29)
    start_7d = today - timedelta(days=6)
    sales = table_select_all(
        "sales_fact",
        columns="date,style_color,qty,channel,marketplace,source",
        filters=[("date", f"gte.{start_30d.isoformat()}"), ("date", f"lte.{today.isoformat()}")],
    )
    metrics: dict[str, dict[str, float]] = defaultdict(lambda: {"qty_30d": 0.0, "qty_7d": 0.0, "ros_30d": 0.0, "ros_7d": 0.0})
    for row in exclude_unicommerce_myntra_sales(sales):
        style = row.get("style_color")
        day = _to_date(row.get("date"))
        if not style or not day:
            continue
        qty = float(row.get("qty") or 0)
        metrics[str(style)]["qty_30d"] += qty
        if day >= start_7d:
            metrics[str(style)]["qty_7d"] += qty
    for values in metrics.values():
        values["ros_30d"] = round(values["qty_30d"] / 30, 2)
        values["ros_7d"] = round(values["qty_7d"] / 7, 2)
    return metrics


def _sku_rows() -> list[dict[str, Any]]:
    overrides = {
        row.get("style_color"): row.get("override_category")
        for row in rows_or_demo("category_overrides", [])
        if row.get("style_color") and row.get("override_category")
    }
    rows: list[dict[str, Any]] = []
    for row in rows_or_demo("sku_master", DEMO_SKUS):
        style = row.get("style_color")
        rows.append({**row, "category_new": overrides.get(style) or row.get("category_new")})
    return rows


def _category_for(row: dict[str, Any], ros: float | None = None) -> str:
    if row.get("category_new"):
        return str(row["category_new"])
    ros_value = float(ros if ros is not None else row.get("ros_30d") or row.get("ros") or 0)
    return finalize_category_new({**row, "ros": ros_value, "new_category": assign_category(ros_value), "_is_dog_style": row.get("is_dog_style")})


def _categorized_rows() -> list[dict[str, Any]]:
    metrics = _style_sales_metrics()
    rows: list[dict[str, Any]] = []
    for row in _sku_rows():
        style = str(row.get("style_color") or "")
        style_metrics = metrics.get(style, {})
        ros_30d = float(style_metrics.get("ros_30d") or row.get("ros_30d") or row.get("ros") or 0)
        ros_7d = float(style_metrics.get("ros_7d") or row.get("ros_7d") or 0)
        rows.append({**row, "category_new": _category_for(row, ros_30d), "ros_30d": ros_30d, "ros_7d": ros_7d})
    return rows


@router.get("/potential_noos")
def potential_noos(page: int = 1, limit: int = Query(50, le=200)):
    rows = [
        row
        for row in _categorized_rows()
        if row.get("category_new") == "NOOS(Potential)"
        or row.get("category_new") == "Potential NOOS"
        or row.get("is_potential_noos")
        or flag_potential_noos(
            str(row.get("style_color") or ""),
            float(row.get("ros_7d") or 0),
            float(row.get("ros_30d") or 0),
            str(row.get("sale_grade_old") or row.get("category_old") or ""),
        )
    ]
    rows = sorted(rows, key=lambda row: (float(row.get("ros_30d") or 0), float(row.get("ros_7d") or 0)), reverse=True)
    return paginate(rows, page, limit)


@router.post("/approve_noos", dependencies=[Depends(require_roles(*MANAGER_ROLES))])
def approve_noos(payload: CategoryApprovalRequest):
    rows = [
        {"style_color": style, "override_category": "NOOS", "override_by": payload.override_by, "notes": payload.notes}
        for style in payload.style_colors
    ]
    inserted = table_upsert("category_overrides", rows, on_conflict="style_color") if rows else 0
    return {"status": "success", "approved": len(rows), "persisted": inserted}


@router.post("/mark_discontinue", dependencies=[Depends(require_roles(*MANAGER_ROLES))])
def mark_discontinue(payload: DiscontinueRequest):
    rows = [
        {"style_color": style, "override_category": "Discontinue", "override_by": payload.override_by, "notes": payload.notes}
        for style in payload.style_colors
    ]
    inserted = table_upsert("category_overrides", rows, on_conflict="style_color") if rows else 0
    return {"status": "success", "marked": len(rows), "persisted": inserted}


@router.get("/cross_analysis")
def cross_analysis():
    matrix: dict[str, dict[str, int]] = {}
    rows = table_select_all(
        "sku_master",
        columns="sale_grade_old,category_new",
        max_rows=500000,
    ) or DEMO_SKUS
    for row in rows:
        old = row.get("sale_grade_old") or "Unknown"
        new = row.get("category_new") or "Unknown"
        matrix.setdefault(old, {}).setdefault(new, 0)
        matrix[old][new] += 1
    return matrix


@router.get("/overrides")
def overrides():
    return rows_or_demo("category_overrides", [])
