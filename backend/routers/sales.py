from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Query

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.routers.common import DEMO_SALES, DEMO_SKUS, rows_or_demo, paginate
from backend.routers.common import DEMO_RETURNS
from backend.services.alert_engine import detect_fast_movers
from backend.services.category_engine import assign_category, finalize_category_new
from backend.services.sku_mapper import is_myntra_channel, normalize_channel

router = APIRouter(prefix="/sales", tags=["sales"])


def _window(from_date: date | None = None, to_date: date | None = None) -> tuple[date, date]:
    default_end = date.today() - timedelta(days=1)
    end_date = to_date or default_end
    start_date = from_date or end_date.replace(day=1)
    return start_date, end_date


def _same_period_previous_month(start_date: date, end_date: date) -> tuple[date, date]:
    previous_year = start_date.year
    previous_month = start_date.month - 1
    if previous_month == 0:
        previous_month = 12
        previous_year -= 1

    previous_month_last_day = calendar.monthrange(previous_year, previous_month)[1]
    previous_start = date(previous_year, previous_month, min(start_date.day, previous_month_last_day))
    previous_end = date(previous_year, previous_month, min(end_date.day, previous_month_last_day))
    if previous_end < previous_start:
        previous_end = previous_start
    return previous_start, previous_end


def _growth_pct(current: float, previous: float) -> float:
    if previous:
        return round((current - previous) * 100 / previous, 2)
    return 100.0 if current else 0.0


def _filters(from_date: date | None = None, to_date: date | None = None, channel: str | None = None) -> list[tuple[str, str]]:
    start_date, end_date = _window(from_date, to_date)
    filters = [("date", f"gte.{start_date.isoformat()}"), ("date", f"lte.{end_date.isoformat()}")]
    if channel:
        filters.append(("channel", f"eq.{channel}"))
    return filters


def _exclude_duplicate_myntra_sales(rows: list[dict[str, Any]], include_sales_master_myntra: bool = False) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        source = str(row.get("source") or "").lower()
        if source == "unicommerce" and is_myntra_channel(row.get("channel")):
            continue
        if not include_sales_master_myntra and source == "sales_master" and is_myntra_channel(row.get("channel")):
            continue
        filtered.append(row)
    return filtered


def _sales_rows(from_date: date | None = None, to_date: date | None = None, channel: str | None = None, include_sales_master_myntra: bool = False) -> list[dict[str, Any]]:
    rows = table_select_all(
        "sales_fact",
        columns="date,style_color,internal_sku,selling_price,qty,channel,marketplace,source,state",
        filters=_filters(from_date, to_date, channel),
        max_rows=300000,
    )
    if not rows and not get_settings().has_supabase:
        rows = DEMO_SALES
    rows = _exclude_duplicate_myntra_sales(rows, include_sales_master_myntra=include_sales_master_myntra)
    if channel:
        requested = channel.lower()
        rows = [
            row
            for row in rows
            if requested
            in {
                str(row.get("channel") or "").lower(),
                str(row.get("marketplace") or "").lower(),
                normalize_channel(row.get("marketplace") or row.get("channel")).lower(),
            }
        ]
    return rows


def _return_rows(from_date: date | None = None, to_date: date | None = None, channel: str | None = None) -> list[dict[str, Any]]:
    rows = table_select_all(
        "returns_fact",
        columns="date,style_color,internal_sku,return_value,qty,channel,state",
        filters=_filters(from_date, to_date, channel),
        max_rows=300000,
    )
    if not rows and not get_settings().has_supabase:
        rows = DEMO_RETURNS
    if channel:
        rows = [row for row in rows if str(row.get("channel")).lower() == channel.lower()]
    return rows


def _sales_amount(row: dict[str, Any]) -> float:
    return float(row.get("selling_price") or 0) * int(row.get("qty") or 1)


@router.get("/kpis")
def sales_kpis(from_date: date | None = None, to_date: date | None = None, channel: str | None = None, category: str | None = None):
    del category
    today_date = date.today()
    start_date, end_date = _window(from_date, to_date)
    previous_start, previous_end = _same_period_previous_month(start_date, end_date)
    rows = _sales_rows(start_date, end_date, channel)
    return_rows = _return_rows(start_date, end_date, channel)
    previous_rows = _sales_rows(previous_start, previous_end, channel, include_sales_master_myntra=True)
    previous_return_rows = _return_rows(previous_start, previous_end, channel)
    today = today_date.isoformat()
    yesterday = (today_date - timedelta(days=1)).isoformat()
    total_sales = sum(_sales_amount(row) for row in rows)
    total_qty = sum(int(row.get("qty") or 0) for row in rows)
    return_qty = sum(int(row.get("qty") or 0) for row in return_rows)
    return_value = sum(float(row.get("return_value") or 0) for row in return_rows)
    previous_sales = sum(_sales_amount(row) for row in previous_rows)
    previous_qty = sum(int(row.get("qty") or 0) for row in previous_rows)
    previous_return_qty = sum(int(row.get("qty") or 0) for row in previous_return_rows)
    return_pct = round(return_qty * 100 / max(total_qty, 1), 2)
    previous_return_pct = round(previous_return_qty * 100 / max(previous_qty, 1), 2)
    yesterday_rows = [row for row in rows if row.get("date") == yesterday]
    return {
        "mtd_sales": total_sales,
        "mtd_qty": total_qty,
        "mtd_sales_lakh": round(total_sales / 100000, 2),
        "asp": round(total_sales / max(total_qty, 1), 2),
        "return_pct": return_pct,
        "return_qty": return_qty,
        "return_value": return_value,
        "yesterday_sales": sum(_sales_amount(row) for row in yesterday_rows),
        "yesterday_qty": sum(int(row.get("qty") or 0) for row in yesterday_rows),
        "sales_growth_pct": _growth_pct(total_sales, previous_sales),
        "qty_growth_pct": _growth_pct(total_qty, previous_qty),
        "return_pct_change": round(return_pct - previous_return_pct, 2),
        "comparison_from": previous_start.isoformat(),
        "comparison_to": previous_end.isoformat(),
        "date": today,
    }


