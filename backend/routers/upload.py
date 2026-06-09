from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from backend.config import get_settings
from backend.db.supabase_client import SupabaseUnavailable, table_insert, table_select_all, table_upsert
from backend.models.schemas import UploadResult
from backend.services.data_ingestion import (
    process_inventory_snapshot,
    process_myntra_orders,
    process_pla_report,
    process_replenishment_upload,
    process_returns,
    process_unicommerce_sales,
    process_visibility_report,
    read_upload_dataframe,
)
from backend.services.category_rebuild import rebuild_sku_master_categories
from backend.services.sku_mapper import build_sale_grade_updates, build_sku_mapping_sale_grade_updates, build_sku_master_map, find_column, normalize_sku

def _enforce_request_size(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if not content_length:
        return
    try:
        size = int(content_length)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Content-Length")
    if size > get_settings().max_upload_bytes + 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Upload is too large")


router = APIRouter(prefix="/upload", tags=["upload"], dependencies=[Depends(_enforce_request_size)])

GRADE_NORMALIZE = {
    "discontinue": "Discontinue",
    "DISCONTINUE": "Discontinue",
    "noos(red)": "NOOS(Red)",
    "NOOS(RED)": "NOOS(Red)",
    "yellow": "Yellow",
    "aw styles": "AW Styles",
    "AW styles": "AW Styles",
    "core winter": "Core Winter",
    "Core winter": "Core Winter",
    "winter noos": "Winter NOOS",
    "potencial noos": "Potential NOOS",
    "Potencial NOOS": "Potential NOOS",
    "red( repeat)": "RED(Repeat)",
    "RED( Repeat)": "RED(Repeat)",
    "new": "New Launch",
    "New": "New Launch",
    "watchlist": "Watchlist",
}


async def _read(file: UploadFile) -> pd.DataFrame:
    settings = get_settings()
    file_name = file.filename or "upload"
    extension = Path(file_name).suffix.lower()
    if extension not in settings.allowed_upload_extensions:
        allowed = ", ".join(sorted(settings.allowed_upload_extensions))
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported upload type. Allowed: {allowed}")
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Upload is too large")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload file is empty")
    return read_upload_dataframe(file_name, content)


async def _sku_map(file: UploadFile | None = None) -> pd.DataFrame:
    if file is not None:
        return await _read(file)
    rows = table_select_all("sku_master_map")
    return pd.DataFrame(rows)


