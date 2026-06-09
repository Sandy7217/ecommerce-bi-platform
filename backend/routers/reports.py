from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from io import BytesIO, StringIO
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.routers.common import DEMO_RETURNS, DEMO_SALES, DEMO_SKUS, exclude_unicommerce_myntra_sales
from backend.services.alert_engine import build_replenishment_rows, resolved_doi
from backend.services.anomaly_engine import build_anomaly_alerts
from backend.services.dsr_report import build_dsr_report, generate_dsr_excel, generate_dsr_png
from backend.services.export_safety import safe_row

router = APIRouter(prefix="/reports", tags=["reports"])

ReportFormat = Literal["csv", "excel", "xlsx"]
DsrFormat = Literal["excel", "xlsx", "png", "image"]


def _month_window(from_date: date | None = None, to_date: date | None = None) -> tuple[date, date]:
    default_end = date.today() - timedelta(days=1)
    end_date = to_date or default_end
    start_date = from_date or end_date.replace(day=1)
    return start_date, end_date


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}") from exc


def _date_filters(from_date: date | None = None, to_date: date | None = None) -> list[tuple[str, str]]:
    start_date, end_date = _month_window(from_date, to_date)
    return [("date", f"gte.{start_date.isoformat()}"), ("date", f"lte.{end_date.isoformat()}")]


def _column_date_filters(column: str, from_date: date, to_date: date) -> list[tuple[str, str]]:
    return [(column, f"gte.{from_date.isoformat()}"), (column, f"lte.{to_date.isoformat()}")]


