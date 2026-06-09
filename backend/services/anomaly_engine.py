from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from backend.config import get_settings


SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Monitor": 3}
EXCLUDED_CATEGORY_KEYWORDS = ("NOOS",)
EXCLUDED_CATEGORY_VALUES = {"GREEN"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _style_key(value: Any) -> str:
    return _text(value).lower()


def _to_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _amount(row: dict[str, Any], value_key: str = "selling_price") -> float:
    qty = _to_float(row.get("qty") or row.get("quantity"))
    if value_key == "return_value":
        return _to_float(row.get("return_value")) * (qty if not row.get("return_value") else 1)
    return _to_float(row.get(value_key)) * qty


def _pct_delta(current: float, baseline: float) -> float:
    if baseline == 0:
        return 999.0 if current > 0 else 0.0
    return ((current - baseline) / baseline) * 100


def _ratio(current: float, baseline: float) -> float:
    if baseline <= 0:
        return 999.0 if current > 0 else 0.0
    return current / baseline


def _return_pct(return_qty: float, sales_qty: float) -> float:
    if sales_qty <= 0:
        return 0.0
    return (return_qty / sales_qty) * 100


def _is_excluded_category(category: str) -> bool:
    normalized = category.upper()
    return any(keyword in normalized for keyword in EXCLUDED_CATEGORY_KEYWORDS) or normalized in EXCLUDED_CATEGORY_VALUES


def _windowed_style_totals(
    rows: list[dict[str, Any]],
    *,
    today: date,
    amount_key: str,
) -> dict[str, dict[str, float]]:
    recent_start = today - timedelta(days=6)
    baseline_start = today - timedelta(days=13)
    baseline_end = today - timedelta(days=7)
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for row in rows:
        row_date = _to_date(row.get("date"))
        style = _style_key(row.get("style_color"))
        if not row_date or not style:
            continue

        bucket: str | None = None
        if recent_start <= row_date <= today:
            bucket = "recent"
        elif baseline_start <= row_date <= baseline_end:
            bucket = "baseline"
        if not bucket:
            continue

        qty = _to_float(row.get("qty") or row.get("quantity"))
        totals[style][f"{bucket}_qty"] += qty
        totals[style][f"{bucket}_value"] += _amount(row, amount_key)

    return {style: dict(values) for style, values in totals.items()}


def _sku_lookup(sku_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in sku_rows:
        style = _style_key(row.get("style_color"))
        if style:
            lookup[style] = row
    return lookup


def _base_alert(
    *,
    alert_type: str,
    severity: str,
    scope: str,
    subject: str,
    category: str = "Unknown",
    status: str = "Unknown",
    reason: str,
    action: str,
) -> dict[str, Any]:
    is_style = scope == "Style"
    return {
        "id": f"{scope.lower()}:{subject.lower()}:{alert_type.lower().replace(' ', '-')}",
        "severity": severity,
        "alert_type": alert_type,
        "scope": scope,
        "subject": subject,
        "style_color": subject if is_style else None,
        "category_subject": subject if not is_style else None,
        "category": category or "Unknown",
        "inventory_status": status or "Unknown",
        "status": status or "Unknown",
        "reason": reason,
        "action": action,
    }


def _style_alerts(
    sales_rows: list[dict[str, Any]],
    return_rows: list[dict[str, Any]],
    sku_rows: list[dict[str, Any]],
    *,
    today: date,
    lead_time_days: int,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    sales = _windowed_style_totals(sales_rows, today=today, amount_key="selling_price")
    returns = _windowed_style_totals(return_rows, today=today, amount_key="return_value")
    skus = _sku_lookup(sku_rows)
    styles = set(sales) | set(returns) | set(skus)

    for style in styles:
        sku = skus.get(style, {})
        display_style = _text(sku.get("style_color")) or style
        category = _text(sku.get("category_new")) or "Unknown"
        status = _text(sku.get("inventory_status")) or "Unknown"

        sales_recent_qty = sales.get(style, {}).get("recent_qty", 0.0)
        sales_baseline_qty = sales.get(style, {}).get("baseline_qty", 0.0)
        sales_recent_value = sales.get(style, {}).get("recent_value", 0.0)
        sales_baseline_value = sales.get(style, {}).get("baseline_value", 0.0)
        sales_delta_pct = _pct_delta(sales_recent_qty, sales_baseline_qty)
        sales_spike = sales_recent_qty >= 5 and _ratio(sales_recent_qty, sales_baseline_qty) >= 1.75

        return_recent_qty = returns.get(style, {}).get("recent_qty", 0.0)
        return_baseline_qty = returns.get(style, {}).get("baseline_qty", 0.0)
        return_recent_value = returns.get(style, {}).get("recent_value", 0.0)
        return_baseline_value = returns.get(style, {}).get("baseline_value", 0.0)
        return_delta_pct = _pct_delta(return_recent_qty, return_baseline_qty)
        return_pct_recent = _return_pct(return_recent_qty, sales_recent_qty)
        return_pct_baseline = _return_pct(return_baseline_qty, sales_baseline_qty)
        return_pct_delta = return_pct_recent - return_pct_baseline
        return_spike = (
            return_recent_qty >= 2
            and (_ratio(return_recent_qty, return_baseline_qty) >= 1.5 or return_pct_delta >= 10)
        )

        shared_metrics = {
            "sales_recent_qty": round(sales_recent_qty, 2),
            "sales_baseline_qty": round(sales_baseline_qty, 2),
            "sales_recent_value": round(sales_recent_value, 2),
            "sales_baseline_value": round(sales_baseline_value, 2),
            "sales_delta_pct": round(sales_delta_pct, 2),
            "return_recent_qty": round(return_recent_qty, 2),
            "return_baseline_qty": round(return_baseline_qty, 2),
            "return_recent_value": round(return_recent_value, 2),
            "return_baseline_value": round(return_baseline_value, 2),
            "return_delta_pct": round(return_delta_pct, 2),
            "return_pct_recent": round(return_pct_recent, 2),
            "return_pct_baseline": round(return_pct_baseline, 2),
            "return_pct_delta": round(return_pct_delta, 2),
        }

        if sales_spike and return_spike:
            alert = _base_alert(
                alert_type="Sales + Return Spike",
                severity="Critical",
                scope="Style",
                subject=display_style,
                category=category,
                status=status,
                reason="Recent 7-day sales and returns both rose sharply versus the previous 7 days.",
                action="Check marketplace issue, product fit, size complaints, and fulfillment quality before scaling ads or replenishment.",
            )
            alert.update(shared_metrics)
            alerts.append(alert)
        elif sales_spike:
            alert = _base_alert(
                alert_type="Sales Spike",
                severity="High",
                scope="Style",
                subject=display_style,
                category=category,
                status=status,
                reason="Recent 7-day sales rose at least 1.75x versus the previous 7 days.",
                action="Review stock cover and marketplace visibility while monitoring returns.",
            )
            alert.update(shared_metrics)
            alerts.append(alert)
        elif return_spike:
            alert = _base_alert(
                alert_type="Return Spike",
                severity="High",
                scope="Style",
                subject=display_style,
                category=category,
                status=status,
                reason="Recent return quantity or return percentage rose sharply versus the previous 7 days.",
                action="Audit listing, size set, quality feedback, and marketplace-specific return reasons.",
            )
            alert.update(shared_metrics)
            alerts.append(alert)

        ros = _to_float(sku.get("ros_30d") if sku.get("ros_30d") is not None else sku.get("ros"))
        current_inventory = _to_float(sku.get("total_inventory"))
        expected_inventory = max(ros * lead_time_days, 1.0)
        inventory_delta_pct = _pct_delta(current_inventory, expected_inventory)
        if current_inventory >= 50 and current_inventory >= expected_inventory * 1.5:
            alert = _base_alert(
                alert_type="Overstock Risk",
                severity="High" if inventory_delta_pct < 100 else "Critical",
                scope="Style",
                subject=display_style,
                category=category,
                status=status,
                reason="Current inventory is at least 1.5x expected stock based on ROS and lead time.",
                action="Avoid fresh buying until sell-through improves; consider channel push or markdown review.",
            )
            alert.update(
                {
                    "current_inventory": round(current_inventory, 2),
                    "expected_inventory": round(expected_inventory, 2),
                    "inventory_delta_pct": round(inventory_delta_pct, 2),
                    "ros_30d": round(ros, 2),
                }
            )
            alerts.append(alert)

    return alerts


def _snapshot_dates(inventory_rows: list[dict[str, Any]], today: date) -> tuple[date | None, date | None]:
    dates = sorted({row_date for row in inventory_rows if (row_date := _to_date(row.get("snapshot_date"))) and row_date <= today})
    if not dates:
        return None, None
    current_date = dates[-1]
    target_baseline = today - timedelta(days=15)
    baseline_candidates = [item for item in dates if item <= target_baseline]
    if baseline_candidates:
        return current_date, baseline_candidates[-1]
    older_candidates = [item for item in dates if item < current_date]
    return current_date, older_candidates[0] if older_candidates else None


def _category_snapshot(
    inventory_rows: list[dict[str, Any]],
    sku_rows: list[dict[str, Any]],
    snapshot_date: date,
) -> dict[str, dict[str, Any]]:
    skus = _sku_lookup(sku_rows)
    totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"inventory": 0.0, "styles": set()})

    for row in inventory_rows:
        row_date = _to_date(row.get("snapshot_date"))
        if row_date != snapshot_date:
            continue
        style = _style_key(row.get("style_color"))
        category = _text(skus.get(style, {}).get("category_new")) or "Unknown"
        qty = _to_float(row.get("qty") or row.get("inventory"))
        totals[category]["inventory"] += qty
        if qty > 0 and style:
            totals[category]["styles"].add(style)

    return {
        category: {"inventory": values["inventory"], "style_count": len(values["styles"])}
        for category, values in totals.items()
    }


def _category_alerts(
    inventory_rows: list[dict[str, Any]],
    sku_rows: list[dict[str, Any]],
    *,
    today: date,
) -> list[dict[str, Any]]:
    current_date, baseline_date = _snapshot_dates(inventory_rows, today)
    if not current_date or not baseline_date:
        return []

    current = _category_snapshot(inventory_rows, sku_rows, current_date)
    baseline = _category_snapshot(inventory_rows, sku_rows, baseline_date)
    categories = set(current) | set(baseline)
    alerts: list[dict[str, Any]] = []

    for category in categories:
        if _is_excluded_category(category):
            continue
        current_inventory = _to_float(current.get(category, {}).get("inventory"))
        baseline_inventory = _to_float(baseline.get(category, {}).get("inventory"))
        inventory_delta_pct = _pct_delta(current_inventory, baseline_inventory)

        if current_inventory != baseline_inventory and abs(inventory_delta_pct) >= 20:
            direction = "Increase" if inventory_delta_pct > 0 else "Decrease"
            alert = _base_alert(
                alert_type=f"Category Inventory Depth {direction}",
                severity="High" if abs(inventory_delta_pct) >= 50 else "Medium",
                scope="Category",
                subject=category,
                category=category,
                status="Mixed",
                reason=f"{category} inventory depth changed {abs(inventory_delta_pct):.1f}% versus the snapshot around 15 days ago.",
                action="Review buying, replenishment, and sell-through for this category before adding more depth.",
            )
            alert.update(
                {
                    "snapshot_date": current_date.isoformat(),
                    "baseline_snapshot_date": baseline_date.isoformat(),
                    "current_inventory": round(current_inventory, 2),
                    "baseline_inventory": round(baseline_inventory, 2),
                    "inventory_delta_pct": round(inventory_delta_pct, 2),
                }
            )
            alerts.append(alert)

        current_count = _to_float(current.get(category, {}).get("style_count"))
        baseline_count = _to_float(baseline.get(category, {}).get("style_count"))
        sku_count_delta_pct = _pct_delta(current_count, baseline_count)
        if current_count != baseline_count and abs(sku_count_delta_pct) >= 10:
            alert = _base_alert(
                alert_type="Category SKU Count Change",
                severity="High" if abs(sku_count_delta_pct) >= 50 else "Medium",
                scope="Category",
                subject=category,
                category=category,
                status="Mixed",
                reason=f"{category} active style count changed {abs(sku_count_delta_pct):.1f}% over the last 15 days.",
                action="Check whether category movement is planned, ingestion-related, or needs merchandising action.",
            )
            alert.update(
                {
                    "snapshot_date": current_date.isoformat(),
                    "baseline_snapshot_date": baseline_date.isoformat(),
                    "sku_count_current": round(current_count, 2),
                    "sku_count_baseline": round(baseline_count, 2),
                    "sku_count_delta_pct": round(sku_count_delta_pct, 2),
                }
            )
            alerts.append(alert)

    return alerts


def build_anomaly_alerts(
    *,
    sales_rows: list[dict[str, Any]],
    return_rows: list[dict[str, Any]],
    sku_rows: list[dict[str, Any]],
    inventory_rows: list[dict[str, Any]],
    today: date | None = None,
    lead_time_days: int | None = None,
) -> list[dict[str, Any]]:
    """Build style and category anomaly alerts from current fact tables."""
    effective_today = today or date.today()
    effective_lead_time = lead_time_days if lead_time_days is not None else get_settings().lead_time_days
    alerts = [
        *_style_alerts(sales_rows, return_rows, sku_rows, today=effective_today, lead_time_days=effective_lead_time),
        *_category_alerts(inventory_rows, sku_rows, today=effective_today),
    ]
    return sorted(
        alerts,
        key=lambda row: (
            SEVERITY_ORDER.get(_text(row.get("severity")), 99),
            _text(row.get("alert_type")),
            _text(row.get("style_color") or row.get("category_subject") or row.get("category")),
        ),
    )


def filter_anomaly_alerts(
    alerts: list[dict[str, Any]],
    *,
    severity: str | None = None,
    alert_type: str | None = None,
    category: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    filtered = alerts
    if severity:
        severity_value = severity.lower()
        filtered = [row for row in filtered if _text(row.get("severity")).lower() == severity_value]
    if alert_type:
        alert_value = alert_type.lower()
        filtered = [row for row in filtered if _text(row.get("alert_type")).lower() == alert_value]
    if category:
        category_value = category.lower()
        filtered = [row for row in filtered if _text(row.get("category")).lower() == category_value]
    if status:
        status_value = status.lower()
        filtered = [row for row in filtered if _text(row.get("status") or row.get("inventory_status")).lower() == status_value]
    if scope:
        scope_value = scope.lower()
        filtered = [row for row in filtered if _text(row.get("scope")).lower() == scope_value]
    if search:
        search_value = search.lower()
        filtered = [
            row
            for row in filtered
            if search_value
            in " ".join(
                [
                    _text(row.get("style_color")),
                    _text(row.get("category_subject")),
                    _text(row.get("category")),
                    _text(row.get("alert_type")),
                    _text(row.get("reason")),
                ]
            ).lower()
        ]
    return filtered


def summarize_anomaly_alerts(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total": len(alerts),
        "critical": 0,
        "high": 0,
        "medium": 0,
        "monitor": 0,
        "style_alerts": 0,
        "category_alerts": 0,
        "by_type": {},
    }
    for row in alerts:
        severity = _text(row.get("severity")).lower()
        if severity in summary:
            summary[severity] += 1
        if row.get("scope") == "Category":
            summary["category_alerts"] += 1
        else:
            summary["style_alerts"] += 1
        alert_type = _text(row.get("alert_type")) or "Unknown"
        summary["by_type"][alert_type] = summary["by_type"].get(alert_type, 0) + 1
    return summary
