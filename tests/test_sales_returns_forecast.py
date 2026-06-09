from __future__ import annotations

from datetime import date, timedelta
import unittest

from fastapi.testclient import TestClient

from backend.main import app
from backend.security import CurrentUser, get_current_user
from backend.services.forecasting import _combined_method, aggregate_daily_sales, build_sales_returns_forecast


def _sales_row(day: date, value: float, qty: int = 10, source: str = "sales_master", channel: str = "MYNTRAPPMP") -> dict:
    return {
        "date": day.isoformat(),
        "selling_price": value / qty,
        "qty": qty,
        "source": source,
        "channel": channel,
        "marketplace": channel,
    }


def _return_row(day: date, value: float, qty: int = 1, source: str = "returns") -> dict:
    return {
        "date": day.isoformat(),
        "return_value": value,
        "qty": qty,
        "source": source,
        "channel": "MYNTRAPPMP",
    }


class SalesReturnsForecastTest(unittest.TestCase):
    def test_forecast_uses_completed_history_instead_of_partial_current_day(self) -> None:
        today = date(2026, 5, 24)
        sales_rows = [
            _sales_row(today - timedelta(days=offset), 100000.0 + offset * 500, qty=100)
            for offset in range(1, 22)
        ]
        sales_rows.append(_sales_row(today, 12000.0, qty=12))
        return_rows = [
            _return_row(today - timedelta(days=offset), 12000.0 + offset * 100, qty=12)
            for offset in range(1, 22)
        ]

        result = build_sales_returns_forecast(sales_rows, return_rows, today=today, horizon_days=30)

        self.assertEqual(result["summary"]["excluded_current_day"], today.isoformat())
        self.assertEqual(result["summary"]["as_of_date"], (today - timedelta(days=1)).isoformat())
        self.assertEqual(result["summary"]["forecast_start_date"], today.isoformat())
        self.assertGreater(result["forecast"][0]["sales_value"], 85000)
        self.assertGreater(result["summary"]["forecast_sales_value"], 2_500_000)
        self.assertGreater(result["forecast"][0]["return_value"], 9000)
        self.assertGreater(result["summary"]["forecast_return_value"], 250_000)

    def test_myntra_source_priority_is_applied_per_date(self) -> None:
        first_day = date(2026, 5, 1)
        second_day = date(2026, 5, 2)
        rows = [
            _sales_row(first_day, 100000, source="sales_master", channel="MYNTRAPPMP"),
            _sales_row(first_day, 80000, source="unicommerce", channel="MYNTRAPPMP"),
            _sales_row(second_day, 100000, source="sales_master", channel="MYNTRAPPMP"),
            _sales_row(second_day, 300000, source="myntra_orders", channel="Myntra"),
            _sales_row(second_day, 50000, source="sales_master", channel="AJIO_DROPSHIP"),
        ]

        daily = {row["date"]: row for row in aggregate_daily_sales(rows)}

        self.assertEqual(daily[first_day.isoformat()]["sales_value"], 80000)
        self.assertEqual(daily[second_day.isoformat()]["sales_value"], 350000)

    def test_sales_master_is_only_used_when_unicommerce_myntra_is_not_available(self) -> None:
        day = date(2026, 5, 1)
        fallback_day = date(2026, 5, 2)
        rows = [
            _sales_row(day, 100000, source="sales_master", channel="MYNTRAPPMP"),
            _sales_row(day, 80000, source="unicommerce", channel="MYNTRAPPMP"),
            _sales_row(day, 50000, source="sales_master", channel="AJIO_DROPSHIP"),
            _sales_row(fallback_day, 120000, source="sales_master", channel="MYNTRAPPMP"),
        ]

        daily = {row["date"]: row for row in aggregate_daily_sales(rows)}

        self.assertEqual(daily[day.isoformat()]["sales_value"], 130000)
        self.assertEqual(daily[fallback_day.isoformat()]["sales_value"], 120000)

    def test_endpoint_returns_sales_and_return_forecast(self) -> None:
        today = date(2026, 5, 24)
        sales_rows = [_sales_row(today - timedelta(days=offset), 100000.0, qty=100) for offset in range(1, 22)]
        return_rows = [_return_row(today - timedelta(days=offset), 10000.0, qty=10) for offset in range(1, 22)]

        def fake_select(table: str, **_kwargs):
            if table == "sales_fact":
                return sales_rows
            if table == "returns_fact":
                return return_rows
            return []

        from unittest.mock import patch

        app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id="test-user", email="test@example.com", role="admin", is_active=True)
        with patch("backend.routers.forecast.table_select_all", side_effect=fake_select), patch("backend.routers.forecast.date") as mocked_date:
            mocked_date.today.return_value = today
            mocked_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
            response = TestClient(app).get("/api/forecast/sales_returns")
        app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["forecast"]), 30)
        self.assertEqual(payload["training_window_days"], 730)
        self.assertEqual(payload["summary"]["training_requested_days"], 730)
        self.assertEqual(payload["summary"]["forecast_start_date"], today.isoformat())
        self.assertGreater(payload["summary"]["forecast_sales_value"], 2_500_000)
        self.assertGreater(payload["summary"]["forecast_return_value"], 250_000)

    def test_combined_method_reports_sarimax_when_any_metric_uses_sarimax(self) -> None:
        self.assertEqual(_combined_method({"sarimax"}), "sarimax")
        self.assertEqual(_combined_method({"sarimax", "baseline"}), "sarimax_with_baseline")
        self.assertEqual(_combined_method({"prophet", "sarimax"}), "prophet_sarimax")


if __name__ == "__main__":
    unittest.main()
