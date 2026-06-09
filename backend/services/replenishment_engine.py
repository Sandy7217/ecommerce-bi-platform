from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import ceil
from statistics import median
from typing import Any


CLOSED_REPLENISHMENT_STATUSES = {"completed", "cancelled", "canceled", "received", "closed", "done"}
HOLD_CATEGORIES = {"Dog styles", "Dead", "Watchlist"}
REVIEW_CATEGORIES = {"Yellow", "Red", "Winter", "New Launch", "RED(Repeat)", "Potential NOOS"}
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL", "FREE", "OS", "UNKNOWN"]
NO_REPLENISHMENT_ACTION = "No Replenishment"
MIN_REPLENISHMENT_ROS = 1.5
MIN_RECENT_SALES_QTY = 3


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _style_key(value: Any) -> str:
    return str(value or "").strip()


def _size_key(value: Any) -> str:
    size = str(value or "UNKNOWN").strip().upper()
    return size or "UNKNOWN"


def _category(row: dict[str, Any]) -> str:
    return str(row.get("category_new") or row.get("cross_category") or "Unknown")


def _sale_status(row: dict[str, Any]) -> str:
    return str(row.get("sale_grade_old") or row.get("sale_status") or "").strip()


def _normalized_sale_status(row: dict[str, Any]) -> str:
    return _sale_status(row).upper()


def _is_discontinued_sale_status(row: dict[str, Any]) -> bool:
    return _normalized_sale_status(row) in {"DISCONTINUE", "DISCONTINUED"}


def _is_noos_sale_status(row: dict[str, Any]) -> bool:
    status = _normalized_sale_status(row)
    if status in {"", "POTENTIAL NOOS", "POTENCIAL NOOS"}:
        return False
    return "NOOS" in status


def _inventory_status(row: dict[str, Any]) -> str:
    return str(row.get("inventory_status") or row.get("status") or "UNKNOWN").upper()


def _size_sort_key(size: str) -> tuple[int, str]:
    normalized = _size_key(size)
    return (SIZE_ORDER.index(normalized) if normalized in SIZE_ORDER else 99, normalized)


def round_replenishment_qty(value: Any) -> int:
    qty = _to_float(value)
    if qty <= 0:
        return 0
    if qty <= 500:
        return 500
    if qty <= 800:
        return 800
    if qty <= 1000:
        return 1000
    return int(ceil(qty / 100) * 100)


def pending_replenishment_by_style(rows: list[dict[str, Any]]) -> dict[str, int]:
    pending: dict[str, int] = defaultdict(int)
    for row in rows:
        style = _style_key(row.get("style_color"))
        if not style:
            continue
        status = str(row.get("status") or "planned").strip().lower()
        if status in CLOSED_REPLENISHMENT_STATUSES:
            continue
        pending[style] += max(_to_int(row.get("replenishment_qty")), 0)
    return dict(pending)


