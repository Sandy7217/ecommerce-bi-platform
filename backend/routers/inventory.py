from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from backend.config import get_settings
from backend.db.supabase_client import table_select_all
from backend.models.schemas import UploadResult
from backend.routers.common import DEMO_RETURNS, DEMO_SALES, DEMO_SKUS, exclude_unicommerce_myntra_sales, paginate, rows_or_demo
from backend.security import MANAGER_ROLES, require_roles
from backend.services.alert_engine import build_replenishment_rows, resolved_doi
from backend.services.category_engine import assign_category, finalize_category_new
from backend.services.export_safety import safe_dict, safe_row
from backend.services.replenishment_engine import (
    build_hybrid_replenishment_plan,
    latest_size_inventory_by_style,
    latest_visibility_ros_by_style,
    size_sales_mix_by_style,
    style_sales_profile_by_style,
)
from backend.services.sku_mapper import extract_style_color

router = APIRouter(prefix="/inventory", tags=["inventory"])

CATEGORY_ORDER = [
    "Green",
    "NOOS",
    "NOOS(Green)",
    "NOOS(Yellow)",
    "NOOS(Red)",
    "NOOS(OOS)",
    "OOS",
    "Red",
    "Yellow",
    "Winter",
    "Discontinue",
    "Potential NOOS",
]

STATUS_ORDER = ["BROKEN", "INSTOCK", "OOS"]

MATRIX_EXPORT_COLUMNS = [
    ("category", "Category"),
    ("sales_value", "Sales Value"),
    ("sales_qty", "Sale Qty"),
    ("return_value", "Return Value"),
    ("return_qty", "Return Qty"),
    ("return_pct", "Return %"),
    ("broken_styles", "Broken Styles"),
    ("broken_pct", "Broken %"),
    ("broken_inventory", "Broken Inv"),
    ("broken_sales_value", "Broken Sale Value"),
    ("broken_sales_qty", "Broken Sale Qty"),
    ("broken_sales_mix_pct", "Broken Sale Mix %"),
    ("broken_return_value", "Broken Return Value"),
    ("broken_return_qty", "Broken Return Qty"),
    ("broken_return_pct", "Broken Return %"),
    ("instock_styles", "Instock Styles"),
    ("instock_pct", "Instock %"),
    ("instock_inventory", "Instock Inv"),
    ("instock_sales_value", "Instock Sale Value"),
    ("instock_sales_qty", "Instock Sale Qty"),
    ("instock_sales_mix_pct", "Instock Sale Mix %"),
    ("instock_return_value", "Instock Return Value"),
    ("instock_return_qty", "Instock Return Qty"),
    ("instock_return_pct", "Instock Return %"),
    ("oos_styles", "OOS Styles"),
    ("oos_pct", "OOS %"),
    ("oos_inventory", "OOS Inv"),
    ("oos_sales_value", "OOS Sale Value"),
    ("oos_sales_qty", "OOS Sale Qty"),
    ("oos_sales_mix_pct", "OOS Sale Mix %"),
    ("oos_return_value", "OOS Return Value"),
    ("oos_return_qty", "OOS Return Qty"),
    ("oos_return_pct", "OOS Return %"),
    ("total_styles", "Total Styles"),
    ("total_inventory", "Total Inv"),
]

STYLE_EXPORT_COLUMNS = [
    ("style_color", "Style"),
    ("category_new", "Category"),
    ("status", "Status"),
    ("total_inventory", "Total Inventory"),
    ("ros_30d", "ROS 30D"),
    ("doi", "DOI"),
    ("priority", "Priority"),
    ("sales_value", "Sales Value"),
    ("sales_qty", "Sale Qty"),
    ("return_value", "Return Value"),
    ("return_qty", "Return Qty"),
    ("return_pct", "Return %"),
]


def _sku_rows() -> list[dict[str, Any]]:
    try:
        rows = table_select_all("sku_master", max_rows=500000)
    except Exception:
        rows = []
    return rows or DEMO_SKUS


def _category_for(row: dict[str, Any]) -> str:
    if row.get("category_new"):
        return str(row["category_new"])
    ros = float(row.get("ros_30d") or row.get("ros") or 0)
    return finalize_category_new({**row, "ros": ros, "new_category": assign_category(ros), "_is_dog_style": row.get("is_dog_style")})


