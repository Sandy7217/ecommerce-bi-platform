from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import APIRouter

from backend.config import get_settings
from backend.models.schemas import AssistantChatRequest, AssistantChatResponse
from backend.routers import ads, alerts, categories, forecast, inventory, regional, sales
from backend.routers.common import DEMO_RETURNS, DEMO_SALES, DEMO_SKUS, rows_or_demo
from backend.services.export_safety import safe_cell

router = APIRouter(prefix="/assistant", tags=["assistant"])
AI_NOT_CONFIGURED_MESSAGE = "AI Assistant not configured \u2014 please add API key"
TABLE_FIRST_INSTRUCTION = "Return short, clean answers. Put numeric comparisons in Markdown tables. Avoid long paragraphs."
ADVISORY_WORDS = {
    "action",
    "advice",
    "analyze",
    "analysis",
    "diagnose",
    "full summary",
    "how can",
    "improve",
    "increase",
    "insight",
    "plan",
    "recommend",
    "reduce",
    "suggest",
    "why",
}
REPORT_WORDS = {"csv", "download", "export", "kpi", "list", "report", "show", "table"}
SALES_WORDS = {"sale", "sales", "revenue", "performance"}


SYSTEM_PROMPT = """You are the E-Commerce BI AI Assistant.

Business context:
- Company sells fashion on Myntra, Ajio, Nykaa, Flipkart, Amazon, and TataCliq.
- Categories: NOOS, Green, Yellow, Red, Dead, OOS, Winter, Dog styles.
- Key metrics: MTD Sales, ROS, DOI, OOS%, Return%.
- Assistant can answer questions about sales, inventory, replenishment, and category performance.

Rules:
- Use the supplied live_data_context first. Include actual numbers, style names, marketplace/channel names, dates, and percentages when available.
- Do not give generic answers when live data is present.
- Prefer table-first answers for KPIs, ranked lists, and SKU performance. Avoid dense paragraphs.
- If the user asks for a report, CSV, or chart, explicitly state which rows and chart should be generated.
- When a requested list is empty, state the exact count is 0 and name the filter/criteria used.
- When answering inventory value questions, use the supplied estimated value and repeat the estimate note.
- If a metric is not available in the database, say that directly and use the closest clearly labeled estimate only when supplied in live_data_context.
- Keep answers concise but data-backed. Prefer bullets for ranked lists."""