@router.get("/trend")
def sales_trend(from_date: date | None = None, to_date: date | None = None, channel: str | None = None, granularity: str = "daily"):
    del granularity
    rows = _sales_rows(from_date, to_date, channel)
    trend: dict[str, dict[str, float | int]] = defaultdict(lambda: {"sales_value": 0.0, "qty": 0})
    for row in rows:
        day = str(row.get("date"))
        trend[day]["sales_value"] = float(trend[day]["sales_value"]) + _sales_amount(row)
        trend[day]["qty"] = int(trend[day]["qty"]) + int(row.get("qty") or 0)
    return [{"date": day, **values} for day, values in sorted(trend.items())]


@router.get("/by_channel_trend")
def sales_by_channel_trend(from_date: date | None = None, to_date: date | None = None):
    grouped: dict[tuple[str, str], dict[str, float | int | str]] = defaultdict(lambda: {"sales_value": 0.0, "qty": 0})
    for row in _sales_rows(from_date, to_date):
        day = str(row.get("date"))
        channel = normalize_channel(row.get("marketplace") or row.get("channel"))
        key = (day, channel)
        grouped[key]["date"] = day
        grouped[key]["channel"] = channel
        grouped[key]["sales_value"] = float(grouped[key]["sales_value"]) + _sales_amount(row)
        grouped[key]["qty"] = int(grouped[key]["qty"]) + int(row.get("qty") or 0)
    return [values for _key, values in sorted(grouped.items())]


@router.get("/marketplace_summary")
def marketplace_summary(from_date: date | None = None, to_date: date | None = None):
    grouped: dict[str, dict[str, float | int | str]] = defaultdict(
        lambda: {
            "marketplace": "Unknown",
            "sales_value": 0.0,
            "sales_qty": 0,
            "return_value": 0.0,
            "return_qty": 0,
        }
    )
    for row in _sales_rows(from_date, to_date):
        marketplace = normalize_channel(row.get("marketplace") or row.get("channel"))
        grouped[marketplace]["marketplace"] = marketplace
        grouped[marketplace]["sales_value"] = float(grouped[marketplace]["sales_value"]) + _sales_amount(row)
        grouped[marketplace]["sales_qty"] = int(grouped[marketplace]["sales_qty"]) + int(row.get("qty") or 0)
    for row in _return_rows(from_date, to_date):
        marketplace = normalize_channel(row.get("marketplace") or row.get("channel"))
        grouped[marketplace]["marketplace"] = marketplace
        grouped[marketplace]["return_value"] = float(grouped[marketplace]["return_value"]) + float(row.get("return_value") or 0)
        grouped[marketplace]["return_qty"] = int(grouped[marketplace]["return_qty"]) + int(row.get("qty") or 0)

    rows = []
    for item in grouped.values():
        sales_value = float(item["sales_value"])
        sales_qty = int(item["sales_qty"])
        return_value = float(item["return_value"])
        return_qty = int(item["return_qty"])
        rows.append(
            {
                "marketplace": item["marketplace"],
                "sales_value": round(sales_value, 2),
                "sales_qty": sales_qty,
                "return_value": round(return_value, 2),
                "return_qty": return_qty,
                "return_pct": round(return_qty * 100 / max(sales_qty, 1), 2),
                "net_sales": round(sales_value - return_value, 2),
            }
        )
    return sorted(rows, key=lambda row: row["sales_value"], reverse=True)


@router.get("/asp")
def average_selling_price(from_date: date | None = None, to_date: date | None = None, channel: str | None = None):
    rows = _sales_rows(from_date, to_date, channel)
    total_sales = sum(_sales_amount(row) for row in rows)
    total_qty = sum(int(row.get("qty") or 0) for row in rows)
    return {"asp": round(total_sales / max(total_qty, 1), 2), "sales_value": total_sales, "qty": total_qty}