def _matrix_category(category: str) -> str:
    return "Potential NOOS" if category == "NOOS(Potential)" else category


def _categorized_rows() -> list[dict[str, Any]]:
    return [{**row, "category_new": _category_for(row)} for row in _sku_rows()]


def _priority_rank(priority: str | None) -> int:
    value = str(priority or "")
    if value.startswith("P0"):
        return 0
    if value.startswith("P1"):
        return 1
    if value.startswith("P2"):
        return 2
    return 9


def _recommended_qty(row: dict[str, Any]) -> int:
    ros = float(row.get("ros_30d") or row.get("ros") or 0)
    stock = int(row.get("total_inventory") or 0)
    target = get_settings().lead_time_days * ros
    return max(int(round(target - stock)), 0)


def _inventory_doi(row: dict[str, Any]) -> float:
    return resolved_doi(row)


def _window(from_date: date | None = None, to_date: date | None = None) -> tuple[date, date]:
    today = date.today()
    return from_date or today.replace(day=1), to_date or today


def _date_filters(from_date: date | None = None, to_date: date | None = None) -> list[tuple[str, str]]:
    start_date, end_date = _window(from_date, to_date)
    return [("date", f"gte.{start_date.isoformat()}"), ("date", f"lte.{end_date.isoformat()}")]


def _style_key(value: Any) -> str:
    return extract_style_color(value) or ""


def _sales_amount(row: dict[str, Any]) -> float:
    return float(row.get("selling_price") or 0) * int(row.get("qty") or 0)


def _sales_rows(from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    rows = table_select_all(
        "sales_fact",
        columns="date,style_color,internal_sku,selling_price,qty,channel,marketplace,source",
        filters=_date_filters(from_date, to_date),
        max_rows=300000,
    )
    if not rows and not get_settings().has_supabase:
        rows = DEMO_SALES
    return exclude_unicommerce_myntra_sales(rows)


def _return_rows(from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    rows = table_select_all(
        "returns_fact",
        columns="date,style_color,internal_sku,return_value,qty,channel",
        filters=_date_filters(from_date, to_date),
        max_rows=300000,
    )
    if not rows and not get_settings().has_supabase:
        rows = DEMO_RETURNS
    return rows


def _category_by_style(rows: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in rows:
        key = _style_key(row.get("style_color"))
        if key:
            lookup[key] = _matrix_category(str(row.get("category_new") or "Unknown"))
    return lookup


def _style_inventory_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        key = _style_key(row.get("style_color"))
        if key:
            lookup[key] = {
                "category": _matrix_category(str(row.get("category_new") or "Unknown")),
                "status": str(row.get("inventory_status") or "UNKNOWN"),
            }
    return lookup


def _metric_style_key(row: dict[str, Any]) -> str:
    for column in ("style_color", "internal_sku"):
        key = _style_key(row.get(column))
        if key:
            return key
    return ""


def _metric_group(row: dict[str, Any], lookup: dict[str, dict[str, str]]) -> tuple[str, str, str]:
    key = _metric_style_key(row)
    info = lookup.get(key, {})
    return key, info.get("category", "Unknown"), info.get("status", "UNKNOWN")


def _empty_metric() -> dict[str, float]:
    return {"sales_value": 0.0, "sales_qty": 0.0, "return_value": 0.0, "return_qty": 0.0}


def _status_metric_fields(metrics: dict[str, dict[str, float]], total_sales_qty: float) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for status in STATUS_ORDER:
        prefix = status.lower()
        item = metrics.get(status, _empty_metric())
        sales_qty = item.get("sales_qty", 0.0)
        return_qty = item.get("return_qty", 0.0)
        output[f"{prefix}_sales_value"] = round(item.get("sales_value", 0.0), 2)
        output[f"{prefix}_sales_qty"] = int(sales_qty)
        output[f"{prefix}_sales_mix_pct"] = round(sales_qty * 100 / max(total_sales_qty, 1), 2)
        output[f"{prefix}_return_value"] = round(item.get("return_value", 0.0), 2)
        output[f"{prefix}_return_qty"] = int(return_qty)
        output[f"{prefix}_return_pct"] = round(return_qty * 100 / max(sales_qty, 1), 2)
    return output


def _sales_return_metrics(
    rows: list[dict[str, Any]],
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, dict[str, float]]], dict[str, dict[str, float]]]:
    lookup = _style_inventory_lookup(rows)
    category_metrics: dict[str, dict[str, float]] = defaultdict(_empty_metric)
    status_metrics: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(_empty_metric))
    style_metrics: dict[str, dict[str, float]] = defaultdict(_empty_metric)

    for row in _sales_rows(from_date, to_date):
        style_key, category, status = _metric_group(row, lookup)
        amount = _sales_amount(row)
        qty = int(row.get("qty") or 0)
        category_metrics[category]["sales_value"] += amount
        category_metrics[category]["sales_qty"] += qty
        status_metrics[category][status]["sales_value"] += amount
        status_metrics[category][status]["sales_qty"] += qty
        if style_key:
            style_metrics[style_key]["sales_value"] += amount
            style_metrics[style_key]["sales_qty"] += qty

    for row in _return_rows(from_date, to_date):
        style_key, category, status = _metric_group(row, lookup)
        amount = float(row.get("return_value") or 0)
        qty = float(row.get("qty") or 0)
        category_metrics[category]["return_value"] += amount
        category_metrics[category]["return_qty"] += qty
        status_metrics[category][status]["return_value"] += amount
        status_metrics[category][status]["return_qty"] += qty
        if style_key:
            style_metrics[style_key]["return_value"] += amount
            style_metrics[style_key]["return_qty"] += qty

    return category_metrics, status_metrics, style_metrics