def _rows(table: str, columns: str = "*", filters: list[tuple[str, str]] | None = None, demo: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = table_select_all(table, columns=columns, filters=filters, max_rows=500000)
    if rows or get_settings().has_supabase:
        return rows
    return demo or []


def _sales_amount(row: dict[str, Any]) -> float:
    return float(row.get("selling_price") or 0) * int(row.get("qty") or 0)


def _recommended_qty(row: dict[str, Any]) -> int:
    ros = float(row.get("ros_30d") or row.get("ros") or 0)
    stock = int(row.get("total_inventory") or 0)
    target = get_settings().lead_time_days * ros
    return max(int(round(target - stock)), 0)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _latest_row_date(*row_groups: tuple[list[dict[str, Any]], str], fallback: date) -> date:
    dates: list[date] = []
    for rows, column in row_groups:
        for row in rows:
            value = row.get(column)
            if not value:
                continue
            try:
                dates.append(date.fromisoformat(str(value)[:10]))
            except ValueError:
                continue
    return max(dates, default=fallback)


def _sales_report(from_date: date | None, to_date: date | None) -> tuple[str, list[str], list[list[Any]]]:
    columns = ["Date", "SKU", "Style Color", "Channel", "Marketplace", "Selling Price", "MRP", "Discount", "Qty", "Order ID", "State", "City"]
    rows = _rows(
        "sales_fact",
        columns="date,internal_sku,style_color,channel,marketplace,selling_price,mrp,discount,qty,order_id,state,city",
        filters=_date_filters(from_date, to_date),
        demo=DEMO_SALES,
    )
    data = [
        [
            row.get("date"),
            row.get("internal_sku"),
            row.get("style_color"),
            row.get("channel"),
            row.get("marketplace"),
            row.get("selling_price"),
            row.get("mrp"),
            row.get("discount"),
            row.get("qty"),
            row.get("order_id"),
            row.get("state"),
            row.get("city"),
        ]
        for row in rows
    ]
    return "MTD Sales Report", columns, data


def _inventory_report() -> tuple[str, list[str], list[list[Any]]]:
    columns = ["Style Color", "Category", "Sale Grade", "Inventory Status", "Total Inventory", "ROS 30D", "DOI", "Priority"]
    rows = build_replenishment_rows(
        _rows(
            "sku_master",
            columns="style_color,category_new,sale_grade_old,inventory_status,total_inventory,ros,ros_30d,doi",
            demo=DEMO_SKUS,
        )
    )
    data = [
        [
            row.get("style_color"),
            row.get("category_new"),
            row.get("sale_grade_old"),
            row.get("inventory_status"),
            row.get("total_inventory"),
            row.get("ros_30d"),
            resolved_doi(row),
            row.get("priority"),
        ]
        for row in rows
    ]
    return "Inventory Report", columns, data


def _replenishment_report() -> tuple[str, list[str], list[list[Any]]]:
    columns = ["Style Color", "Category", "Status", "Total Inventory", "ROS 30D", "DOI", "Priority", "Recommended Qty"]
    rows = build_replenishment_rows(
        _rows(
            "sku_master",
            columns="style_color,category_new,sale_grade_old,inventory_status,total_inventory,ros,ros_30d,doi",
            demo=DEMO_SKUS,
        )
    )
    rows = [row for row in rows if str(row.get("priority") or "").startswith(("P0", "P1"))]
    data = [
        [
            row.get("style_color"),
            row.get("category_new"),
            row.get("inventory_status"),
            row.get("total_inventory"),
            row.get("ros_30d"),
            resolved_doi(row),
            row.get("priority"),
            _recommended_qty(row),
        ]
        for row in rows
    ]
    return "Replenishment Report", columns, data


def _returns_report(from_date: date | None, to_date: date | None) -> tuple[str, list[str], list[list[Any]]]:
    columns = ["Date", "SKU", "Style Color", "Channel", "Return Qty", "Return Value", "Return Type", "State"]
    rows = _rows(
        "returns_fact",
        columns="date,internal_sku,style_color,channel,qty,return_value,return_type,state",
        filters=_date_filters(from_date, to_date),
        demo=DEMO_RETURNS,
    )
    data = [
        [
            row.get("date"),
            row.get("internal_sku"),
            row.get("style_color"),
            row.get("channel"),
            row.get("qty"),
            row.get("return_value"),
            row.get("return_type"),
            row.get("state"),
        ]
        for row in rows
    ]
    return "Returns Report", columns, data


def _category_analysis_report(from_date: date | None, to_date: date | None) -> tuple[str, list[str], list[list[Any]]]:
    columns = ["Style Color", "Old Sale Grade", "New Category", "Inventory Status", "Total Inventory", "ROS", "MTD Sales"]
    sku_rows = _rows(
        "sku_master",
        columns="style_color,sale_grade_old,category_new,inventory_status,total_inventory,ros,ros_30d,doi",
        demo=DEMO_SKUS,
    )
    sales_rows = _rows(
        "sales_fact",
        columns="date,style_color,selling_price,qty",
        filters=_date_filters(from_date, to_date),
        demo=DEMO_SALES,
    )
    sales_by_style: dict[str, float] = {}
    for row in sales_rows:
        style = _text(row.get("style_color"))
        if style:
            sales_by_style[style] = sales_by_style.get(style, 0.0) + _sales_amount(row)

    data = [
        [
            row.get("style_color"),
            row.get("sale_grade_old"),
            row.get("category_new"),
            row.get("inventory_status"),
            row.get("total_inventory"),
            row.get("ros"),
            round(sales_by_style.get(_text(row.get("style_color")), 0.0), 2),
        ]
        for row in sku_rows
    ]
    return "Category Analysis Report", columns, data


def _anomaly_alerts_report(from_date: date | None, to_date: date | None) -> tuple[str, list[str], list[list[Any]]]:
    today = to_date or date.today()
    history_start = today - timedelta(days=20)
    with ThreadPoolExecutor(max_workers=4) as executor:
        sales_future = executor.submit(
            _rows,
            "sales_fact",
            "date,style_color,channel,source,selling_price,qty",
            _column_date_filters("date", history_start, today),
            DEMO_SALES,
        )
        returns_future = executor.submit(
            _rows,
            "returns_fact",
            "date,style_color,channel,return_value,qty",
            _column_date_filters("date", history_start, today),
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
            _column_date_filters("snapshot_date", history_start, today),
            [],
        )
        sales_rows = exclude_unicommerce_myntra_sales(sales_future.result())
        return_rows = returns_future.result()
        sku_rows = sku_future.result()
        inventory_rows = inventory_future.result()
    if to_date is None:
        today = _latest_row_date(
            (sales_rows, "date"),
            (return_rows, "date"),
            (inventory_rows, "snapshot_date"),
            fallback=today,
        )
    alerts = build_anomaly_alerts(
        sales_rows=sales_rows,
        return_rows=return_rows,
        sku_rows=sku_rows,
        inventory_rows=inventory_rows,
        today=today,
    )
    columns = [
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
    ]
    data = [
        [
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
        ]
        for row in alerts
    ]
    return "Anomaly Alerts Report", columns, data


def _report_payload(report_type: str, from_date: date | None, to_date: date | None) -> tuple[str, list[str], list[list[Any]]]:
    normalized = report_type.strip().lower().replace("-", "_")
    if normalized in {"sales", "mtd_sales"}:
        return _sales_report(from_date, to_date)
    if normalized == "inventory":
        return _inventory_report()
    if normalized == "replenishment":
        return _replenishment_report()
    if normalized in {"returns", "return"}:
        return _returns_report(from_date, to_date)
    if normalized in {"category", "categories", "category_analysis"}:
        return _category_analysis_report(from_date, to_date)
    if normalized in {"anomaly_alerts", "anomalies", "alerts"}:
        return _anomaly_alerts_report(from_date, to_date)
    raise HTTPException(status_code=400, detail=f"Unsupported report type: {report_type}")


def _csv_bytes(headers: list[str], rows: list[list[Any]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(safe_row(headers))
    writer.writerows(safe_row(row) for row in rows)
    return output.getvalue().encode("utf-8-sig")


def _excel_bytes(title: str, headers: list[str], rows: list[list[Any]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = title[:31]
    worksheet.append(safe_row(headers))
    for row in rows:
        worksheet.append(safe_row(row))
    for column_cells in worksheet.columns:
        max_length = max(len(_text(cell.value)) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 36)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


def _filename(title: str, report_format: ReportFormat) -> str:
    slug = title.lower().replace(" ", "-")
    extension = "xlsx" if report_format in {"excel", "xlsx"} else "csv"
    return f"{slug}.{extension}"


@router.get("/download")
def download_report(
    type: str,
    format: ReportFormat = "csv",
    from_date: str | None = None,
    to_date: str | None = None,
):
    start_date = _parse_date(from_date)
    end_date = _parse_date(to_date)
    title, headers, rows = _report_payload(type, start_date, end_date)
    filename = _filename(title, format)
    if format == "csv":
        payload = _csv_bytes(headers, rows)
        media_type = "text/csv"
    else:
        payload = _excel_bytes(title, headers, rows)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return StreamingResponse(
        BytesIO(payload),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/dsr")
def dsr_report(date: str):
    report_date = _parse_date(date)
    if report_date is None:
        raise HTTPException(status_code=400, detail="date is required")
    return build_dsr_report(report_date)


@router.get("/dsr/download")
def download_dsr_report(date: str, format: DsrFormat = "excel"):
    report_date = _parse_date(date)
    if report_date is None:
        raise HTTPException(status_code=400, detail="date is required")
    report = build_dsr_report(report_date)
    normalized_format = "png" if format in {"png", "image"} else "excel"
    if normalized_format == "png":
        payload = generate_dsr_png(report)
        media_type = "image/png"
        filename = f"dsr-report-{report_date.isoformat()}.png"
    else:
        payload = generate_dsr_excel(report)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"dsr-report-{report_date.isoformat()}.xlsx"
    return StreamingResponse(
        BytesIO(payload),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