@router.get("/top_products")
def top_products(limit: int = Query(20, le=100), from_date: date | None = None, to_date: date | None = None):
    start_date, end_date = _window(from_date, to_date)
    period_days = max((end_date - start_date).days + 1, 1)
    previous_start, previous_end = _same_period_previous_month(start_date, end_date)
    current = _sales_rows(start_date, end_date)
    previous = _sales_rows(previous_start, previous_end, include_sales_master_myntra=True)
    returns = _return_rows(start_date, end_date)

    grouped: dict[str, dict[str, float | int | str]] = defaultdict(lambda: {"revenue": 0.0, "orders": 0, "qty": 0})
    previous_revenue: dict[str, float] = defaultdict(float)
    return_qty: dict[str, int] = defaultdict(int)
    for row in current:
        style = str(row.get("style_color") or row.get("internal_sku") or "Unknown")
        grouped[style]["style_color"] = style
        grouped[style]["revenue"] = float(grouped[style]["revenue"]) + _sales_amount(row)
        grouped[style]["orders"] = int(grouped[style]["orders"]) + 1
        grouped[style]["qty"] = int(grouped[style]["qty"]) + int(row.get("qty") or 0)
    for row in previous:
        style = str(row.get("style_color") or row.get("internal_sku") or "Unknown")
        previous_revenue[style] += _sales_amount(row)
    for row in returns:
        style = str(row.get("style_color") or row.get("internal_sku") or "Unknown")
        return_qty[style] += int(row.get("qty") or 0)

    products = []
    for style, data in grouped.items():
        revenue = float(data["revenue"])
        prev = previous_revenue[style]
        qty = int(data["qty"])
        products.append(
            {
                "style_color": style,
                "revenue": round(revenue, 2),
                "orders": int(data["orders"]),
                "qty": qty,
                "ros": round(qty / period_days, 2),
                "growth_pct": _growth_pct(revenue, prev),
                "return_pct": round(return_qty[style] * 100 / max(qty, 1), 2),
            }
        )
    return sorted(products, key=lambda item: item["revenue"], reverse=True)[:limit]


@router.get("/by_category")
def sales_by_category(from_date: date | None = None, to_date: date | None = None):
    start_date, end_date = _window(from_date, to_date)
    period_days = max((end_date - start_date).days + 1, 1)
    sales = _sales_rows(from_date, to_date)
    skus = {row["style_color"]: row for row in rows_or_demo("sku_master", DEMO_SKUS)}
    style_qty: dict[str, int] = defaultdict(int)
    for row in sales:
        style_qty[str(row.get("style_color") or row.get("internal_sku") or "Unknown")] += int(row.get("qty") or 0)

    def category_for(style: str) -> str:
        sku = skus.get(style, {})
        if sku.get("category_new"):
            return str(sku["category_new"])
        ros = style_qty[style] / period_days
        return finalize_category_new({**sku, "ros": ros, "new_category": assign_category(ros)})

    grouped: dict[str, dict[str, float | int | set[str]]] = defaultdict(lambda: {"sales_value": 0.0, "qty": 0, "sku_count": set()})
    for row in sales:
        style = str(row.get("style_color") or row.get("internal_sku") or "Unknown")
        category = category_for(style)
        grouped[category]["sales_value"] = float(grouped[category]["sales_value"]) + _sales_amount(row)
        grouped[category]["qty"] = int(grouped[category]["qty"]) + int(row.get("qty") or 0)
        grouped[category]["sku_count"].add(style)
    category_order = [
        "NOOS",
        "NOOS(Green)",
        "NOOS(Yellow)",
        "NOOS(Red)",
        "NOOS(Potential)",
        "Green",
        "Yellow",
        "Red",
        "Dead",
        "Winter",
        "Discontinue",
        "OOS",
        "Dog styles",
        "Unknown",
    ]
    for category in category_order:
        grouped.setdefault(category, {"sales_value": 0.0, "qty": 0, "sku_count": set()})
    ordered = category_order + sorted(category for category in grouped if category not in category_order)
    return [{"category": category, "sales_value": grouped[category]["sales_value"], "qty": grouped[category]["qty"], "sku_count": len(grouped[category]["sku_count"])} for category in ordered]


@router.get("/styles")
def sales_styles(from_date: date | None = None, to_date: date | None = None, channel: str | None = None, category: str | None = None, sort: str = "mtd_sales", page: int = 1, limit: int = Query(50, le=200)):
    del from_date, to_date, channel
    rows = rows_or_demo("sku_master", DEMO_SKUS)
    if category:
        rows = [row for row in rows if row.get("category_new") == category or row.get("cross_category") == category]
    mapped = [
        {
            "style_color": row["style_color"],
            "category_new": row.get("category_new"),
            "cross_category": row.get("cross_category"),
            "ros": row.get("ros", 0),
            "mtd_sales": float(row.get("current_month_sales") or 0),
            "mtd_qty": int(row.get("current_month_sales") or 0),
            "growth_flag": "fast_mover" if float(row.get("ros_7d") or 0) > float(row.get("ros_30d") or 0) * 1.5 else "stable",
            "doi": row.get("doi", 0),
        }
        for row in rows
    ]
    mapped.sort(key=lambda row: row.get(sort, 0) or 0, reverse=True)
    return paginate(mapped, page, limit)


@router.get("/fast_movers")
def fast_movers():
    return detect_fast_movers(rows_or_demo("sku_master", DEMO_SKUS))