def _safe_table_rows(table: str, columns: str = "*", filters: list[tuple[str, str]] | None = None, max_rows: int = 50000) -> list[dict[str, Any]]:
    try:
        return table_select_all(table, columns=columns, filters=filters, max_rows=max_rows)
    except Exception:
        return []


def _hybrid_replenishment_plan() -> dict[str, Any]:
    today_date = date.today()
    sales_start = today_date - timedelta(days=89)
    inventory_start = today_date - timedelta(days=14)
    visibility_start = today_date - timedelta(days=89)
    replenishment_rows = _safe_table_rows(
        "replenishment_log",
        columns="style_color,replenishment_qty,replenishment_date,status",
        max_rows=100000,
    )
    inventory_rows = _safe_table_rows(
        "inventory_fact",
        columns="snapshot_date,style_color,size,qty",
        filters=[("snapshot_date", f"gte.{inventory_start.isoformat()}"), ("snapshot_date", f"lte.{today_date.isoformat()}")],
        max_rows=100000,
    )
    sales_rows = exclude_unicommerce_myntra_sales(
        _safe_table_rows(
            "sales_fact",
            columns="date,style_color,internal_sku,size,qty,channel,source",
            filters=[("date", f"gte.{sales_start.isoformat()}"), ("date", f"lte.{today_date.isoformat()}")],
            max_rows=100000,
        )
    )
    visibility_rows = _safe_table_rows(
        "visibility_fact",
        columns="period_start,period_end,style_color,ros",
        filters=[("period_start", f"gte.{visibility_start.isoformat()}"), ("period_start", f"lte.{today_date.isoformat()}")],
        max_rows=50000,
    )
    return build_hybrid_replenishment_plan(
        _categorized_rows(),
        manual_replenishment_rows=replenishment_rows,
        size_inventory_by_style=latest_size_inventory_by_style(inventory_rows),
        size_sales_by_style=size_sales_mix_by_style(sales_rows),
        style_sales_profile_by_style=style_sales_profile_by_style(sales_rows, today=today_date),
        visibility_ros_by_style=latest_visibility_ros_by_style(visibility_rows),
        lead_time_days=get_settings().lead_time_days,
        review_cycle_days=15,
        today=today_date,
    )


@router.get("/kpis")
def inventory_kpis():
    rows = _sku_rows()
    total = len(rows) or 1
    oos = len([row for row in rows if row.get("inventory_status") == "OOS"])
    broken = len([row for row in rows if row.get("inventory_status") == "BROKEN"])
    instock = len([row for row in rows if row.get("inventory_status") == "INSTOCK"])
    low_stock = len(
        [
            row
            for row in build_replenishment_rows(rows)
            if _priority_rank(row.get("priority")) <= 2
        ]
    )
    return {
        "total_inventory": sum(int(row.get("total_inventory") or 0) for row in rows),
        "total_styles": len(rows),
        "oos_pct": round(oos * 100 / total, 2),
        "broken_pct": round(broken * 100 / total, 2),
        "instock_pct": round(instock * 100 / total, 2),
        "oos_count": oos,
        "broken_count": broken,
        "instock_count": instock,
        "low_stock_alerts": low_stock,
    }


