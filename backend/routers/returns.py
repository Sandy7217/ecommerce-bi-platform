from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.routers.common import DEMO_RETURNS, DEMO_SALES, DEMO_SKUS, exclude_unicommerce_myntra_sales, rows_or_demo
from backend.services.sku_mapper import extract_style_color

router = APIRouter(prefix="/returns", tags=["returns"])


@router.get("/summary")
def returns_summary(from_date: date | None = None, to_date: date | None = None):
    rows = _mtd_returns(from_date, to_date)
    return {
        "return_value": sum(float(row.get("return_value") or 0) for row in rows),
        "return_qty": sum(int(row.get("qty") or 0) for row in rows),
    }


@router.get("/by_channel")
def returns_by_channel(from_date: date | None = None, to_date: date | None = None):
    grouped: dict[str, float] = defaultdict(float)
    for row in _mtd_returns(from_date, to_date):
        grouped[row.get("channel") or "Unknown"] += float(row.get("return_value") or 0)
    return [{"channel": key, "return_value": value} for key, value in grouped.items()]


@router.get("/high_return_skus")
def high_return_skus(from_date: date | None = None, to_date: date | None = None):
    returns_by_style: dict[str, dict[str, float]] = defaultdict(lambda: {"return_qty": 0.0, "return_value": 0.0})
    for row in _mtd_returns(from_date, to_date):
        key = _metric_style_key(row)
        if not key:
            key = "Unknown"
        returns_by_style[key]["return_qty"] += float(row.get("qty") or 0)
        returns_by_style[key]["return_value"] += float(row.get("return_value") or 0)

    sales_by_style: dict[str, float] = defaultdict(float)
    for row in _mtd_sales(from_date, to_date):
        key = _metric_style_key(row)
        if key:
            sales_by_style[key] += float(row.get("qty") or 0)

    sku_lookup = _sku_lookup()
    total_return_qty = sum(metrics["return_qty"] for metrics in returns_by_style.values())
    rows: list[dict[str, Any]] = []
    for key, metrics in returns_by_style.items():
        sales_qty = sales_by_style.get(key, 0.0)
        sku = sku_lookup.get(key, {})
        return_qty = metrics["return_qty"]
        rows.append(
            {
                "style_color": key,
                "sales_qty": int(sales_qty),
                "return_qty": int(return_qty),
                "return_value": round(metrics["return_value"], 2),
                "return_pct": round(return_qty * 100 / max(sales_qty, 1), 2),
                "inventory": int(sku.get("total_inventory") or 0),
                "sale_grade": str(sku.get("sale_grade_old") or "Unknown"),
                "share": round(return_qty * 100 / max(total_return_qty, 1), 2),
            }
        )
    return sorted(rows, key=lambda row: row["return_qty"], reverse=True)


@router.get("/trend")
def returns_trend(from_date: date | None = None, to_date: date | None = None):
    trend: dict[str, dict[str, float | int]] = defaultdict(lambda: {"return_value": 0.0, "return_qty": 0})
    for row in _mtd_returns(from_date, to_date):
        day = str(row.get("date"))
        trend[day]["return_value"] = float(trend[day]["return_value"]) + float(row.get("return_value") or 0)
        trend[day]["return_qty"] = int(trend[day]["return_qty"]) + int(row.get("qty") or 0)
    return [{"date": day, **values} for day, values in sorted(trend.items())]


def _window(from_date: date | None = None, to_date: date | None = None) -> tuple[date, date]:
    default_end = date.today() - timedelta(days=1)
    end_date = to_date or default_end
    start_date = from_date or end_date.replace(day=1)
    return start_date, end_date


def _date_filters(from_date: date | None = None, to_date: date | None = None) -> list[tuple[str, str]]:
    start_date, end_date = _window(from_date, to_date)
    return [("date", f"gte.{start_date.isoformat()}"), ("date", f"lte.{end_date.isoformat()}")]


def _style_key(value: Any) -> str:
    return extract_style_color(value) or ""


def _metric_style_key(row: dict[str, Any]) -> str:
    for column in ("style_color", "internal_sku"):
        key = _style_key(row.get(column))
        if key:
            return key
    return ""


def _mtd_sales(from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    rows = table_select_all(
        "sales_fact",
        columns="date,style_color,internal_sku,selling_price,qty,channel,marketplace,source",
        filters=_date_filters(from_date, to_date),
        max_rows=300000,
    )
    if not rows and not get_settings().has_supabase:
        rows = DEMO_SALES
    return exclude_unicommerce_myntra_sales(rows)


def _mtd_returns(from_date: date | None = None, to_date: date | None = None):
    rows = table_select_all(
        "returns_fact",
        columns="date,style_color,internal_sku,return_value,qty,channel",
        filters=_date_filters(from_date, to_date),
        max_rows=300000,
    )
    if rows or get_settings().has_supabase:
        return rows
    return rows_or_demo("returns_fact", DEMO_RETURNS, limit=20)


def _sku_lookup() -> dict[str, dict[str, Any]]:
    rows = table_select_all(
        "sku_master",
        columns="style_color,total_inventory,sale_grade_old",
        max_rows=500000,
    )
    if not rows and not get_settings().has_supabase:
        rows = DEMO_SKUS
    return {_style_key(row.get("style_color")): row for row in rows if _style_key(row.get("style_color"))}
