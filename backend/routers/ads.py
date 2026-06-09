from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter

from backend.routers.common import DEMO_PLA, DEMO_VISIBILITY
from backend.db.supabase_client import table_select_all

router = APIRouter(prefix="/ads", tags=["ads"])


def _window(from_date: date | None = None, to_date: date | None = None) -> tuple[date, date]:
    default_end = date.today() - timedelta(days=1)
    end_date = to_date or default_end
    start_date = from_date or end_date.replace(day=1)
    return start_date, end_date


def _date_filters(column: str, from_date: date | None = None, to_date: date | None = None) -> list[tuple[str, str]]:
    start_date, end_date = _window(from_date, to_date)
    return [(column, f"gte.{start_date.isoformat()}"), (column, f"lte.{end_date.isoformat()}")]


def _dated_rows_or_demo(table: str, demo: list[dict[str, Any]], date_column: str, from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    rows = table_select_all(table, max_rows=500000, filters=_date_filters(date_column, from_date, to_date))
    return rows or demo


@router.get("/pla")
def pla_performance(from_date: date | None = None, to_date: date | None = None):
    return _dated_rows_or_demo("pla_fact", DEMO_PLA, "upload_date", from_date, to_date)


@router.get("/visibility")
def visibility_funnel(from_date: date | None = None, to_date: date | None = None):
    return _dated_rows_or_demo("visibility_fact", DEMO_VISIBILITY, "period_start", from_date, to_date)


@router.get("/problem_skus")
def problem_skus(from_date: date | None = None, to_date: date | None = None):
    pla = _dated_rows_or_demo("pla_fact", DEMO_PLA, "upload_date", from_date, to_date)
    visibility = {
        row.get("style_color"): row
        for row in _dated_rows_or_demo("visibility_fact", DEMO_VISIBILITY, "period_start", from_date, to_date)
    }
    problems = []
    for row in pla:
        style = row.get("style_color")
        vis = visibility.get(style, {})
        label = "Healthy"
        if float(vis.get("return_pct") or 0) > 20:
            label = "High Leakage"
        elif float(row.get("spend") or 0) == 0:
            label = "No Ads"
        elif float(row.get("cvr") or 0) < 1:
            label = "Low CVR"
        problems.append({**row, "problem": label})
    return problems