@router.get("/styles")
def inventory_styles(status: str | None = None, category: str | None = None, priority: str | None = None, page: int = 1, limit: int = Query(50, le=200)):
    rows = _categorized_rows()
    if status:
        rows = [row for row in rows if row.get("inventory_status") == status]
    if category:
        rows = [row for row in rows if row.get("category_new") == category or _matrix_category(str(row.get("category_new"))) == category]
    rows = build_replenishment_rows(rows)
    if priority:
        rows = [row for row in rows if row.get("priority") == priority]
    return paginate(
        [
            {
                "style_color": row["style_color"],
                "total_inventory": row.get("total_inventory", 0),
                "status": row.get("inventory_status", "UNKNOWN"),
                "ros_30d": row.get("ros_30d", 0),
                "doi": _inventory_doi(row),
                "priority": row.get("priority"),
                "category_new": row.get("category_new"),
                "replenishment_qty": row.get("replenishment_qty") or _recommended_qty(row),
            }
            for row in rows
        ],
        page,
        limit,
    )


@router.get("/replenishment_plan")
def replenishment_plan(
    status: str | None = None,
    category: str | None = None,
    urgency: str | None = None,
    page: int = 1,
    limit: int = Query(200, le=500),
):
    plan = _hybrid_replenishment_plan()
    items = plan["items"]
    if status:
        items = [row for row in items if str(row.get("inventory_status") or "").upper() == status.upper()]
    if category:
        items = [row for row in items if row.get("category_new") == category]
    if urgency:
        items = [row for row in items if str(row.get("urgency") or "").startswith(urgency)]
    return {
        "summary": plan["summary"],
        "charts": plan["charts"],
        **paginate(items, page, limit),
    }


@router.get("/category_status_matrix")
def category_status_matrix(from_date: date | None = None, to_date: date | None = None):
    rows = _categorized_rows()
    matrix: dict[str, dict[str, dict[str, int]]] = {
        category: {status: {"styles": 0, "inventory": 0} for status in STATUS_ORDER}
        for category in CATEGORY_ORDER
    }
    category_metrics, status_metrics, _ = _sales_return_metrics(rows, from_date, to_date)

    for row in rows:
        category = _matrix_category(str(row.get("category_new") or "Unknown"))
        if category not in matrix:
            matrix[category] = {status: {"styles": 0, "inventory": 0} for status in STATUS_ORDER}
        status = str(row.get("inventory_status") or "UNKNOWN")
        if status not in matrix[category]:
            matrix[category][status] = {"styles": 0, "inventory": 0}
        matrix[category][status]["styles"] += 1
        matrix[category][status]["inventory"] += int(row.get("total_inventory") or 0)

    result: list[dict[str, Any]] = []
    grand = {status: {"styles": 0, "inventory": 0} for status in STATUS_ORDER}
    grand_status_metrics: dict[str, dict[str, float]] = defaultdict(_empty_metric)
    metric_categories = set(category_metrics)
    for category in CATEGORY_ORDER + sorted((set(matrix) | metric_categories) - set(CATEGORY_ORDER)):
        statuses = matrix.get(category, {status: {"styles": 0, "inventory": 0} for status in STATUS_ORDER})
        total_styles = sum(statuses.get(status, {}).get("styles", 0) for status in STATUS_ORDER)
        total_inventory = sum(statuses.get(status, {}).get("inventory", 0) for status in STATUS_ORDER)
        metrics = category_metrics.get(category, _empty_metric())
        sales_qty = metrics.get("sales_qty", 0.0)
        return_qty = metrics.get("return_qty", 0.0)
        output: dict[str, Any] = {
            "category": category,
            "sales_value": round(metrics.get("sales_value", 0.0), 2),
            "sales_qty": int(sales_qty),
            "return_value": round(metrics.get("return_value", 0.0), 2),
            "return_qty": int(return_qty),
            "return_pct": round(return_qty * 100 / max(sales_qty, 1), 2),
            "total_styles": total_styles,
            "total_inventory": total_inventory,
        }
        output.update(_status_metric_fields(status_metrics.get(category, {}), sales_qty))
        for status in STATUS_ORDER:
            styles = statuses.get(status, {}).get("styles", 0)
            inventory = statuses.get(status, {}).get("inventory", 0)
            grand[status]["styles"] += styles
            grand[status]["inventory"] += inventory
            status_metric = status_metrics.get(category, {}).get(status, _empty_metric())
            for key in ("sales_value", "sales_qty", "return_value", "return_qty"):
                grand_status_metrics[status][key] += status_metric.get(key, 0.0)
            prefix = status.lower()
            output[f"{prefix}_styles"] = styles
            output[f"{prefix}_pct"] = round(styles * 100 / max(total_styles, 1), 2)
            output[f"{prefix}_inventory"] = inventory
        result.append(output)

    grand_total_styles = sum(item["styles"] for item in grand.values())
    grand_sales_value = sum(item.get("sales_value", 0.0) for item in category_metrics.values())
    grand_sales_qty = sum(item.get("sales_qty", 0.0) for item in category_metrics.values())
    grand_return_value = sum(item.get("return_value", 0.0) for item in category_metrics.values())
    grand_return_qty = sum(item.get("return_qty", 0.0) for item in category_metrics.values())
    grand_row: dict[str, Any] = {
        "category": "Grand Total",
        "sales_value": round(grand_sales_value, 2),
        "sales_qty": int(grand_sales_qty),
        "return_value": round(grand_return_value, 2),
        "return_qty": int(grand_return_qty),
        "return_pct": round(grand_return_qty * 100 / max(grand_sales_qty, 1), 2),
        "total_styles": grand_total_styles,
        "total_inventory": sum(item["inventory"] for item in grand.values()),
    }
    grand_row.update(_status_metric_fields(grand_status_metrics, grand_sales_qty))
    for status in STATUS_ORDER:
        prefix = status.lower()
        grand_row[f"{prefix}_styles"] = grand[status]["styles"]
        grand_row[f"{prefix}_pct"] = round(grand[status]["styles"] * 100 / max(grand_total_styles, 1), 2)
        grand_row[f"{prefix}_inventory"] = grand[status]["inventory"]
    result.append(grand_row)
    return result