def latest_size_inventory_by_style(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    latest_by_style: dict[str, str] = {}
    for row in rows:
        style = _style_key(row.get("style_color"))
        snapshot = str(row.get("snapshot_date") or "")
        if style and snapshot > latest_by_style.get(style, ""):
            latest_by_style[style] = snapshot

    grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        style = _style_key(row.get("style_color"))
        if not style:
            continue
        if latest_by_style.get(style) and str(row.get("snapshot_date") or "") != latest_by_style[style]:
            continue
        grouped[style][_size_key(row.get("size"))] += max(_to_int(row.get("qty")), 0)
    return {style: dict(sizes) for style, sizes in grouped.items()}


def size_sales_mix_by_style(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        style = _style_key(row.get("style_color") or row.get("internal_sku"))
        if not style:
            continue
        grouped[style][_size_key(row.get("size"))] += max(_to_int(row.get("qty")), 0)
    return {style: dict(sizes) for style, sizes in grouped.items()}


def latest_visibility_ros_by_style(rows: list[dict[str, Any]]) -> dict[str, float]:
    latest: dict[str, tuple[str, float]] = {}
    for row in rows:
        style = _style_key(row.get("style_color"))
        ros = _to_float(row.get("ros"))
        if not style or ros <= 0:
            continue
        period = str(row.get("period_end") or row.get("period_start") or "")
        if style not in latest or period >= latest[style][0]:
            latest[style] = (period, ros)
    return {style: value for style, (_period, value) in latest.items()}


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def style_sales_profile_by_style(rows: list[dict[str, Any]], today: date | None = None) -> dict[str, dict[str, int]]:
    today_date = today or date.today()
    start_30d = today_date - timedelta(days=29)
    start_90d = today_date - timedelta(days=89)
    qty_30d: dict[str, int] = defaultdict(int)
    qty_90d: dict[str, int] = defaultdict(int)
    active_days: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        style = _style_key(row.get("style_color") or row.get("internal_sku"))
        sale_date = _parse_date(row.get("date"))
        qty = max(_to_int(row.get("qty")), 0)
        if not style or not sale_date or qty <= 0 or sale_date < start_90d or sale_date > today_date:
            continue
        qty_90d[style] += qty
        active_days[style].add(sale_date.isoformat())
        if sale_date >= start_30d:
            qty_30d[style] += qty

    return {
        style: {
            "qty_30d": qty_30d.get(style, 0),
            "qty_90d": qty_90d.get(style, 0),
            "active_sale_days_90d": len(active_days.get(style, set())),
        }
        for style in sorted(qty_90d)
    }


def _base_weighted_ros(row: dict[str, Any], visibility_ros: float = 0) -> float:
    ros_7d = _to_float(row.get("ros_7d"))
    ros_30d = _to_float(row.get("ros_30d") or row.get("ros"))
    if visibility_ros > 0 and ros_7d > 0 and ros_30d > 0:
        return (0.35 * ros_7d) + (0.45 * ros_30d) + (0.20 * visibility_ros)
    if ros_7d > 0 and ros_30d > 0:
        return (0.35 * ros_7d) + (0.65 * ros_30d)
    if visibility_ros > 0 and ros_30d > 0:
        return (0.75 * ros_30d) + (0.25 * visibility_ros)
    return max(ros_7d, ros_30d, visibility_ros)


def _category_baselines(rows: list[dict[str, Any]], visibility_ros_by_style: dict[str, float]) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        style = _style_key(row.get("style_color"))
        status = _inventory_status(row)
        stock = _to_int(row.get("total_inventory"))
        demand = _base_weighted_ros(row, visibility_ros_by_style.get(style, 0))
        if demand > 0 and stock > 0 and status != "OOS":
            values[_category(row)].append(demand)
    return {category: float(median(items)) for category, items in values.items() if items}


def _action_for_category(category: str, status: str) -> str:
    if category in HOLD_CATEGORIES:
        return "Hold"
    if status == "OOS" or category not in REVIEW_CATEGORIES:
        return "Auto"
    return "Review"


def _replenishment_eligibility(
    row: dict[str, Any],
    predicted_ros: float,
    sales_profile: dict[str, int],
) -> tuple[bool, str]:
    qty_30d = _to_int(sales_profile.get("qty_30d"))
    qty_90d = _to_int(sales_profile.get("qty_90d"))
    ros_7d = _to_float(row.get("ros_7d"))
    ros_30d = _to_float(row.get("ros_30d") or row.get("ros"))
    status = _inventory_status(row)

    if _is_discontinued_sale_status(row) and qty_90d <= 0:
        return False, "Discontinued and no sales in last 90 days"
    if _is_discontinued_sale_status(row):
        return False, "Sale status is discontinued"
    if not _is_noos_sale_status(row):
        return False, "Sale status is not NOOS"
    if qty_90d <= 0:
        return False, "No sales in last 90 days"
    if max(predicted_ros, ros_30d) < MIN_REPLENISHMENT_ROS:
        return False, "Sales performance below replenishment threshold"
    if status not in {"OOS", "BROKEN"} and qty_30d < MIN_RECENT_SALES_QTY and ros_7d < 0.75:
        return False, "Sales performance below replenishment threshold"
    return True, "Eligible NOOS with consistent sales"


def _urgency(
    action: str,
    status: str,
    predicted_ros: float,
    stock: int,
    pending_qty: int,
    raw_qty: int,
    today: date,
    lead_time_days: int,
) -> tuple[str, str | None, str | None, float | None]:
    if action == "Hold" or predicted_ros <= 0:
        return "Hold", None, None, None
    days_to_stockout = stock / predicted_ros if predicted_ros > 0 else None
    stockout_date = today + timedelta(days=int(days_to_stockout or 0))
    order_by_date = stockout_date - timedelta(days=lead_time_days)
    if raw_qty <= 0:
        return "Covered", stockout_date.isoformat(), order_by_date.isoformat(), round(days_to_stockout or 0, 1)
    if status == "OOS" or stock <= 0:
        return "P0 - Stockout", stockout_date.isoformat(), order_by_date.isoformat(), round(days_to_stockout or 0, 1)
    if order_by_date <= today:
        return "P1 - Order Now", stockout_date.isoformat(), order_by_date.isoformat(), round(days_to_stockout or 0, 1)
    if order_by_date <= today + timedelta(days=7):
        return "P2 - Due This Week", stockout_date.isoformat(), order_by_date.isoformat(), round(days_to_stockout or 0, 1)
    return "Monitor", stockout_date.isoformat(), order_by_date.isoformat(), round(days_to_stockout or 0, 1)


def _size_weights(size_inventory: dict[str, int], size_sales: dict[str, int]) -> dict[str, float]:
    sizes = {_size_key(size) for size in size_inventory} | {_size_key(size) for size in size_sales}
    if not sizes:
        return {"UNKNOWN": 1.0}
    total_sales = sum(max(qty, 0) for qty in size_sales.values())
    if total_sales > 0:
        return {_size_key(size): max(_to_int(size_sales.get(size)), 0) / total_sales for size in sizes}
    equal_weight = 1 / len(sizes)
    return {size: equal_weight for size in sizes}


def allocate_size_replenishment(total_qty: int, size_inventory: dict[str, int] | None = None, size_sales: dict[str, int] | None = None) -> list[dict[str, Any]]:
    if total_qty <= 0:
        return []
    inventory = {_size_key(size): max(_to_int(qty), 0) for size, qty in (size_inventory or {}).items()}
    sales = {_size_key(size): max(_to_int(qty), 0) for size, qty in (size_sales or {}).items()}
    weights = _size_weights(inventory, sales)
    sizes = sorted(weights, key=lambda size: (-weights[size], _size_sort_key(size)))
    allocation = {size: 0 for size in sizes}

    lots = total_qty // 100
    for size in sizes:
        if lots <= 0:
            break
        allocation[size] += 100
        lots -= 1

    remaining = lots * 100
    if remaining > 0:
        ideals = {size: total_qty * weights[size] for size in sizes}
        while remaining > 0:
            size = max(
                sizes,
                key=lambda item: (
                    ideals[item] - allocation[item],
                    weights[item],
                    -inventory.get(item, 0),
                    -_size_sort_key(item)[0],
                ),
            )
            allocation[size] += 100
            remaining -= 100

    return [
        {"size": size, "current_qty": inventory.get(size, 0), "recommended_qty": qty}
        for size, qty in sorted(allocation.items(), key=lambda item: (-item[1], -weights[item[0]], _size_sort_key(item[0])))
        if qty > 0
    ]


def build_hybrid_replenishment_plan(
    rows: list[dict[str, Any]],
    *,
    manual_replenishment_rows: list[dict[str, Any]] | None = None,
    size_inventory_by_style: dict[str, dict[str, int]] | None = None,
    size_sales_by_style: dict[str, dict[str, int]] | None = None,
    visibility_ros_by_style: dict[str, float] | None = None,
    style_sales_profile_by_style: dict[str, dict[str, int]] | None = None,
    lead_time_days: int = 45,
    review_cycle_days: int = 15,
    today: date | None = None,
) -> dict[str, Any]:
    today_date = today or date.today()
    manual_rows = manual_replenishment_rows or []
    pending_by_style = pending_replenishment_by_style(manual_rows)
    size_inventory = size_inventory_by_style or {}
    size_sales = size_sales_by_style or {}
    visibility_ros = visibility_ros_by_style or {}
    sales_profiles = style_sales_profile_by_style or {}
    baselines = _category_baselines(rows, visibility_ros)
    cover_days = lead_time_days + review_cycle_days

    items: list[dict[str, Any]] = []
    for row in rows:
        style = _style_key(row.get("style_color"))
        if not style:
            continue
        category = _category(row)
        status = _inventory_status(row)
        stock = _to_int(row.get("total_inventory"))
        pending_qty = pending_by_style.get(style, 0)
        base_ros = _base_weighted_ros(row, visibility_ros.get(style, 0))
        baseline_ros = baselines.get(category, 0) if status in {"OOS", "BROKEN"} else 0
        predicted_ros = round(max(base_ros, baseline_ros), 2)
        eligible, replenishment_reason = _replenishment_eligibility(row, predicted_ros, sales_profiles.get(style, {}))
        target_stock = int(round(predicted_ros * cover_days)) if eligible else 0
        action = _action_for_category(category, status) if eligible else NO_REPLENISHMENT_ACTION
        raw_qty = max(target_stock - stock - pending_qty, 0) if action not in {"Hold", NO_REPLENISHMENT_ACTION} else 0
        recommended_qty = round_replenishment_qty(raw_qty)
        if not eligible:
            urgency, stockout_date, order_by_date, days_to_stockout = NO_REPLENISHMENT_ACTION, None, None, None
        else:
            urgency, stockout_date, order_by_date, days_to_stockout = _urgency(
                action,
                status,
                predicted_ros,
                stock,
                pending_qty,
                raw_qty,
                today_date,
                lead_time_days,
            )
        items.append(
            {
                "style_color": style,
                "category_new": category,
                "inventory_status": status,
                "total_inventory": stock,
                "ros_7d": round(_to_float(row.get("ros_7d")), 2),
                "ros_30d": round(_to_float(row.get("ros_30d") or row.get("ros")), 2),
                "visibility_ros": round(visibility_ros.get(style, 0), 2),
                "predicted_ros": predicted_ros,
                "target_cover_days": cover_days,
                "target_stock": target_stock,
                "pending_replenishment_qty": pending_qty,
                "sales_qty_30d": _to_int(sales_profiles.get(style, {}).get("qty_30d")),
                "sales_qty_90d": _to_int(sales_profiles.get(style, {}).get("qty_90d")),
                "active_sale_days_90d": _to_int(sales_profiles.get(style, {}).get("active_sale_days_90d")),
                "raw_replenishment_qty": raw_qty,
                "recommended_replenishment_qty": recommended_qty,
                "replenishment_qty": recommended_qty,
                "replenishment_reason": replenishment_reason,
                "already_planned": pending_qty > 0,
                "action": action,
                "urgency": urgency,
                "stockout_date": stockout_date,
                "order_by_date": order_by_date,
                "days_to_stockout": days_to_stockout,
                "doi": round(stock / predicted_ros, 1) if predicted_ros > 0 else 9999,
                "size_replenishment": allocate_size_replenishment(
                    recommended_qty,
                    size_inventory.get(style),
                    size_sales.get(style),
                ),
            }
        )

    def urgency_rank(item: dict[str, Any]) -> int:
        urgency = str(item.get("urgency") or "")
        if urgency.startswith("P0"):
            return 0
        if urgency.startswith("P1"):
            return 1
        if urgency.startswith("P2"):
            return 2
        if urgency == "Covered":
            return 3
        if urgency == "Monitor":
            return 4
        if urgency == NO_REPLENISHMENT_ACTION:
            return 8
        return 9

    items.sort(
        key=lambda item: (
            urgency_rank(item),
            -int(item.get("recommended_replenishment_qty") or 0),
            str(item.get("style_color") or ""),
        )
    )
    summary = _build_summary(items)
    return {
        "summary": summary,
        "charts": _build_charts(items),
        "items": items,
    }


def _build_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_styles": len(items),
        "urgent_styles": sum(1 for item in items if str(item.get("urgency") or "").startswith(("P0", "P1"))),
        "due_this_week_styles": sum(1 for item in items if str(item.get("urgency") or "").startswith("P2")),
        "already_planned_styles": sum(1 for item in items if item.get("already_planned")),
        "manual_pending_qty": sum(int(item.get("pending_replenishment_qty") or 0) for item in items),
        "recommended_qty": sum(int(item.get("recommended_replenishment_qty") or 0) for item in items),
        "eligible_styles": sum(1 for item in items if item.get("replenishment_reason") == "Eligible NOOS with consistent sales"),
        "no_replenishment_styles": sum(1 for item in items if item.get("action") == NO_REPLENISHMENT_ACTION),
        "auto_styles": sum(1 for item in items if item.get("action") == "Auto" and int(item.get("recommended_replenishment_qty") or 0) > 0),
        "review_styles": sum(1 for item in items if item.get("action") == "Review" and int(item.get("recommended_replenishment_qty") or 0) > 0),
        "hold_styles": sum(1 for item in items if item.get("action") == "Hold"),
    }


def _rollup(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, int | str]] = {}
    for item in items:
        name = str(item.get(key) or "Unknown")
        row = grouped.setdefault(name, {"name": name, "styles": 0, "qty": 0})
        row["styles"] = int(row["styles"]) + 1
        row["qty"] = int(row["qty"]) + int(item.get("recommended_replenishment_qty") or 0)
    return sorted(grouped.values(), key=lambda row: int(row["qty"]), reverse=True)


def _build_charts(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    size_qty: dict[str, int] = defaultdict(int)
    for item in items:
        for size_row in item.get("size_replenishment") or []:
            size_qty[str(size_row["size"])] += int(size_row["recommended_qty"] or 0)
    return {
        "urgency": _rollup(items, "urgency"),
        "category": _rollup(items, "category_new"),
        "manual_vs_new": [
            {"name": "Manual pending", "qty": sum(int(item.get("pending_replenishment_qty") or 0) for item in items)},
            {"name": "New recommended", "qty": sum(int(item.get("recommended_replenishment_qty") or 0) for item in items)},
        ],
        "size": [
            {"name": size, "qty": qty}
            for size, qty in sorted(size_qty.items(), key=lambda item: (-item[1], _size_sort_key(item[0])))
        ],
    }
