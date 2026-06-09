from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from io import StringIO
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.routers.common import DEMO_RETURNS, DEMO_SALES, DEMO_SKUS, exclude_unicommerce_myntra_sales, rows_or_demo
from backend.services.alert_engine import build_alert_count
from backend.services.anomaly_engine import build_anomaly_alerts, filter_anomaly_alerts, summarize_anomaly_alerts
from backend.services.export_safety import safe_row

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field}: {value}") from exc


def _date_filters(column: str, start: date, end: date) -> list[tuple[str, str]]:
    return [(column, f"gte.{start.isoformat()}"), (column, f"lte.{end.isoformat()}")]


def _rows(table: str, columns: str, filters: list[tuple[str, str]] | None = None, demo: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = table_select_all(table, columns=columns, filters=filters, max_rows=500000)
    if rows or get_settings().has_supabase:
        return rows
    return demo or []


def _source_rows(from_date: date | None = None, to_date: date | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], date]:
    effective_today = to_date or date.today()
    history_start = effective_today - timedelta(days=20)
    with ThreadPoolExecutor(max_workers=4) as executor:
        sales_future = executor.submit(
            _rows,
            "sales_fact",
            "date,style_color,channel,source,selling_price,qty",
            _date_filters("date", history_start, effective_today),
            DEMO_SALES,
        )
        returns_future = executor.submit(
            _rows,
            "returns_fact",
            "date,style_color,channel,return_value,qty",
            _date_filters("date", history_start, effective_today),
            DEMO_RETURNS,
        )
        sku_future = executor.submit(
            _rows,
            "sku_master",
            "style_color,category_new,inventory_status,total_inventory,ros,ros_30d,doi",
            None,
            DEMO_SKUS,
        )
        inventory_future = executor.submit(
            _rows,
            "inventory_fact",
            "snapshot_date,style_color,size,qty",
            _date_filters("snapshot_date", history_start, effective_today),
            [],
        )
        sales_rows = sales_future.result()
        return_rows = returns_future.result()
        sku_rows = sku_future.result()
        inventory_rows = inventory_future.result()
    return exclude_unicommerce_myntra_sales(sales_rows), return_rows, sku_rows, inventory_rows, effective_today


def _build_filtered_alerts(
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    category: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    sales_rows, return_rows, sku_rows, inventory_rows, today = _source_rows(from_date=from_date, to_date=to_date)
    alerts = build_anomaly_alerts(
        sales_rows=sales_rows,
        return_rows=return_rows,
        sku_rows=sku_rows,
        inventory_rows=inventory_rows,
        today=today,
    )
    return filter_anomaly_alerts(
        alerts,
        severity=severity,
        alert_type=alert_type,
        category=category,
        status=status,
        scope=scope,
        search=search,
    )


@router.get("/count")
def alerts_count():
    return build_alert_count(rows_or_demo("sku_master", DEMO_SKUS))


@router.get("/anomalies")
def anomaly_alerts(
    from_date: str | None = None,
    to_date: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    category: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    search: str | None = None,
    limit: int = Query(250, ge=1, le=1000),
):
    start_date = _parse_date(from_date, "from_date")
    end_date = _parse_date(to_date, "to_date")
    alerts = _build_filtered_alerts(
        from_date=start_date,
        to_date=end_date,
        severity=severity,
        alert_type=alert_type,
        category=category,
        status=status,
        scope=scope,
        search=search,
    )
    return {"items": alerts[:limit], "summary": summarize_anomaly_alerts(alerts)}


@router.get("/anomalies/download")
def download_anomaly_alerts(
    from_date: str | None = None,
    to_date: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    category: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    search: str | None = None,
):
    start_date = _parse_date(from_date, "from_date")
    end_date = _parse_date(to_date, "to_date")
    alerts = _build_filtered_alerts(
        from_date=start_date,
        to_date=end_date,
        severity=severity,
        alert_type=alert_type,
        category=category,
        status=status,
        scope=scope,
        search=search,
    )
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        safe_row([
            "Severity",
            "Alert Type",
            "Scope",
            "Style/Category",
            "Category",
            "Status",
            "Sales Recent",
            "Sales Baseline",
            "Sales Delta %",
            "Return Recent Qty",
            "Return Baseline Qty",
            "Return Delta %",
            "Return % Recent",
            "Inventory",
            "Expected Inventory",
            "Inventory Delta %",
            "SKU Count Current",
            "SKU Count Baseline",
            "SKU Count Delta %",
            "Reason",
            "Action",
        ])
    )
    for row in alerts:
        writer.writerow(
            safe_row([
                row.get("severity"),
                row.get("alert_type"),
                row.get("scope"),
                row.get("style_color") or row.get("category_subject") or row.get("category"),
                row.get("category"),
                row.get("status"),
                row.get("sales_recent_qty"),
                row.get("sales_baseline_qty"),
                row.get("sales_delta_pct"),
                row.get("return_recent_qty"),
                row.get("return_baseline_qty"),
                row.get("return_delta_pct"),
                row.get("return_pct_recent"),
                row.get("current_inventory"),
                row.get("expected_inventory"),
                row.get("inventory_delta_pct"),
                row.get("sku_count_current"),
                row.get("sku_count_baseline"),
                row.get("sku_count_delta_pct"),
                row.get("reason"),
                row.get("action"),
            ])
        )
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=anomaly-alerts-report.csv"},
    )