def _category_style_detail_rows(category: str | None = None, from_date: date | None = None, to_date: date | None = None) -> list[dict[str, Any]]:
    rows = _categorized_rows()
    _, _, style_metrics = _sales_return_metrics(rows, from_date, to_date)
    if category and category != "Grand Total":
        rows = [row for row in rows if row.get("category_new") == category or _matrix_category(str(row.get("category_new"))) == category]
    rows = build_replenishment_rows(rows)
    rows = sorted(
        rows,
        key=lambda row: (
            _matrix_category(str(row.get("category_new") or "Unknown")),
            str(row.get("inventory_status") or ""),
            str(row.get("style_color") or ""),
        ),
    )
    output: list[dict[str, Any]] = []
    for row in rows:
        style_key = _style_key(row.get("style_color"))
        metrics = style_metrics.get(style_key, {})
        sales_qty = metrics.get("sales_qty", 0.0)
        return_qty = metrics.get("return_qty", 0.0)
        output.append({
            "style_color": row.get("style_color"),
            "category_new": _matrix_category(str(row.get("category_new") or "Unknown")),
            "status": row.get("inventory_status", "UNKNOWN"),
            "total_inventory": row.get("total_inventory", 0),
            "ros_30d": row.get("ros_30d", 0),
            "doi": _inventory_doi(row),
            "priority": row.get("priority"),
            "sales_value": round(metrics.get("sales_value", 0.0), 2),
            "sales_qty": int(sales_qty),
            "return_value": round(metrics.get("return_value", 0.0), 2),
            "return_qty": int(return_qty),
            "return_pct": round(return_qty * 100 / max(sales_qty, 1), 2),
        })
    return output


def _cell_text(value: Any) -> str:
    return "" if value is None else str(value)


def _write_workbook_sheet(workbook: Workbook, title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]], *, active: bool = False) -> None:
    worksheet = workbook.active if active else workbook.create_sheet()
    worksheet.title = title
    worksheet.append(safe_row([label for _, label in columns]))
    for row in rows:
        worksheet.append(safe_row([row.get(key) for key, _ in columns]))
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for column_cells in worksheet.columns:
        max_length = max(len(_cell_text(cell.value)) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 34)


