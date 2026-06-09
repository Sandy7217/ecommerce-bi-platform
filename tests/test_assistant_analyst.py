from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


NO_AI_SETTINGS = SimpleNamespace(
    anthropic_api_key=None,
    anthropic_model="claude-sonnet-4-20250514",
    openai_api_key=None,
)


def _sales_row(day: str, style: str, value: float, qty: int, channel: str = "MYNTRAPPMP") -> dict:
    return {
        "date": day,
        "style_color": style,
        "internal_sku": style,
        "selling_price": value / max(qty, 1),
        "qty": qty,
        "channel": channel,
        "marketplace": channel,
        "source": "myntra_orders",
    }


def _return_row(day: str, style: str, value: float, qty: int, channel: str = "MYNTRAPPMP") -> dict:
    return {
        "date": day,
        "style_color": style,
        "internal_sku": style,
        "return_value": value,
        "qty": qty,
        "channel": channel,
    }


def _assistant_source_patches():
    kpis = {
        "mtd_sales": 25882235.53,
        "mtd_qty": 22141,
        "asp": 1168.97,
        "return_pct": 33.97,
        "return_qty": 7520,
        "return_value": 7532805.77,
        "sales_growth_pct": -18.61,
        "qty_growth_pct": -12.3,
        "return_pct_change": 4.2,
        "date": "2026-05-24",
    }
    top_products = [
        {"style_color": "23ssnm016-seashellpink", "revenue": 891000, "qty": 667, "ros": 28, "return_pct": 16.19},
        {"style_color": "23ssnm001-pink", "revenue": 619000, "qty": 733, "ros": 31, "return_pct": 34.79},
        {"style_color": "nm424-cream", "revenue": 464000, "qty": 544, "ros": 23, "return_pct": 33.27},
    ]
    marketplace_rows = [
        {"marketplace": "Myntra", "sales_value": 15000000, "sales_qty": 12000, "return_value": 5400000, "return_qty": 4200, "return_pct": 35.0, "net_sales": 9600000},
        {"marketplace": "Ajio", "sales_value": 4200000, "sales_qty": 3000, "return_value": 800000, "return_qty": 450, "return_pct": 15.0, "net_sales": 3400000},
    ]
    sales_rows = [
        _sales_row("2026-05-22", "23ssnm016-seashellpink", 500000, 380),
        _sales_row("2026-05-23", "23ssnm001-pink", 619000, 733),
        _sales_row("2026-05-24", "nm424-cream", 464000, 544, "AJIO_DROPSHIP"),
    ]
    return_rows = [
        _return_row("2026-05-23", "23ssnm001-pink", 215000, 255),
        _return_row("2026-05-24", "nm424-cream", 154000, 181, "AJIO_DROPSHIP"),
    ]
    replenishment = {
        "summary": {
            "urgent_styles": 11,
            "recommended_qty": 7600,
            "eligible_styles": 69,
            "no_replenishment_styles": 1854,
            "manual_pending_qty": 0,
        },
        "items": [
            {
                "style_color": "23ssnm001-pink",
                "category_new": "NOOS",
                "inventory_status": "OOS",
                "recommended_replenishment_qty": 1100,
                "urgency": "P0 - Urgent",
                "replenishment_reason": "Eligible NOOS with consistent sales",
            }
        ],
    }
    forecast = {
        "summary": {
            "forecast_sales_value": 31000000,
            "forecast_return_value": 9500000,
            "forecast_net_sales": 21500000,
            "forecast_return_pct": 31.5,
            "sales_training_days": 45,
            "return_training_days": 45,
        },
        "method": "weighted_fallback",
    }
    anomalies = {
        "summary": {"total": 2, "critical": 1, "high": 1, "medium": 0},
        "items": [
            {"severity": "Critical", "alert_type": "Sales + Return Spike", "style_color": "23ssnm001-pink", "reason": "Sales and returns rose together."}
        ],
    }

    return [
        patch("backend.routers.assistant.get_settings", return_value=NO_AI_SETTINGS),
        patch("backend.routers.assistant.sales.sales_kpis", return_value=kpis),
        patch("backend.routers.assistant.sales.top_products", return_value=top_products),
        patch("backend.routers.assistant.sales.marketplace_summary", return_value=marketplace_rows),
        patch("backend.routers.assistant.sales.sales_by_category", return_value=[]),
        patch("backend.routers.assistant.sales.sales_trend", return_value=[]),
        patch("backend.routers.assistant.sales._sales_rows", return_value=sales_rows),
        patch("backend.routers.assistant.sales._return_rows", return_value=return_rows),
        patch("backend.routers.assistant.inventory.inventory_kpis", return_value={"total_inventory": 222356, "total_styles": 1923, "oos_count": 125}),
        patch("backend.routers.assistant.inventory.inventory_styles", return_value={"items": []}),
        patch("backend.routers.assistant.inventory.category_status_matrix", return_value=[]),
        patch("backend.routers.assistant.inventory.replenishment_plan", return_value=replenishment),
        patch("backend.routers.assistant.categories.potential_noos", return_value={"items": []}),
        patch("backend.routers.assistant.ads.pla_performance", return_value=[{"spend": 100000, "revenue": 450000}]),
        patch("backend.routers.assistant.regional.state_heatmap", return_value=[]),
        patch("backend.routers.assistant.forecast.sales_returns_forecast", return_value=forecast),
        patch("backend.routers.assistant.alerts.anomaly_alerts", return_value=anomalies),
    ]


class _PatchStack:
    def __enter__(self):
        self._patches = _assistant_source_patches()
        for item in self._patches:
            item.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        for item in reversed(self._patches):
            item.__exit__(exc_type, exc, tb)


def test_advisory_sales_prompt_routes_to_business_analysis_with_recommendations() -> None:
    with _PatchStack():
        response = TestClient(app).post(
            "/api/assistant/chat",
            json={"message": "give me 3 suggestion how can improve my sale and reduce my return", "conversation_history": []},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "business_analysis"
    assert payload["recommendations"]
    assert len(payload["recommendations"]) >= 3
    assert payload["summary_cards"]
    assert "AI Assistant not configured" not in payload["answer"]
    assert payload["answer"] != "Sales are Rs 25,882,235.53 on 22141 units. Return rate is 33.97%."
    assert all(item.get("evidence") and item.get("next_step") for item in payload["recommendations"])


def test_explicit_sales_kpi_report_still_returns_sales_report_tables() -> None:
    with _PatchStack():
        response = TestClient(app).post(
            "/api/assistant/chat",
            json={"message": "show sales KPI report", "conversation_history": []},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "sales_report"
    assert [table["title"] for table in payload["tables"]][:1] == ["Sales KPI summary"]
    assert payload["recommendations"] == []


def test_sku_specific_question_still_returns_sku_lookup() -> None:
    with _PatchStack(), patch(
        "backend.routers.assistant.rows_or_demo",
        return_value=[
            {
                "style_color": "23ssnm001-pink",
                "total_inventory": 0,
                "category_new": "NOOS",
                "inventory_status": "OOS",
            }
        ],
    ):
        response = TestClient(app).post(
            "/api/assistant/chat",
            json={"message": "show 23ssnm001-pink performance", "conversation_history": []},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "sku_lookup"
    assert payload["tables"][0]["title"] == "SKU performance summary"
    assert "23ssnm001-pink" in payload["answer"]
