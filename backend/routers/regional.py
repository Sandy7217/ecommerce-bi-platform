from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.routers.common import DEMO_RETURNS, DEMO_SALES, exclude_unicommerce_myntra_sales, rows_or_demo

router = APIRouter(prefix="/regional", tags=["regional"])


def _date_filters(from_date: date | None = None, to_date: date | None = None) -> list[tuple[str, str]]:
    default_end = date.today() - timedelta(days=1)
    end_date = to_date or default_end
    start_date = from_date or end_date.replace(day=1)
    return [("date", f"gte.{start_date.isoformat()}"), ("date", f"lte.{end_date.isoformat()}")]


def _sales_amount(row: dict[str, Any]) -> float:
    return float(row.get("selling_price") or 0) * int(row.get("qty") or 1)


def _state_key(value: Any) -> str:
    text = str(value or "Unknown").strip()
    aliases = {
        "Ct": "Chhattisgarh",
        "Jammu & Kashmir": "Jammu and Kashmir",
        "Dadra & Nagar Haveli": "Dadra and Nagar Haveli",
        "Andaman & Nicobar Islands": "Andaman and Nicobar Islands",
    }
    return aliases.get(text, text)


def _sales_rows(from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    sales = table_select_all(
        "sales_fact",
        columns="date,selling_price,qty,state,source,channel,style_color,internal_sku",
        filters=_date_filters(from_date, to_date),
        max_rows=300000,
    )
    if not sales and not get_settings().has_supabase:
        sales = DEMO_SALES
    return exclude_unicommerce_myntra_sales(sales)


def _return_rows(from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    returns = table_select_all(
        "returns_fact",
        columns="date,return_value,qty,state,style_color,internal_sku",
        filters=_date_filters(from_date, to_date),
        max_rows=300000,
    )
    if not returns and not get_settings().has_supabase:
        returns = DEMO_RETURNS
    return returns


@router.get("/states")
def states(from_date: date | None = None, to_date: date | None = None):
    sales = _sales_rows(from_date, to_date)
    returns = _return_rows(from_date, to_date)
    return_by_state: dict[str, float] = defaultdict(float)
    return_qty_by_state: dict[str, int] = defaultdict(int)
    for row in returns:
        state = _state_key(row.get("state"))
        return_by_state[state] += float(row.get("return_value") or 0)
        return_qty_by_state[state] += int(row.get("qty") or 0)
    grouped: dict[str, dict[str, float | int]] = defaultdict(lambda: {"sales": 0.0, "qty": 0})
    for row in sales:
        state = _state_key(row.get("state"))
        grouped[state]["sales"] = float(grouped[state]["sales"]) + _sales_amount(row)
        grouped[state]["qty"] = int(grouped[state]["qty"]) + int(row.get("qty") or 0)
    return [
        {"state": state, "sales": data["sales"], "qty": data["qty"], "return_pct": round(return_qty_by_state[state] * 100 / max(int(data["qty"]), 1), 2)}
        for state, data in grouped.items()
    ]


@router.get("/state_heatmap")
def state_heatmap(from_date: date | None = None, to_date: date | None = None):
    sales = _sales_rows(from_date, to_date)
    returns = _return_rows(from_date, to_date)
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "state": "Unknown",
            "sales": 0.0,
            "qty": 0,
            "return_value": 0.0,
            "return_qty": 0,
            "top_styles_map": defaultdict(lambda: {"style_color": "Unknown", "sales": 0.0, "qty": 0}),
        }
    )

    for row in sales:
        state = _state_key(row.get("state"))
        style = str(row.get("style_color") or row.get("internal_sku") or "Unknown")
        amount = _sales_amount(row)
        qty = int(row.get("qty") or 0)
        grouped[state]["state"] = state
        grouped[state]["sales"] = float(grouped[state]["sales"]) + amount
        grouped[state]["qty"] = int(grouped[state]["qty"]) + qty
        grouped[state]["top_styles_map"][style]["style_color"] = style
        grouped[state]["top_styles_map"][style]["sales"] += amount
        grouped[state]["top_styles_map"][style]["qty"] += qty

    for row in returns:
        state = _state_key(row.get("state"))
        grouped[state]["state"] = state
        grouped[state]["return_value"] = float(grouped[state]["return_value"]) + float(row.get("return_value") or 0)
        grouped[state]["return_qty"] = int(grouped[state]["return_qty"]) + int(row.get("qty") or 0)

    result: list[dict[str, Any]] = []
    for state, data in grouped.items():
        top_styles = sorted(data["top_styles_map"].values(), key=lambda item: item["sales"], reverse=True)[:5]
        qty = int(data["qty"])
        result.append(
            {
                "state": state,
                "sales": round(float(data["sales"]), 2),
                "qty": qty,
                "return_value": round(float(data["return_value"]), 2),
                "return_qty": int(data["return_qty"]),
                "return_pct": round(int(data["return_qty"]) * 100 / qty, 2) if qty else 0.0,
                "top_styles": [
                    {"style_color": item["style_color"], "sales": round(float(item["sales"]), 2), "qty": int(item["qty"])}
                    for item in top_styles
                ],
            }
        )
    return sorted(result, key=lambda row: row["sales"], reverse=True)


@router.get("/cities")
def cities(from_date: date | None = None, to_date: date | None = None):
    sales = table_select_all(
        "sales_fact",
        columns="date,selling_price,qty,city,source,channel",
        filters=_date_filters(from_date, to_date),
        max_rows=300000,
    )
    if not sales and not get_settings().has_supabase:
        sales = DEMO_SALES
    grouped: dict[str, float] = defaultdict(float)
    for row in exclude_unicommerce_myntra_sales(sales):
        grouped[row.get("city") or "Unknown"] += float(row.get("selling_price") or 0)
    return [{"city": key, "sales": value} for key, value in grouped.items()]