def _category_status_matrix_workbook(from_date: date | None = None, to_date: date | None = None) -> bytes:
    workbook = Workbook()
    _write_workbook_sheet(workbook, "Category Matrix", MATRIX_EXPORT_COLUMNS, category_status_matrix(from_date, to_date), active=True)
    _write_workbook_sheet(workbook, "Style Details", STYLE_EXPORT_COLUMNS, _category_style_detail_rows("Grand Total", from_date, to_date))
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


@router.get("/category_status_matrix/download")
def download_category_status_matrix(from_date: date | None = None, to_date: date | None = None):
    payload = _category_status_matrix_workbook(from_date, to_date)
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=category-status-matrix.xlsx"},
    )


@router.get("/category_styles")
def category_styles(category: str, from_date: date | None = None, to_date: date | None = None, page: int = 1, limit: int = Query(200, le=500)):
    return paginate(
        _category_style_detail_rows(category, from_date, to_date),
        page,
        limit,
    )


@router.get("/download_replenishment")
def download_replenishment():
    output = StringIO()
    fieldnames = [
        "style_color",
        "category",
        "status",
        "total_inventory",
        "ros_7d",
        "ros_30d",
        "predicted_ros",
        "target_stock",
        "pending_replenishment_qty",
        "sales_qty_90d",
        "replenishment_reason",
        "urgency",
        "stockout_date",
        "order_by_date",
        "recommended_qty",
        "size_replenishment",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in _hybrid_replenishment_plan()["items"]:
        size_text = "; ".join(
            f"{size_row.get('size')}:{size_row.get('recommended_qty')}"
            for size_row in row.get("size_replenishment") or []
        )
        writer.writerow(
            safe_dict({
                "style_color": row.get("style_color"),
                "category": row.get("category_new"),
                "status": row.get("inventory_status"),
                "total_inventory": row.get("total_inventory") or 0,
                "ros_7d": row.get("ros_7d") or 0,
                "ros_30d": row.get("ros_30d") or 0,
                "predicted_ros": row.get("predicted_ros") or 0,
                "target_stock": row.get("target_stock") or 0,
                "pending_replenishment_qty": row.get("pending_replenishment_qty") or 0,
                "sales_qty_90d": row.get("sales_qty_90d") or 0,
                "replenishment_reason": row.get("replenishment_reason") or "",
                "urgency": row.get("urgency"),
                "stockout_date": row.get("stockout_date"),
                "order_by_date": row.get("order_by_date"),
                "recommended_qty": row.get("recommended_replenishment_qty") or 0,
                "size_replenishment": size_text,
            })
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=replenishment_plan.csv"},
    )


@router.get("/replenishment")
def replenishment_history(
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    limit: int = Query(50, le=200),
):
    rows = rows_or_demo("replenishment_log", [])
    if status:
        rows = [row for row in rows if str(row.get("status") or "").lower() == status.lower()]
    if from_date:
        rows = [
            row
            for row in rows
            if row.get("replenishment_date") and date.fromisoformat(str(row["replenishment_date"])[:10]) >= from_date
        ]
    if to_date:
        rows = [
            row
            for row in rows
            if row.get("replenishment_date") and date.fromisoformat(str(row["replenishment_date"])[:10]) <= to_date
        ]
    rows = sorted(rows, key=lambda row: str(row.get("replenishment_date") or ""), reverse=True)
    return paginate(rows, page, limit)


@router.post("/replenishment/upload", response_model=UploadResult, dependencies=[Depends(require_roles(*MANAGER_ROLES))])
async def upload_replenishment(file: UploadFile = File(...)):
    settings = get_settings()
    file_name = file.filename or "upload"
    if Path(file_name).suffix.lower() not in settings.allowed_upload_extensions:
        return UploadResult(status="error", rows_processed=0, rows_inserted=0, rows_skipped=0, errors=["Unsupported upload type"])
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        return UploadResult(status="error", rows_processed=0, rows_inserted=0, rows_skipped=0, errors=["Upload is too large"])
    return UploadResult(status="success", rows_processed=0, rows_inserted=0, rows_skipped=0, errors=[f"{file.filename} accepted; configure Supabase to persist uploads ({len(content)} bytes)."])
