from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from backend.db.supabase_client import table_select, table_select_all
from backend.services.sku_mapper import is_myntra_channel


DEMO_SALES = [
    {"date": date.today().isoformat(), "style_color": "nm1292-navy", "channel": "Myntra", "marketplace": "Myntra", "selling_price": 1499, "qty": 1, "state": "Maharashtra"},
    {"date": date.today().isoformat(), "style_color": "23ssnm001-cherry", "channel": "NYKAA_FASHION", "marketplace": "Nykaa", "selling_price": 1899, "qty": 1, "state": "Delhi"},
    {"date": (date.today() - timedelta(days=1)).isoformat(), "style_color": "nm1301-black", "channel": "AJIO_DROPSHIP", "marketplace": "Ajio", "selling_price": 999, "qty": 2, "state": "Karnataka"},
]

DEMO_SKUS = [
    {"style_color": "nm1292-navy", "category_new": "NOOS", "cross_category": "NOOS", "inventory_status": "INSTOCK", "total_inventory": 420, "ros": 5.2, "ros_7d": 6.1, "ros_30d": 4.4, "doi": 95},
    {"style_color": "23ssnm001-cherry", "category_new": "NOOS(Potential)", "cross_category": "NOOS(Potential)", "inventory_status": "BROKEN", "total_inventory": 70, "ros": 4.8, "ros_7d": 5.5, "ros_30d": 3.1, "doi": 22},
    {"style_color": "nm1301-black", "category_new": "Red", "cross_category": "Red", "inventory_status": "OOS", "total_inventory": 0, "ros": 0.7, "ros_7d": 0.2, "ros_30d": 0.8, "doi": 0},
]

DEMO_RETURNS = [
    {"date": date.today().isoformat(), "style_color": "nm1292-navy", "channel": "Myntra", "return_value": 1499, "qty": 1, "state": "Maharashtra", "return_type": "Customer Return"},
]

DEMO_PLA = [
    {"style_color": "nm1292-navy", "campaign_id": "PLA-001", "campaign_name": "NOOS Push", "spend": 12000, "revenue": 74000, "roi": 6.1, "clicks": 2200, "impressions": 89000, "cvr": 3.4}
]

DEMO_VISIBILITY = [
    {"style_color": "nm1292-navy", "period_start": date.today().isoformat(), "units_sold": 84, "ros": 5.2, "conversion_pct": 3.2, "return_pct": 8.1}
]

UNICOMMERCE_SOURCES = {"unicommerce", "sales_master"}


def rows_or_demo(table: str, demo: list[dict[str, Any]], limit: int = 500000) -> list[dict[str, Any]]:
    rows = table_select_all(table, max_rows=limit) if limit > 1000 else table_select(table, limit=limit)
    return rows or demo


def is_unicommerce_myntra_sale(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "").lower()
    return source in UNICOMMERCE_SOURCES and is_myntra_channel(row.get("channel"))


def exclude_unicommerce_myntra_sales(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if not is_unicommerce_myntra_sale(row)]


def sum_by(rows: list[dict[str, Any]], key: str, value_key: str) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    qty: dict[str, int] = defaultdict(int)
    for row in rows:
        group = row.get(key) or "Unknown"
        totals[group] += float(row.get(value_key) or 0)
        qty[group] += int(row.get("qty") or 0)
    return [{"name": name, "value": value, "qty": qty[name]} for name, value in totals.items()]


def paginate(rows: list[dict[str, Any]], page: int = 1, limit: int = 50) -> dict[str, Any]:
    start = max(page - 1, 0) * limit
    end = start + limit
    return {"items": rows[start:end], "page": page, "limit": limit, "total": len(rows)}