def _has_real_api_key(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return bool(normalized and not normalized.startswith("your-") and "api-key-here" not in normalized)


def _safe_call(default: Any, fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default


def _top_items(rows: list[dict[str, Any]], key: str, limit: int = 10) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: float(row.get(key) or 0), reverse=True)[:limit]


def _format_inr(value: float) -> str:
    return f"Rs {value:,.2f}"


def _format_pct(value: float) -> str:
    return f"{value:.2f}%"


def _csv_value(value: Any) -> str:
    text = "" if value is None else str(safe_cell(value))
    if any(char in text for char in [",", '"', "\n"]):
      return '"' + text.replace('"', '""') + '"'
    return text


def _make_csv(columns: list[dict[str, str]], rows: list[dict[str, Any]]) -> str:
    keys = [column["key"] for column in columns]
    labels = [column["label"] for column in columns]
    lines = [",".join(_csv_value(label) for label in labels)]
    for row in rows:
        lines.append(",".join(_csv_value(row.get(key)) for key in keys))
    return "\n".join(lines)


def _table(title: str, columns: list[dict[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"title": title, "columns": columns, "rows": rows}


def _line_chart(title: str, rows: list[dict[str, Any]], y_keys: list[dict[str, str]]) -> dict[str, Any]:
    return {"title": title, "type": "line", "xKey": "date", "yKeys": y_keys, "data": rows}


def _contains_any(message: str, words: set[str]) -> bool:
    normalized = message.lower()
    return any(word in normalized for word in words)


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


def _requested_count(message: str, default: int = 4) -> int:
    match = re.search(r"\b([1-9])\s+(suggestion|suggestions|recommendation|recommendations|action|actions)\b", message.lower())
    if match:
        return max(1, min(int(match.group(1)), 6))
    return default


def _classify_intent(message: str) -> str | None:
    normalized = message.lower()
    has_advisory = _contains_any(normalized, ADVISORY_WORDS)
    has_sales = _contains_any(normalized, SALES_WORDS)
    has_report = _contains_any(normalized, REPORT_WORDS)

    if _contains_any(normalized, {"csv", "download", "export"}):
        return "export"
    if _contains_any(normalized, {"replenish", "replenishment", "stockout", "stock out"}):
        return "replenishment"
    if _contains_any(normalized, {"return", "returns", "rto"}):
        if has_advisory or has_sales:
            return "business_analysis"
        return "returns"
    if _contains_any(normalized, {"forecast", "predict", "prediction"}):
        return "forecast"
    if _contains_any(normalized, {"anomaly", "alert", "spike"}):
        return "anomaly"
    if _contains_any(normalized, {"inventory", "stock", "oos", "broken", "dead stock", "slow mover", "slow movers"}):
        return "inventory"
    if _contains_any(normalized, {"marketplace", "channel", "platform", "ads", "pla", "roi"}):
        return "business_analysis" if has_advisory else "sales_report"
    if has_sales and has_report and not has_advisory:
        return "sales_report"
    if has_advisory or has_sales:
        return "business_analysis"
    return None


def _style_token(value: str | None) -> str:
    return re.sub(r"[^a-z0-9.-]", "", str(value or "").lower())


def _find_requested_style(message: str, known_styles: set[str]) -> str | None:
    normalized_message = message.lower()
    normalized_map = {_style_token(style): style for style in known_styles if style}
    for normalized, style in normalized_map.items():
        if normalized and normalized in normalized_message:
            return style
    candidates = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9.-]*-[a-zA-Z0-9][a-zA-Z0-9.-]*", message)
    for candidate in candidates:
        normalized = _style_token(candidate)
        if normalized in normalized_map:
            return normalized_map[normalized]
    return None


def _aggregate_daily(rows: list[dict[str, Any]], returns_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        day = str(row.get("date") or "")
        if not day:
            continue
        item = by_date.setdefault(day, {"date": day, "sales_value": 0.0, "qty": 0, "return_value": 0.0, "return_qty": 0})
        item["sales_value"] += sales._sales_amount(row)
        item["qty"] += int(row.get("qty") or 0)
    for row in returns_rows:
        day = str(row.get("date") or "")
        if not day:
            continue
        item = by_date.setdefault(day, {"date": day, "sales_value": 0.0, "qty": 0, "return_value": 0.0, "return_qty": 0})
        item["return_value"] += float(row.get("return_value") or 0)
        item["return_qty"] += int(row.get("qty") or 0)
    return [by_date[day] for day in sorted(by_date)]


def _style_matches(row: dict[str, Any], style: str) -> bool:
    normalized = _style_token(style)
    style_color = _style_token(str(row.get("style_color") or ""))
    internal_sku = _style_token(str(row.get("internal_sku") or ""))
    return style_color == normalized or internal_sku.startswith(normalized)


def _sku_performance_response(message: str) -> dict[str, Any] | None:
    sales_rows = _safe_call([], sales._sales_rows)
    return_rows = _safe_call([], sales._return_rows)
    inventory_rows = rows_or_demo("sku_master", DEMO_SKUS, limit=5000)
    known_styles = {
        str(row.get("style_color"))
        for row in [*sales_rows, *return_rows, *inventory_rows]
        if row.get("style_color")
    }
    style = _find_requested_style(message, known_styles)
    if not style:
        return None

    sku_sales = [row for row in sales_rows if _style_matches(row, style)]
    sku_returns = [row for row in return_rows if _style_matches(row, style)]
    inventory_row = next((row for row in inventory_rows if _style_token(str(row.get("style_color") or "")) == _style_token(style)), {})
    total_sales = round(sum(sales._sales_amount(row) for row in sku_sales), 2)
    total_qty = sum(int(row.get("qty") or 0) for row in sku_sales)
    return_value = round(sum(float(row.get("return_value") or 0) for row in sku_returns), 2)
    return_qty = sum(int(row.get("qty") or 0) for row in sku_returns)
    return_pct = round(return_qty * 100 / max(total_qty, 1), 2)
    daily_rows = _aggregate_daily(sku_sales, sku_returns)

    summary_columns = [
        {"key": "metric", "label": "Metric"},
        {"key": "value", "label": "Value"},
    ]
    summary_rows = [
        {"metric": "Style / SKU", "value": style},
        {"metric": "Sales", "value": _format_inr(total_sales)},
        {"metric": "Qty sold", "value": total_qty},
        {"metric": "Return value", "value": _format_inr(return_value)},
        {"metric": "Return qty", "value": return_qty},
        {"metric": "Return %", "value": _format_pct(return_pct)},
        {"metric": "Inventory Qty", "value": inventory_row.get("total_inventory", "NA")},
        {"metric": "Category", "value": inventory_row.get("category_new") or "NA"},
        {"metric": "Status", "value": inventory_row.get("inventory_status") or inventory_row.get("status") or "NA"},
    ]
    daily_columns = [
        {"key": "date", "label": "Date"},
        {"key": "sales_value", "label": "Sales"},
        {"key": "qty", "label": "Qty"},
        {"key": "return_value", "label": "Returns"},
        {"key": "return_qty", "label": "Return Qty"},
    ]
    answer = (
        f"SKU performance for {style}. "
        f"Sales are {_format_inr(total_sales)} on {total_qty} units, with {return_qty} returned units ({_format_pct(return_pct)}). "
        f"Current inventory is {inventory_row.get('total_inventory', 'NA')} units."
    )
    return {
        "answer": answer,
        "intent": "sku_lookup",
        "used_sources": ["sales", "returns", "inventory"],
        "tables": [_table("SKU performance summary", summary_columns, summary_rows), _table("Daily SKU trend", daily_columns, daily_rows[-30:])],
        "charts": [_line_chart("SKU sales and returns trend", daily_rows, [{"key": "sales_value", "label": "Sales", "color": "#0f9488"}, {"key": "return_value", "label": "Returns", "color": "#dc2626"}])] if daily_rows else [],
        "csv_files": [{"filename": f"{_style_token(style)}-performance.csv", "content": _make_csv(daily_columns, daily_rows)}],
    }


def _sales_performance_response(message: str) -> dict[str, Any] | None:
    if not _contains_any(message, {"sale", "sales", "revenue", "performance", "report", "csv", "chart"}):
        return None

    kpis = _safe_call({}, sales.sales_kpis)
    top_products = _safe_call([], sales.top_products, limit=10)
    marketplace_rows = _safe_call([], sales.marketplace_summary)
    trend_rows = _safe_call([], sales.sales_trend)
    return_trend = _safe_call([], sales._return_rows)
    daily_rows = _aggregate_daily(_safe_call([], sales._sales_rows), return_trend)

    metric_columns = [{"key": "metric", "label": "Metric"}, {"key": "value", "label": "Value"}]
    metric_rows = [
        {"metric": "Sales", "value": _format_inr(float(kpis.get("mtd_sales") or 0))},
        {"metric": "Qty sold", "value": int(kpis.get("mtd_qty") or 0)},
        {"metric": "ASP", "value": _format_inr(float(kpis.get("asp") or 0))},
        {"metric": "Return %", "value": _format_pct(float(kpis.get("return_pct") or 0))},
        {"metric": "Return value", "value": _format_inr(float(kpis.get("return_value") or 0))},
        {"metric": "Sales growth", "value": _format_pct(float(kpis.get("sales_growth_pct") or 0))},
    ]
    product_columns = [
        {"key": "style_color", "label": "Style"},
        {"key": "revenue", "label": "Sales"},
        {"key": "qty", "label": "Qty"},
        {"key": "ros", "label": "ROS"},
        {"key": "return_pct", "label": "Return %"},
    ]
    marketplace_columns = [
        {"key": "marketplace", "label": "Marketplace"},
        {"key": "sales_value", "label": "Sales"},
        {"key": "sales_qty", "label": "Qty"},
        {"key": "return_value", "label": "Returns"},
        {"key": "return_pct", "label": "Return %"},
        {"key": "net_sales", "label": "Net Sales"},
    ]
    answer = (
        f"Sales are {_format_inr(float(kpis.get('mtd_sales') or 0))} on {int(kpis.get('mtd_qty') or 0)} units. "
        f"Return rate is {_format_pct(float(kpis.get('return_pct') or 0))}."
    )
    csv_rows = top_products or marketplace_rows or trend_rows
    csv_columns = product_columns if top_products else marketplace_columns
    return {
        "answer": answer,
        "intent": "sales_report",
        "used_sources": ["sales", "returns", "marketplace"],
        "tables": [
            _table("Sales KPI summary", metric_columns, metric_rows),
            _table("Top styles by sales", product_columns, top_products),
            _table("Marketplace performance", marketplace_columns, marketplace_rows),
        ],
        "charts": [_line_chart("Sales and returns trend", daily_rows, [{"key": "sales_value", "label": "Sales", "color": "#0f9488"}, {"key": "return_value", "label": "Returns", "color": "#dc2626"}])] if daily_rows else [],
        "csv_files": [{"filename": "sales-performance-report.csv", "content": _make_csv(csv_columns, csv_rows)}],
    }


def _summary_cards(context: dict[str, Any]) -> list[dict[str, str]]:
    kpis = context.get("sales_kpis_mtd") or {}
    inventory_kpis = context.get("inventory_kpis") or {}
    replenishment_summary = (context.get("replenishment_plan") or {}).get("summary") or {}
    forecast_summary = (context.get("sales_returns_forecast") or {}).get("summary") or {}
    anomaly_summary = (context.get("anomaly_alerts") or {}).get("summary") or {}
    return [
        {
            "label": "MTD Sales",
            "value": _format_inr(_to_float(kpis.get("mtd_sales"))),
            "detail": f"{_to_int(kpis.get('mtd_qty'))} units | growth {_format_pct(_to_float(kpis.get('sales_growth_pct')))}",
            "tone": "red" if _to_float(kpis.get("sales_growth_pct")) < 0 else "green",
        },
        {
            "label": "Return Rate",
            "value": _format_pct(_to_float(kpis.get("return_pct"))),
            "detail": f"{_to_int(kpis.get('return_qty'))} return units | change {_format_pct(_to_float(kpis.get('return_pct_change')))}",
            "tone": "red" if _to_float(kpis.get("return_pct")) >= 30 else "orange",
        },
        {
            "label": "Inventory",
            "value": str(_to_int(inventory_kpis.get("total_inventory"))),
            "detail": f"{_to_int(inventory_kpis.get('total_styles'))} styles | OOS {_to_int(inventory_kpis.get('oos_count'))}",
            "tone": "neutral",
        },
        {
            "label": "Urgent Replenishment",
            "value": str(_to_int(replenishment_summary.get("urgent_styles"))),
            "detail": f"Recommended qty {_to_int(replenishment_summary.get('recommended_qty'))}",
            "tone": "red" if _to_int(replenishment_summary.get("urgent_styles")) else "green",
        },
        {
            "label": "Forecast Net Sales",
            "value": _format_inr(_to_float(forecast_summary.get("forecast_net_sales"))),
            "detail": f"Forecast return {_format_pct(_to_float(forecast_summary.get('forecast_return_pct')))}",
            "tone": "neutral",
        },
        {
            "label": "Anomaly Alerts",
            "value": str(_to_int(anomaly_summary.get("total"))),
            "detail": f"Critical {_to_int(anomaly_summary.get('critical'))} | High {_to_int(anomaly_summary.get('high'))}",
            "tone": "red" if _to_int(anomaly_summary.get("critical")) else "neutral",
        },
    ]


def _top_high_return_styles(context: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    overall_return_pct = _to_float((context.get("sales_kpis_mtd") or {}).get("return_pct"))
    threshold = max(overall_return_pct, 25.0)
    rows = [
        row
        for row in context.get("top_10_styles_by_revenue") or []
        if _to_float(row.get("return_pct")) >= threshold and _to_int(row.get("qty")) > 0
    ]
    return sorted(rows, key=lambda row: (_to_float(row.get("return_pct")), _to_float(row.get("revenue"))), reverse=True)[:limit]


def _clean_marketplaces(context: dict[str, Any]) -> list[dict[str, Any]]:
    overall_return_pct = _to_float((context.get("sales_kpis_mtd") or {}).get("return_pct"))
    rows = [
        row
        for row in context.get("marketplace_sales_returns") or []
        if _to_float(row.get("sales_value")) > 0 and _to_float(row.get("return_pct")) < max(overall_return_pct, 1)
    ]
    return sorted(rows, key=lambda row: _to_float(row.get("net_sales")), reverse=True)[:3]


def _high_return_marketplaces(context: dict[str, Any]) -> list[dict[str, Any]]:
    overall_return_pct = _to_float((context.get("sales_kpis_mtd") or {}).get("return_pct"))
    rows = [
        row
        for row in context.get("marketplace_sales_returns") or []
        if _to_float(row.get("return_pct")) >= max(overall_return_pct, 25)
    ]
    return sorted(rows, key=lambda row: _to_float(row.get("return_pct")), reverse=True)[:3]


def _urgent_replenishment_items(context: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    items = (context.get("replenishment_plan") or {}).get("items") or []
    urgent = [row for row in items if str(row.get("urgency") or "").startswith(("P0", "P1"))]
    return sorted(urgent, key=lambda row: _to_int(row.get("recommended_replenishment_qty")), reverse=True)[:limit]


def _recommendation(
    *,
    priority: str,
    title: str,
    action: str,
    reason: str,
    evidence: str,
    impact: str,
    next_step: str,
    styles: list[str] | None = None,
    channels: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "title": title,
        "action": action,
        "reason": reason,
        "evidence": evidence,
        "impact": impact,
        "next_step": next_step,
        "styles": styles or [],
        "channels": channels or [],
    }


def _build_recommendations(intent: str, context: dict[str, Any], message: str) -> list[dict[str, Any]]:
    del message
    kpis = context.get("sales_kpis_mtd") or {}
    replenishment_summary = (context.get("replenishment_plan") or {}).get("summary") or {}
    forecast_summary = (context.get("sales_returns_forecast") or {}).get("summary") or {}
    anomaly_payload = context.get("anomaly_alerts") or {}
    anomaly_summary = anomaly_payload.get("summary") or {}
    high_return_styles = _top_high_return_styles(context)
    clean_marketplaces = _clean_marketplaces(context)
    high_return_marketplaces = _high_return_marketplaces(context)
    urgent_replenishment = _urgent_replenishment_items(context)
    recommendations: list[dict[str, Any]] = []

    if high_return_styles:
        style_names = [str(row.get("style_color")) for row in high_return_styles[:3]]
        worst = high_return_styles[0]
        recommendations.append(
            _recommendation(
                priority="P1",
                title="Reduce returns on high-volume styles",
                action=f"Audit size, fit, image accuracy, and marketplace issue tags for {', '.join(style_names)}.",
                reason="These styles are already selling, so return-rate fixes protect net sales without needing new demand.",
                evidence=(
                    f"{worst.get('style_color')} has return {_format_pct(_to_float(worst.get('return_pct')))} "
                    f"against MTD return {_format_pct(_to_float(kpis.get('return_pct')))}."
                ),
                impact="Lower return leakage on styles that already contribute meaningful revenue.",
                next_step="Start with return reason tags, size exchange pattern, and PDP content changes before scaling spend.",
                styles=style_names,
            )
        )

    if _to_float(kpis.get("sales_growth_pct")) < 0:
        top_styles = context.get("top_10_styles_by_revenue") or []
        winner_names = [str(row.get("style_color")) for row in top_styles[:3]]
        recommendations.append(
            _recommendation(
                priority="P1",
                title="Recover the MTD sales decline through proven winners",
                action=f"Increase availability, visibility, and marketplace focus for {', '.join(winner_names) or 'top revenue styles'}.",
                reason="Current sales growth is negative, so the fastest recovery path is to push styles already converting this month.",
                evidence=f"MTD sales growth is {_format_pct(_to_float(kpis.get('sales_growth_pct')))} on {_to_int(kpis.get('mtd_qty'))} sold units.",
                impact="Improves near-term sales without expanding risk into unproven styles.",
                next_step="Create a top-style action list by marketplace: stock, ad push, visibility slot, and discount check.",
                styles=winner_names,
            )
        )

    if urgent_replenishment:
        urgent_names = [str(row.get("style_color")) for row in urgent_replenishment[:3]]
        recommendations.append(
            _recommendation(
                priority="P0",
                title="Clear urgent NOOS replenishment gaps",
                action=f"Place replenishment for urgent styles such as {', '.join(urgent_names)}.",
                reason="Stockouts on consistent NOOS sellers cap sales even when demand exists.",
                evidence=(
                    f"{_to_int(replenishment_summary.get('urgent_styles'))} urgent styles and "
                    f"{_to_int(replenishment_summary.get('recommended_qty'))} recommended units are in the hybrid plan."
                ),
                impact="Prevents avoidable lost sales on styles already eligible for replenishment.",
                next_step="Review the replenishment page, approve P0/P1 styles first, and check size split before PO creation.",
                styles=urgent_names,
            )
        )

    if clean_marketplaces or high_return_marketplaces:
        clean_names = [str(row.get("marketplace")) for row in clean_marketplaces]
        risk_names = [str(row.get("marketplace")) for row in high_return_marketplaces]
        best = clean_marketplaces[0] if clean_marketplaces else {}
        risk = high_return_marketplaces[0] if high_return_marketplaces else {}
        recommendations.append(
            _recommendation(
                priority="P2",
                title="Shift growth toward cleaner net-sales channels",
                action=f"Protect or scale {', '.join(clean_names) or 'low-return channels'} and review {', '.join(risk_names) or 'high-return channels'}.",
                reason="Return percentage changes the real value of sales by marketplace.",
                evidence=(
                    f"{best.get('marketplace', 'Best channel')} return {_format_pct(_to_float(best.get('return_pct')))}; "
                    f"{risk.get('marketplace', 'risk channel')} return {_format_pct(_to_float(risk.get('return_pct')))}."
                ),
                impact="Improves net sales quality while reducing reverse-logistics drag.",
                next_step="Move incremental ads and stock depth toward channels with lower return percentage and positive net sales.",
                channels=clean_names + risk_names,
            )
        )

    if _to_float(forecast_summary.get("forecast_sales_value")) > 0:
        recommendations.append(
            _recommendation(
                priority="P2",
                title="Use the forecast as a weekly operating target",
                action="Compare current MTD run rate against forecast sales and forecast return percentage every week.",
                reason="Forecast variance highlights whether the issue is demand, returns, or inventory availability.",
                evidence=(
                    f"Forecast sales {_format_inr(_to_float(forecast_summary.get('forecast_sales_value')))}, "
                    f"net {_format_inr(_to_float(forecast_summary.get('forecast_net_sales')))}, "
                    f"return {_format_pct(_to_float(forecast_summary.get('forecast_return_pct')))}."
                ),
                impact="Keeps sales growth and return-control actions tied to measurable targets.",
                next_step="Track forecast gap by channel and assign weekly owners for the biggest variance.",
            )
        )

    if _to_int(anomaly_summary.get("total")):
        first_alert = ((anomaly_payload.get("items") or [{}])[0]) or {}
        recommendations.append(
            _recommendation(
                priority="P1" if _to_int(anomaly_summary.get("critical")) else "P2",
                title="Act on current anomaly alerts",
                action="Review critical sales, return, and inventory anomaly alerts before scaling buying or ads.",
                reason="Anomalies identify recent behavior shifts that static MTD KPIs can hide.",
                evidence=f"{_to_int(anomaly_summary.get('total'))} anomaly alerts, including {_to_int(anomaly_summary.get('critical'))} critical.",
                impact="Prevents scaling styles or categories where sales and returns are moving in the wrong direction.",
                next_step=f"Start with {first_alert.get('style_color') or first_alert.get('category') or 'the first critical alert'} in Reports.",
            )
        )

    pla_summary = context.get("ad_roi_summary") or {}
    if _to_float(pla_summary.get("pla_spend")) > 0:
        recommendations.append(
            _recommendation(
                priority="P3",
                title="Tie PLA scaling to net sales quality",
                action="Scale PLA only on styles and channels where sales, returns, and inventory are all healthy.",
                reason="Ad ROI can look acceptable before returns and stockouts are considered.",
                evidence=f"PLA spend {_format_inr(_to_float(pla_summary.get('pla_spend')))} with ROI {_to_float(pla_summary.get('pla_roi')):.2f}.",
                impact="Reduces wasted spend on styles that sell but return heavily or cannot be fulfilled.",
                next_step="Join PLA performance with high-return style and replenishment tables before increasing budgets.",
            )
        )

    if intent == "replenishment":
        recommendations.sort(key=lambda row: 0 if "replenishment" in row["title"].lower() else 1)
    elif intent == "returns":
        recommendations.sort(key=lambda row: 0 if "return" in row["title"].lower() else 1)
    elif intent == "forecast":
        recommendations.sort(key=lambda row: 0 if "forecast" in row["title"].lower() else 1)
    elif intent == "anomaly":
        recommendations.sort(key=lambda row: 0 if "anomaly" in row["title"].lower() else 1)
    elif intent == "inventory":
        recommendations.sort(key=lambda row: 0 if "replenishment" in row["title"].lower() else 1)
    return recommendations


def _business_metric_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    kpis = context.get("sales_kpis_mtd") or {}
    inventory_kpis = context.get("inventory_kpis") or {}
    replenishment_summary = (context.get("replenishment_plan") or {}).get("summary") or {}
    forecast_summary = (context.get("sales_returns_forecast") or {}).get("summary") or {}
    anomaly_summary = (context.get("anomaly_alerts") or {}).get("summary") or {}
    ad_summary = context.get("ad_roi_summary") or {}
    return [
        {"metric": "MTD Sales", "value": _format_inr(_to_float(kpis.get("mtd_sales")))},
        {"metric": "MTD Qty", "value": _to_int(kpis.get("mtd_qty"))},
        {"metric": "Sales Growth", "value": _format_pct(_to_float(kpis.get("sales_growth_pct")))},
        {"metric": "Return %", "value": _format_pct(_to_float(kpis.get("return_pct")))},
        {"metric": "Return Value", "value": _format_inr(_to_float(kpis.get("return_value")))},
        {"metric": "Inventory Units", "value": _to_int(inventory_kpis.get("total_inventory"))},
        {"metric": "Urgent Replenishment Styles", "value": _to_int(replenishment_summary.get("urgent_styles"))},
        {"metric": "Recommended Replenishment Qty", "value": _to_int(replenishment_summary.get("recommended_qty"))},
        {"metric": "Forecast Net Sales", "value": _format_inr(_to_float(forecast_summary.get("forecast_net_sales")))},
        {"metric": "Anomaly Alerts", "value": _to_int(anomaly_summary.get("total"))},
        {"metric": "PLA ROI", "value": f"{_to_float(ad_summary.get('pla_roi')):.2f}"},
    ]


def _recommendation_rows(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "priority": row.get("priority"),
            "action": row.get("title"),
            "evidence": row.get("evidence"),
            "impact": row.get("impact"),
            "next_step": row.get("next_step"),
        }
        for row in recommendations
    ]


def _business_answer(intent: str, context: dict[str, Any], recommendations: list[dict[str, Any]]) -> str:
    kpis = context.get("sales_kpis_mtd") or {}
    intro = (
        f"Analyst view: sales are {_format_inr(_to_float(kpis.get('mtd_sales')))} on {_to_int(kpis.get('mtd_qty'))} units, "
        f"sales growth is {_format_pct(_to_float(kpis.get('sales_growth_pct')))}, and return rate is {_format_pct(_to_float(kpis.get('return_pct')))}."
    )
    if intent == "replenishment":
        intro = "Replenishment analyst view: " + intro
    elif intent == "returns":
        intro = "Returns analyst view: " + intro
    elif intent == "inventory":
        intro = "Inventory analyst view: " + intro
    elif intent == "forecast":
        intro = "Forecast analyst view: " + intro
    elif intent == "anomaly":
        intro = "Anomaly analyst view: " + intro
    lines = [intro, "Recommended actions:"]
    for index, item in enumerate(recommendations, start=1):
        lines.append(f"{index}. {item['title']}: {item['action']} Evidence: {item['evidence']}")
    return "\n".join(lines)


def _business_analysis_response(message: str, intent: str) -> dict[str, Any]:
    context = _build_live_context()
    recommendations = _build_recommendations(intent, context, message)
    recommendations = recommendations[: _requested_count(message)]
    summary_cards = _summary_cards(context)
    metric_columns = [{"key": "metric", "label": "Metric"}, {"key": "value", "label": "Value"}]
    recommendation_columns = [
        {"key": "priority", "label": "Priority"},
        {"key": "action", "label": "Action"},
        {"key": "evidence", "label": "Evidence"},
        {"key": "impact", "label": "Impact"},
        {"key": "next_step", "label": "Next Step"},
    ]
    high_return_columns = [
        {"key": "style_color", "label": "Style"},
        {"key": "revenue", "label": "Sales"},
        {"key": "qty", "label": "Qty"},
        {"key": "ros", "label": "ROS"},
        {"key": "return_pct", "label": "Return %"},
    ]
    urgent_columns = [
        {"key": "style_color", "label": "Style"},
        {"key": "category_new", "label": "Category"},
        {"key": "inventory_status", "label": "Status"},
        {"key": "recommended_replenishment_qty", "label": "Reco Qty"},
        {"key": "urgency", "label": "Urgency"},
    ]
    recommendation_rows = _recommendation_rows(recommendations)
    tables = [
        _table("Business KPI summary", metric_columns, _business_metric_rows(context)),
        _table("Recommendation evidence", recommendation_columns, recommendation_rows),
    ]
    high_return_styles = _top_high_return_styles(context)
    if high_return_styles:
        tables.append(_table("High-return selling styles", high_return_columns, high_return_styles))
    urgent_items = _urgent_replenishment_items(context)
    if urgent_items:
        tables.append(_table("Urgent replenishment styles", urgent_columns, urgent_items))

    daily_rows = context.get("daily_sales_returns_trend") or []
    charts = [
        _line_chart(
            "Sales and returns trend",
            daily_rows,
            [
                {"key": "sales_value", "label": "Sales", "color": "#0f9488"},
                {"key": "return_value", "label": "Returns", "color": "#dc2626"},
            ],
        )
    ] if daily_rows else []
    used_sources = [
        "sales",
        "returns",
        "inventory",
        "replenishment",
        "forecast",
        "anomaly_alerts",
        "ads",
        "regional",
    ]
    return {
        "answer": _business_answer(intent, context, recommendations),
        "intent": intent,
        "summary_cards": summary_cards,
        "recommendations": recommendations,
        "evidence": recommendation_rows,
        "tables": tables,
        "charts": charts,
        "csv_files": [{"filename": "business-analysis-evidence.csv", "content": _make_csv(recommendation_columns, recommendation_rows)}],
        "used_sources": used_sources,
    }


def _structured_response(message: str) -> dict[str, Any] | None:
    sku_response = _sku_performance_response(message)
    if sku_response:
        return sku_response
    intent = _classify_intent(message)
    if intent in {"business_analysis", "replenishment", "returns", "inventory", "forecast", "anomaly"}:
        return _business_analysis_response(message, intent)
    if intent in {"sales_report", "export"}:
        return _sales_performance_response(message)
    return None


def _build_live_context() -> dict[str, Any]:
    sales_kpis = _safe_call({}, sales.sales_kpis)
    top_products = _safe_call([], sales.top_products, limit=10)
    marketplace_rows = _safe_call([], sales.marketplace_summary)
    category_rows = _safe_call([], sales.sales_by_category)
    sales_rows = _safe_call([], sales._sales_rows)
    return_rows = _safe_call([], sales._return_rows)
    inventory_kpis = _safe_call({}, inventory.inventory_kpis)
    inventory_rows = _safe_call({"items": []}, inventory.inventory_styles, page=1, limit=200).get("items", [])
    matrix_rows = _safe_call([], inventory.category_status_matrix)
    replenishment_plan = _safe_call({"summary": {}, "items": [], "charts": {}}, inventory.replenishment_plan, page=1, limit=50)
    potential_noos = _safe_call({"items": []}, categories.potential_noos, page=1, limit=10).get("items", [])
    pla_rows = _safe_call([], ads.pla_performance)
    state_rows = _safe_call([], regional.state_heatmap)
    forecast_payload = _safe_call({"summary": {}, "history": [], "forecast": []}, forecast.sales_returns_forecast)
    anomaly_payload = _safe_call({"summary": {}, "items": []}, alerts.anomaly_alerts, limit=50)
    daily_rows = _aggregate_daily(sales_rows, return_rows)[-30:]

    noos_categories = [row for row in category_rows if "NOOS" in str(row.get("category") or "")]
    oos_risk = [
        row
        for row in inventory_rows
        if str(row.get("status") or row.get("inventory_status") or "").upper() != "OOS"
        and 0 < float(row.get("doi") or 0) <= 15
    ]
    broken_rows = [
        row
        for row in inventory_rows
        if str(row.get("status") or row.get("inventory_status") or "").upper() == "BROKEN"
    ]
    discontinue_rows = [
        row
        for row in inventory_rows
        if str(row.get("category_new") or "").lower() == "discontinue" and int(row.get("total_inventory") or 0) > 0
    ]
    asp = float(sales_kpis.get("asp") or 0) if isinstance(sales_kpis, dict) else 0
    broken_inventory_units = sum(int(row.get("total_inventory") or 0) for row in broken_rows)
    pla_spend = sum(float(row.get("spend") or 0) for row in pla_rows)
    pla_revenue = sum(float(row.get("revenue") or 0) for row in pla_rows)
    noos_sales_value = sum(float(row.get("sales_value") or 0) for row in noos_categories)
    noos_qty = sum(int(row.get("qty") or 0) for row in noos_categories)
    noos_sku_count = sum(int(row.get("sku_count") or 0) for row in noos_categories)

    return {
        "sales_kpis_mtd": sales_kpis,
        "top_10_styles_by_revenue": top_products,
        "marketplace_sales_returns": marketplace_rows,
        "highest_return_marketplaces": _top_items(marketplace_rows, "return_pct", 6),
        "category_sales_performance": category_rows,
        "noos_sales_performance": {
            "categories": noos_categories,
            "total_sales_value": round(noos_sales_value, 2),
            "total_qty": noos_qty,
            "total_sku_count": noos_sku_count,
        },
        "inventory_kpis": inventory_kpis,
        "inventory_category_status_matrix": matrix_rows,
        "replenishment_plan": replenishment_plan,
        "sales_returns_forecast": forecast_payload,
        "anomaly_alerts": anomaly_payload,
        "daily_sales_returns_trend": daily_rows,
        "oos_risk_next_15_days_summary": {
            "criteria": "inventory status is not OOS and DOI is greater than 0 and less than or equal to 15",
            "style_count": len(oos_risk),
            "styles": sorted(oos_risk, key=lambda row: float(row.get("doi") or 999))[:20],
        },
        "broken_inventory_summary": {
            "broken_style_count": len(broken_rows),
            "broken_inventory_units": broken_inventory_units,
            "estimated_value_at_mtd_asp": round(broken_inventory_units * asp, 2),
            "estimate_note": "Inventory value is estimated using MTD ASP because sku-level cost/MRP inventory valuation is not stored in sku_master.",
            "top_broken_styles": _top_items(broken_rows, "total_inventory", 10),
        },
        "potential_noos_queue": potential_noos,
        "discontinue_inventory_summary": {
            "style_count_with_inventory": len(discontinue_rows),
            "inventory_units": sum(int(row.get("total_inventory") or 0) for row in discontinue_rows),
            "top_styles": _top_items(discontinue_rows, "total_inventory", 10),
        },
        "marketplace_focus_summary": {
            "best_low_return_marketplaces": sorted(marketplace_rows, key=lambda row: (float(row.get("return_pct") or 999), -float(row.get("net_sales") or 0)))[:5],
            "highest_sales_marketplaces": sorted(marketplace_rows, key=lambda row: float(row.get("sales_value") or 0), reverse=True)[:5],
            "roi_note": "True marketplace ROI requires marketplace ad spend. When ad spend is unavailable, use net sales and return percentage as ROI proxies.",
        },
        "ad_roi_summary": {
            "pla_spend": round(pla_spend, 2),
            "pla_revenue": round(pla_revenue, 2),
            "pla_roi": round(pla_revenue / pla_spend, 2) if pla_spend else 0,
            "note": "PLA data is marketplace-specific when uploaded; marketplace comparison should combine this with sales/returns by marketplace.",
        },
        "top_states": state_rows[:10],
        "samples": {
            "sales_sample": sales_rows[:5] or rows_or_demo("sales_fact", DEMO_SALES, limit=5),
            "inventory_sample": rows_or_demo("sku_master", DEMO_SKUS, limit=5),
            "returns_sample": return_rows[:5] or rows_or_demo("returns_fact", DEMO_RETURNS, limit=5),
        },
    }


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(payload: AssistantChatRequest):
    structured = _structured_response(payload.message)
    if structured:
        return AssistantChatResponse(**structured, context={"source": "structured_assistant"})

    context = _build_live_context()

    settings = get_settings()
    context_text = json.dumps(context, default=str)
    conversation_history = [
        {"role": item.role, "content": item.content}
        for item in payload.conversation_history
        if item.role in {"user", "assistant"}
    ]
    user_message = {"role": "user", "content": f"{payload.message}\n\n{TABLE_FIRST_INSTRUCTION}\n\nlive_data_context: {context_text}"}

    if _has_real_api_key(settings.anthropic_api_key):
        messages = [*conversation_history, user_message]
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"},
            json={"model": settings.anthropic_model, "max_tokens": 1000, "system": SYSTEM_PROMPT, "messages": messages},
            timeout=30,
        )
        try:
            response.raise_for_status()
            data = response.json()
            text = "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
            return AssistantChatResponse(answer=text, context=context)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                return AssistantChatResponse(answer=AI_NOT_CONFIGURED_MESSAGE, context=context)
            raise

    if _has_real_api_key(settings.openai_api_key):
        from openai import OpenAI

        try:
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *conversation_history,
                    user_message,
                ],
                max_tokens=1000,
            )
            return AssistantChatResponse(answer=response.choices[0].message.content or "", context=context)
        except Exception as exc:
            if "401" in str(exc) or "invalid_api_key" in str(exc).lower():
                return AssistantChatResponse(answer=AI_NOT_CONFIGURED_MESSAGE, context=context)
            raise

    return AssistantChatResponse(answer=AI_NOT_CONFIGURED_MESSAGE, context=context)
