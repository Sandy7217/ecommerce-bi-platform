from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from backend.db.supabase_client import table_select_all, table_upsert
from backend.services.category_engine import assign_category, finalize_category_new
from backend.services.sku_mapper import is_myntra_channel

UNICOMMERCE_SOURCES = {"unicommerce", "sales_master"}


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_unicommerce_myntra_sale(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "").lower()
    return source in UNICOMMERCE_SOURCES and is_myntra_channel(row.get("channel"))


def style_ros_30d(today: date | None = None) -> dict[str, float]:
    today_date = today or date.today()
    start_30d = today_date - timedelta(days=29)
    rows = table_select_all(
        "sales_fact",
        columns="date,style_color,qty,channel,source",
        filters=[("date", f"gte.{start_30d.isoformat()}"), ("date", f"lte.{today_date.isoformat()}")],
        max_rows=500000,
    )
    qty_by_style: dict[str, float] = defaultdict(float)
    for row in rows:
        if _is_unicommerce_myntra_sale(row):
            continue
        style = row.get("style_color")
        day = _to_date(row.get("date"))
        if not style or not day:
            continue
        qty_by_style[str(style)] += float(row.get("qty") or 0)
    return {style: round(qty / 30, 2) for style, qty in qty_by_style.items()}


def rebuild_sku_master_categories() -> dict[str, Any]:
    rows = table_select_all(
        "sku_master",
        columns="style_color,inventory_status,ros,ros_30d,sale_grade_old,is_dog_style",
        max_rows=500000,
    )
    ros_by_style = style_ros_30d()
    updates: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in rows:
        style = str(row.get("style_color") or "")
        ros = float(ros_by_style.get(style, row.get("ros_30d") or row.get("ros") or 0))
        category = finalize_category_new(
            {
                "style_color": style,
                "inventory_status": row.get("inventory_status"),
                "ros": ros,
                "sale_grade_old": row.get("sale_grade_old"),
                "new_category": assign_category(ros),
                "_is_dog_style": row.get("is_dog_style"),
            }
        )
        updates.append({"style_color": style, "category_new": category, "ros": ros, "ros_30d": ros})
        counts[category] += 1
    updated = table_upsert("sku_master", updates, on_conflict="style_color") if updates else 0
    return {
        "status": "success",
        "rows_read": len(rows),
        "rows_updated": updated,
        "breakdown": dict(sorted(counts.items())),
    }
