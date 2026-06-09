from __future__ import annotations

from datetime import date
from typing import Any

from backend.config import get_settings
from backend.services.category_engine import compute_doi, get_replenishment_priority


def resolved_doi(style: dict[str, Any]) -> float:
    status = str(style.get("inventory_status") or style.get("status") or "").upper()
    ros = float(style.get("ros_30d") or style.get("ros") or 0)
    total_inventory = int(style.get("total_inventory") or 0)
    if status == "OOS":
        return 0.0
    if ros == 0 and total_inventory > 0:
        return 999.0
    return float(style.get("doi") or compute_doi(total_inventory, ros))


def classify_doi_alert(doi: float, inventory_status: str) -> dict[str, Any]:
    lead_time = get_settings().lead_time_days
    if inventory_status == "OOS" or doi == 0:
        return {"level": "Critical", "priority": "P0 - Critical OOS", "action": "Immediate WhatsApp alert"}
    if doi < 15:
        return {"level": "Urgent", "priority": "P1 - Urgent Replenishment", "action": "Urgent replenishment"}
    if doi < lead_time:
        return {"level": "High Risk", "priority": "P2 - High Risk", "action": "Plan replenishment"}
    if doi < 90:
        return {"level": "Monitor", "priority": "Monitor", "action": "Watch"}
    return {"level": "Safe", "priority": "Do Not Replenish", "action": "No action needed"}


def build_replenishment_rows(styles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for style in styles:
        status = style.get("inventory_status") or style.get("status") or "UNKNOWN"
        doi = resolved_doi({**style, "inventory_status": status})
        rows.append(
            {
                **style,
                "doi": doi,
                "priority": get_replenishment_priority(doi, status),
                "alert": classify_doi_alert(doi, status),
            }
        )
    return rows


def build_alert_count(styles: list[dict[str, Any]]) -> dict[str, int]:
    replenishment_rows = build_replenishment_rows(styles)
    oos_styles: set[str] = set()
    p0_p1_styles: set[str] = set()
    for row in replenishment_rows:
        style = str(row.get("style_color") or "").strip()
        if not style:
            continue
        status = str(row.get("inventory_status") or row.get("status") or "").upper()
        priority = str(row.get("priority") or "")
        if status == "OOS":
            oos_styles.add(style)
        if priority.startswith(("P0", "P1")):
            p0_p1_styles.add(style)
    actionable_styles = oos_styles | p0_p1_styles
    return {
        "count": len(actionable_styles),
        "oos_count": len(oos_styles),
        "p0_p1_count": len(p0_p1_styles),
    }


def detect_fast_movers(styles: list[dict[str, Any]], multiplier: float = 1.5) -> list[dict[str, Any]]:
    movers: list[dict[str, Any]] = []
    for style in styles:
        ros_7d = float(style.get("ros_7d") or 0)
        ros_30d = float(style.get("ros_30d") or 0)
        if ros_30d > 0 and ros_7d > ros_30d * multiplier:
            movers.append({**style, "growth_flag": "fast_mover", "growth_ratio": round(ros_7d / ros_30d, 2)})
    return sorted(movers, key=lambda row: row["growth_ratio"], reverse=True)


def build_daily_brief(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": metrics.get("date", date.today().isoformat()),
        "sales_cr": metrics.get("sales_cr", 0),
        "qty": metrics.get("qty", 0),
        "return_pct": metrics.get("return_pct", 0),
        "oos_pct": metrics.get("oos_pct", 0),
        "oos_count": metrics.get("oos_count", 0),
        "broken_pct": metrics.get("broken_pct", 0),
        "fast_movers": metrics.get("fast_movers", []),
        "urgent_count": metrics.get("urgent_count", 0),
        "top_channel": metrics.get("top_channel", "Unknown"),
    }
