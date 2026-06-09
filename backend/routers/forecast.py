from __future__ import annotations

from datetime import date, timedelta
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.routers.common import DEMO_RETURNS, DEMO_SALES, DEMO_SKUS, rows_or_demo
from backend.services.forecasting import build_sales_returns_forecast

router = APIRouter(prefix="/forecast", tags=["forecast"])
_FORECAST_CACHE: dict[tuple[str, int, int, str, str | None, bool], tuple[float, dict]] = {}
_FORECAST_CACHE_TTL_SECONDS = 60


@router.get("/styles")
def style_forecasts():
    rows = rows_or_demo("sku_master", DEMO_SKUS)
    return [
        {
            "style_color": row["style_color"],
            "forecast_30d": round(float(row.get("ros_30d") or row.get("ros") or 0) * 30, 2),
            "forecast_60d": round(float(row.get("ros_30d") or row.get("ros") or 0) * 60, 2),
            "forecast_90d": round(float(row.get("ros_30d") or row.get("ros") or 0) * 90, 2),
        }
        for row in rows
    ]


@router.get("/sales_returns")
def sales_returns_forecast(
    horizon_days: int = Query(30, ge=1, le=90),
    training_days: int = Query(730, ge=32, le=730),
    model: Literal["auto", "prophet", "sarimax", "arima", "baseline"] = Query("auto"),
    include_diagnostics: bool = Query(True),
    as_of_date: str | None = Query(None),
):
    today_date = date.today()
    requested_as_of: date | None = None
    if as_of_date:
        try:
            requested_as_of = date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="as_of_date must be YYYY-MM-DD") from exc
    query_end = min(requested_as_of or (today_date - timedelta(days=1)), today_date - timedelta(days=1))
    cache_key = (today_date.isoformat(), horizon_days, training_days, model, requested_as_of.isoformat() if requested_as_of else None, include_diagnostics)
    cached = _FORECAST_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < _FORECAST_CACHE_TTL_SECONDS:
        return cached[1]

    start_date = query_end - timedelta(days=training_days - 1)
    filters = [("date", f"gte.{start_date.isoformat()}"), ("date", f"lte.{query_end.isoformat()}")]
    sales_rows = table_select_all(
        "sales_fact",
        columns="date,selling_price,qty,channel,marketplace,source",
        filters=filters,
        page_size=5000,
        max_rows=1000000,
    )
    return_rows = table_select_all(
        "returns_fact",
        columns="date,return_value,qty,channel,source",
        filters=filters,
        page_size=5000,
        max_rows=1000000,
    )
    if not sales_rows and not get_settings().has_supabase:
        sales_rows = DEMO_SALES
    if not return_rows and not get_settings().has_supabase:
        return_rows = DEMO_RETURNS
    result = build_sales_returns_forecast(
        sales_rows,
        return_rows,
        today=today_date,
        as_of_date=requested_as_of,
        horizon_days=horizon_days,
        training_requested_days=training_days,
        model=model,
        include_diagnostics=include_diagnostics,
    )
    result["training_window_days"] = training_days
    _FORECAST_CACHE[cache_key] = (now, result)
    return result