def _error_message(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        text = getattr(response, "text", "")
        status_code = getattr(response, "status_code", "")
        if text:
            return f"{status_code}: {text}"
    return str(exc)


def _dedupe_on_conflict(rows: list[dict], on_conflict: str | None) -> list[dict]:
    if not on_conflict:
        return rows
    columns = [column.strip() for column in on_conflict.split(",") if column.strip()]
    if not columns:
        return rows

    keyed: dict[tuple, dict] = {}
    unkeyed: list[dict] = []
    for row in rows:
        values = tuple(row.get(column) for column in columns)
        if any(value is None or value == "" for value in values):
            unkeyed.append(row)
            continue
        keyed[values] = row
    return unkeyed + list(keyed.values())


def _skip_existing(rows: list[dict], table: str, conflict_key: str | None) -> list[dict]:
    if not conflict_key or not rows:
        return rows
    columns = [column.strip() for column in conflict_key.split(",") if column.strip()]
    existing_rows = table_select_all(table, columns=",".join(columns), max_rows=500000)
    existing_keys = {
        tuple(row.get(column) for column in columns)
        for row in existing_rows
        if all(row.get(column) not in {None, ""} for column in columns)
    }
    if not existing_keys:
        return rows
    return [
        row
        for row in rows
        if any(row.get(column) in {None, ""} for column in columns)
        or tuple(row.get(column) for column in columns) not in existing_keys
    ]


def _is_sales_master(df: pd.DataFrame) -> bool:
    columns = set(df.columns)
    return "Source Type" in columns or ("Order id" in columns and "Reverse Pickup Code" not in columns)


def _normalized_column_set(df: pd.DataFrame) -> set[str]:
    return {str(column).strip().lower().replace("_", " ") for column in df.columns}


def _detect_upload_type(df: pd.DataFrame) -> str:
    columns = _normalized_column_set(df)
    if {"sku", "sale grade"}.issubset(columns):
        return "sale_grade_master"
    if {"order status", "style id", "seller sku code", "created on", "final amount"}.issubset(columns):
        return "myntra_orders"
    if {"channel name", "sale order code", "item sku code", "sale order item status"}.issubset(columns):
        return "unicommerce"
    if {"product sku code", "sale order number", "unit price", "qty"}.issubset(columns):
        return "returns"
    if {"item skucode", "size", "inventory"}.issubset(columns) or "row labels" in columns:
        return "inventory"
    if {"campaign id", "product id", "impressions", "budget spend"}.issubset(columns):
        return "pla"
    if {"time period", "product id", "units sold", "ros"}.issubset(columns):
        return "visibility"
    raise ValueError("Could not auto-detect upload type from file columns")


def _result(
    df: pd.DataFrame,
    table: str,
    on_conflict: str | None = None,
    existing_conflict: str | None = None,
    ignore_duplicates: bool = False,
    file_type: str | None = None,
    file_name: str | None = None,
) -> UploadResult:
    rows = df.where(pd.notna(df), None).to_dict("records")
    conflict_key = on_conflict or existing_conflict
    rows_to_write = _dedupe_on_conflict(rows, conflict_key)
    rows_to_write = _skip_existing(rows_to_write, table, existing_conflict)
    try:
        inserted = table_upsert(table, rows_to_write, on_conflict=on_conflict, ignore_duplicates=ignore_duplicates) if rows_to_write else 0
        result = UploadResult(rows_processed=len(df), rows_inserted=inserted, rows_skipped=max(len(df) - inserted, 0))
    except SupabaseUnavailable as exc:
        result = UploadResult(status="error", rows_processed=len(df), rows_inserted=0, rows_skipped=len(df), errors=[str(exc)])
    except Exception as exc:
        result = UploadResult(status="error", rows_processed=len(df), rows_inserted=0, rows_skipped=len(df), errors=[_error_message(exc)])
    if file_type:
        _log_upload(
            file_type,
            file_name,
            result.rows_processed,
            result.rows_inserted,
            result.rows_skipped,
            result.status,
            "; ".join(result.errors) if result.errors else None,
        )
    return result


def _log_upload(
    file_type: str,
    file_name: str | None,
    rows_processed: int,
    rows_inserted: int,
    rows_skipped: int,
    status: str = "success",
    error_msg: str | None = None,
) -> None:
    try:
        table_insert(
            "upload_log",
            [
                {
                    "file_type": file_type,
                    "file_name": file_name,
                    "rows_processed": rows_processed,
                    "rows_inserted": rows_inserted,
                    "rows_skipped": rows_skipped,
                    "status": status,
                    "error_msg": error_msg,
                }
            ],
        )
    except Exception:
        pass


def _upsert_sale_grade_updates(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = df.where(pd.notna(df), None).to_dict("records")
    return table_upsert("sku_master", rows, on_conflict="style_color") if rows else 0


def _normalize_sale_grade(value: object) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    raw = str(value).strip()
    if not raw:
        return "Unknown"
    return GRADE_NORMALIZE.get(raw, raw)


def _sale_grade_master_rows(df: pd.DataFrame) -> pd.DataFrame:
    sku_col = find_column(df, ["sku"])
    sale_grade_col = find_column(df, ["sale_grade"])
    if not sku_col or not sale_grade_col:
        raise ValueError("Sale grade master requires columns: sku and sale_grade")
    rows = df[[sku_col, sale_grade_col]].copy()
    rows.columns = ["sku", "sale_grade_old"]
    rows["style_color"] = rows["sku"].apply(normalize_sku)
    rows["sale_grade_old"] = rows["sale_grade_old"].apply(_normalize_sale_grade)
    return rows[["style_color", "sale_grade_old"]].dropna(subset=["style_color"])


@router.post("/myntra_orders", response_model=UploadResult)
async def upload_myntra_orders(file: UploadFile = File(...), sku_map_file: UploadFile | None = File(None)):
    return _result(process_myntra_orders(await _read(file), await _sku_map(sku_map_file), file_name=file.filename), "sales_fact", "order_id,internal_sku", file_type="myntra_orders", file_name=file.filename)


@router.post("/auto_detect")
async def upload_auto_detect(file: UploadFile = File(...)):
    df = await _read(file)
    detected = _detect_upload_type(df)
    if detected == "myntra_orders":
        return _result(process_myntra_orders(df, await _sku_map(), file_name=file.filename), "sales_fact", "order_id,internal_sku", file_type="myntra_orders", file_name=file.filename)
    if detected == "unicommerce":
        _upsert_sale_grade_updates(build_sale_grade_updates(df, ["Item SKU Code", "item_sku_code", "SKU Code"]))
        processed = process_unicommerce_sales(df, source="sales_master", include_myntra=True) if _is_sales_master(df) else process_unicommerce_sales(df, include_myntra=True)
        return _result(processed, "sales_fact", "order_id,internal_sku", file_type="unicommerce", file_name=file.filename)
    if detected == "inventory":
        master, history = process_inventory_snapshot(df, date.today())
        try:
            table_upsert("inventory_fact", history.where(pd.notna(history), None).to_dict("records"), on_conflict="snapshot_date,style_color,size")
        except Exception as exc:
            return UploadResult(status="error", rows_processed=len(history), rows_inserted=0, rows_skipped=len(history), errors=[_error_message(exc)])
        return _result(master.drop(columns=["snapshot_date"], errors="ignore"), "sku_master", "style_color", file_type="inventory", file_name=file.filename)
    if detected == "returns":
        return _result(
            process_returns(df),
            "returns_fact",
            on_conflict="order_id,internal_sku,date",
            ignore_duplicates=True,
            file_type="returns",
            file_name=file.filename,
        )
    if detected == "pla":
        return _result(
            process_pla_report(df, await _sku_map(), date.today()),
            "pla_fact",
            existing_conflict="upload_date,style_id,campaign_id",
            file_type="pla",
            file_name=file.filename,
        )
    if detected == "visibility":
        return _result(
            process_visibility_report(df, await _sku_map()),
            "visibility_fact",
            existing_conflict="period_start,period_end,style_id",
            file_type="visibility",
            file_name=file.filename,
        )
    if detected == "sale_grade_master":
        rows = _sale_grade_master_rows(df)
        existing = {
            row.get("style_color")
            for row in table_select_all("sku_master", columns="style_color", max_rows=500000)
            if row.get("style_color")
        }
        rows_not_found = int((~rows["style_color"].isin(existing)).sum())
        found = rows[rows["style_color"].isin(existing)].drop_duplicates("style_color", keep="last")
        updates = found.where(pd.notna(found), None).to_dict("records")
        rows_updated = table_upsert("sku_master", updates, on_conflict="style_color") if updates else 0
        category_result = rebuild_sku_master_categories()
        _log_upload("sale_grade_master", file.filename, rows_processed=len(df), rows_inserted=rows_updated, rows_skipped=rows_not_found)
        return {
            "status": "success",
            "detected_type": detected,
            "rows_processed": len(df),
            "rows_updated": rows_updated,
            "rows_not_found": rows_not_found,
            "category_breakdown": category_result["breakdown"],
        }
    raise ValueError(f"Unsupported detected upload type: {detected}")


@router.post("/unicommerce", response_model=UploadResult)
async def upload_unicommerce(file: UploadFile = File(...)):
    df = await _read(file)
    _upsert_sale_grade_updates(build_sale_grade_updates(df, ["Item SKU Code", "item_sku_code", "SKU Code"]))
    if _is_sales_master(df):
        processed = process_unicommerce_sales(df, source="sales_master", include_myntra=True)
    else:
        processed = process_unicommerce_sales(df, include_myntra=True)
    return _result(processed, "sales_fact", "order_id,internal_sku", file_type="unicommerce", file_name=file.filename)


@router.post("/inventory", response_model=UploadResult)
async def upload_inventory(file: UploadFile = File(...)):
    master, history = process_inventory_snapshot(await _read(file), date.today())
    try:
        table_upsert("inventory_fact", history.where(pd.notna(history), None).to_dict("records"), on_conflict="snapshot_date,style_color,size")
    except Exception as exc:
        return UploadResult(status="error", rows_processed=len(history), rows_inserted=0, rows_skipped=len(history), errors=[_error_message(exc)])
    return _result(master.drop(columns=["snapshot_date"], errors="ignore"), "sku_master", "style_color", file_type="inventory", file_name=file.filename)


@router.post("/returns", response_model=UploadResult)
async def upload_returns(file: UploadFile = File(...)):
    return _result(
        process_returns(await _read(file)),
        "returns_fact",
        on_conflict="order_id,internal_sku,date",
        ignore_duplicates=True,
        file_type="returns",
        file_name=file.filename,
    )


@router.post("/sale_grade_master")
async def upload_sale_grade_master(file: UploadFile = File(...)):
    df = await _read(file)
    rows = _sale_grade_master_rows(df)
    existing = {
        row.get("style_color")
        for row in table_select_all("sku_master", columns="style_color", max_rows=500000)
        if row.get("style_color")
    }
    rows_not_found = int((~rows["style_color"].isin(existing)).sum())
    found = rows[rows["style_color"].isin(existing)].drop_duplicates("style_color", keep="last")
    updates = found.where(pd.notna(found), None).to_dict("records")
    rows_updated = table_upsert("sku_master", updates, on_conflict="style_color") if updates else 0
    category_result = rebuild_sku_master_categories()
    _log_upload(
        "sale_grade_master",
        file.filename,
        rows_processed=len(df),
        rows_inserted=rows_updated,
        rows_skipped=rows_not_found,
    )
    return {
        "status": "success",
        "rows_processed": len(df),
        "rows_updated": rows_updated,
        "rows_not_found": rows_not_found,
        "category_breakdown": category_result["breakdown"],
    }


@router.post("/pla", response_model=UploadResult)
async def upload_pla(file: UploadFile = File(...), sku_map_file: UploadFile | None = File(None)):
    return _result(
        process_pla_report(await _read(file), await _sku_map(sku_map_file), date.today()),
        "pla_fact",
        existing_conflict="upload_date,style_id,campaign_id",
        file_type="pla",
        file_name=file.filename,
    )


@router.post("/visibility", response_model=UploadResult)
async def upload_visibility(file: UploadFile = File(...), sku_map_file: UploadFile | None = File(None)):
    return _result(
        process_visibility_report(await _read(file), await _sku_map(sku_map_file)),
        "visibility_fact",
        existing_conflict="period_start,period_end,style_id",
        file_type="visibility",
        file_name=file.filename,
    )


@router.post("/replenishment", response_model=UploadResult)
async def upload_replenishment(file: UploadFile = File(...)):
    return _result(process_replenishment_upload(await _read(file)), "replenishment_log", file_type="replenishment", file_name=file.filename)


@router.post("/sku_mapping", response_model=UploadResult)
async def upload_sku_mapping(listing_file: UploadFile = File(...), channel_item_file: UploadFile = File(...)):
    listing_df = await _read(listing_file)
    channel_item_df = await _read(channel_item_file)
    sku_map = build_sku_master_map(listing_df, channel_item_df)
    _upsert_sale_grade_updates(build_sku_mapping_sale_grade_updates(listing_df, channel_item_df, sku_map))
    return _result(sku_map, "sku_master_map", "style_id,myntra_seller_sku", file_type="sku_mapping", file_name=f"{listing_file.filename}, {channel_item_file.filename}")
