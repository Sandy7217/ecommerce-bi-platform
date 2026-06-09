from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from functools import lru_cache
import math
import time
from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from supabase import Client

from backend.config import get_settings


class SupabaseUnavailable(RuntimeError):
    """Raised when a route requires Supabase but env vars are not configured."""


_SELECT_ALL_CACHE: dict[tuple[Any, ...], tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 60
_DEFAULT_ORDER_BY = {
    "sales_fact": "date.asc,id.asc",
    "returns_fact": "date.asc,id.asc",
    "inventory_fact": "snapshot_date.asc,style_color.asc,size.asc",
    "sku_master": "style_color.asc",
    "sku_master_map": "style_id.asc,myntra_seller_sku.asc",
    "pla_fact": "upload_date.asc,id.asc",
    "visibility_fact": "period_start.asc,id.asc",
    "replenishment_log": "replenishment_date.asc,id.asc",
    "user_roles": "email.asc",
    "upload_log": "created_at.asc,id.asc",
}


def _cache_key(
    table: str,
    columns: str,
    page_size: int,
    max_rows: int,
    filters: dict[str, str] | list[tuple[str, str]] | None,
    order_by: str | None = None,
) -> tuple[Any, ...]:
    filter_items = tuple(filters.items() if isinstance(filters, dict) else filters or [])
    return (table, columns, page_size, max_rows, filter_items, order_by)


def _clear_select_cache() -> None:
    _SELECT_ALL_CACHE.clear()


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _batches(rows: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _parse_content_range(value: str | None) -> int | None:
    if not value or "/" not in value:
        return None
    total = value.rsplit("/", 1)[-1]
    if total == "*":
        return None
    try:
        return int(total)
    except ValueError:
        return None


def _select_params(columns: str, filters: dict[str, str] | list[tuple[str, str]] | None = None, order_by: str | None = None) -> list[tuple[str, str]]:
    params = [("select", columns)]
    if filters:
        params.extend(filters.items() if isinstance(filters, dict) else filters)
    if order_by:
        params.append(("order", order_by))
    return params


@lru_cache
def get_supabase_client() -> "Client | None":
    settings = get_settings()
    if not settings.has_supabase:
        return None
    try:
        from supabase import create_client
    except ModuleNotFoundError as exc:
        raise SupabaseUnavailable("Install requirements.txt to enable Supabase access") from exc
    return create_client(settings.supabase_url, settings.supabase_service_key)


def require_supabase() -> "Client":
    client = get_supabase_client()
    if client is None:
        raise SupabaseUnavailable("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for this operation")
    return client


def table_select(table: str, columns: str = "*", limit: int = 500) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.has_supabase:
        return []
    try:
        client = get_supabase_client()
        if client is not None:
            response = client.table(table).select(columns).limit(limit).execute()
            return list(response.data or [])
    except SupabaseUnavailable:
        pass
    response = httpx.get(
        f"{settings.supabase_url}/rest/v1/{table}",
        params={"select": columns, "limit": str(limit)},
        headers={
            "apikey": settings.supabase_service_key,
            "Authorization": f"Bearer {settings.supabase_service_key}",
        },
        timeout=30,
    )
    response.raise_for_status()
    return list(response.json() or [])


def table_select_all(
    table: str,
    columns: str = "*",
    page_size: int = 5000,
    max_rows: int = 200000,
    filters: dict[str, str] | list[tuple[str, str]] | None = None,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.has_supabase:
        return []
    order_by = order_by or _DEFAULT_ORDER_BY.get(table)
    cache_key = _cache_key(table, columns, page_size, max_rows, filters, order_by)
    cached = _SELECT_ALL_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return [dict(row) for row in cached[1]]

    base_headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
    }
    params = _select_params(columns, filters, order_by)
    first_response = httpx.get(
        f"{settings.supabase_url}/rest/v1/{table}",
        params=params,
        headers={**base_headers, "Range": f"0-{page_size - 1}", "Prefer": "count=exact"},
        timeout=60,
    )
    first_response.raise_for_status()
    first_batch = list(first_response.json() or [])
    total = _parse_content_range(first_response.headers.get("content-range"))
    if not total or len(first_batch) >= total:
        return first_batch[:max_rows]

    total = min(total, max_rows)
    actual_page_size = max(len(first_batch), 1)
    ranges = [(start, min(start + actual_page_size - 1, total - 1)) for start in range(actual_page_size, total, actual_page_size)]
    if not ranges:
        return first_batch[:total]

    def fetch_range(item: tuple[int, int]) -> tuple[int, list[dict[str, Any]]]:
        start, end = item
        response = httpx.get(
            f"{settings.supabase_url}/rest/v1/{table}",
            params=params,
            headers={**base_headers, "Range": f"{start}-{end}"},
            timeout=60,
        )
        response.raise_for_status()
        return start, list(response.json() or [])

    page_map: dict[int, list[dict[str, Any]]] = {0: first_batch}
    workers = min(16, max(1, len(ranges)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch_range, item) for item in ranges]
        for future in as_completed(futures):
            start, batch = future.result()
            page_map[start] = batch

    rows: list[dict[str, Any]] = []
    for start in sorted(page_map):
        rows.extend(page_map[start])
    result = rows[:total]
    _SELECT_ALL_CACHE[cache_key] = (now, result)
    return [dict(row) for row in result]


def _rest_upsert(table: str, rows: list[dict[str, Any]], on_conflict: str | None = None, ignore_duplicates: bool = False) -> int:
    settings = get_settings()
    if not settings.has_supabase:
        raise SupabaseUnavailable("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for this operation")
    inserted = 0
    params = {"on_conflict": on_conflict} if on_conflict else None
    resolution = "ignore-duplicates" if ignore_duplicates else "merge-duplicates"
    returning = "representation" if ignore_duplicates else "minimal"
    for batch in _batches(rows):
        response = httpx.post(
            f"{settings.supabase_url}/rest/v1/{table}",
            params=params,
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Prefer": f"resolution={resolution},return={returning}",
            },
            json=batch,
            timeout=120,
        )
        response.raise_for_status()
        inserted += len(response.json() or []) if ignore_duplicates else len(batch)
    return inserted


def table_upsert(
    table: str,
    rows: list[dict[str, Any]],
    on_conflict: str | None = None,
    ignore_duplicates: bool = False,
) -> int:
    if not rows:
        return 0
    _clear_select_cache()
    rows = [_json_safe(row) for row in rows]
    if ignore_duplicates:
        return _rest_upsert(table, rows, on_conflict=on_conflict, ignore_duplicates=True)
    try:
        client = require_supabase()
        inserted = 0
        for batch in _batches(rows):
            query = client.table(table).upsert(batch, on_conflict=on_conflict) if on_conflict else client.table(table).upsert(batch)
            response = query.execute()
            inserted += len(response.data or batch)
        return inserted
    except SupabaseUnavailable:
        return _rest_upsert(table, rows, on_conflict=on_conflict)


def table_insert(table: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    _clear_select_cache()
    rows = [_json_safe(row) for row in rows]
    try:
        client = require_supabase()
        inserted = 0
        for batch in _batches(rows):
            response = client.table(table).insert(batch).execute()
            inserted += len(response.data or batch)
        return inserted
    except SupabaseUnavailable:
        settings = get_settings()
        if not settings.has_supabase:
            raise
        inserted = 0
        for batch in _batches(rows):
            response = httpx.post(
                f"{settings.supabase_url}/rest/v1/{table}",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Prefer": "return=minimal",
                },
                json=batch,
                timeout=120,
            )
            response.raise_for_status()
            inserted += len(batch)
        return inserted
