from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.anomaly_engine import build_anomaly_alerts


TODAY = date(2026, 5, 24)


def _sales_rows() -> list[dict]:
    return [
        *[
            {"date": "2026-05-20", "style_color": "nm001-red", "selling_price": 1000, "qty": 2}
            for _ in range(5)
        ],
        {"date": "2026-05-10", "style_color": "nm001-red", "selling_price": 1000, "qty": 2},
        {"date": "2026-05-21", "style_color": "nm002-yellow", "selling_price": 800, "qty": 1},
        {"date": "2026-05-11", "style_color": "nm002-yellow", "selling_price": 800, "qty": 2},
    ]


def _return_rows() -> list[dict]:
    return [
        {"date": "2026-05-21", "style_color": "nm001-red", "return_value": 1000, "qty": 4},
        {"date": "2026-05-10", "style_color": "nm001-red", "return_value": 1000, "qty": 1},
    ]


def _sku_rows() -> list[dict]:
    return [
        {"style_color": "nm001-red", "category_new": "Red", "inventory_status": "INSTOCK", "total_inventory": 500, "ros_30d": 2.0},
        {"style_color": "nm002-yellow", "category_new": "Yellow", "inventory_status": "BROKEN", "total_inventory": 200, "ros_30d": 0.5},
        {"style_color": "nm005-yellow", "category_new": "Yellow", "inventory_status": "INSTOCK", "total_inventory": 80, "ros_30d": 0.2},
        {"style_color": "nm003-noos", "category_new": "NOOS(Green)", "inventory_status": "INSTOCK", "total_inventory": 900, "ros_30d": 8.0},
        {"style_color": "nm004-green", "category_new": "Green", "inventory_status": "INSTOCK", "total_inventory": 300, "ros_30d": 3.0},
    ]


def _inventory_rows() -> list[dict]:
    return [
        {"snapshot_date": "2026-05-09", "style_color": "nm001-red", "size": "M", "qty": 100},
        {"snapshot_date": "2026-05-09", "style_color": "nm002-yellow", "size": "M", "qty": 100},
        {"snapshot_date": "2026-05-09", "style_color": "nm003-noos", "size": "M", "qty": 500},
        {"snapshot_date": "2026-05-24", "style_color": "nm001-red", "size": "M", "qty": 500},
        {"snapshot_date": "2026-05-24", "style_color": "nm002-yellow", "size": "M", "qty": 200},
        {"snapshot_date": "2026-05-24", "style_color": "nm005-yellow", "size": "M", "qty": 80},
        {"snapshot_date": "2026-05-24", "style_color": "nm003-noos", "size": "M", "qty": 900},
        {"snapshot_date": "2026-05-24", "style_color": "nm004-green", "size": "M", "qty": 300},
    ]


class AnomalyAlertsTest(unittest.TestCase):
    def test_builds_style_and_category_anomaly_alerts(self) -> None:
        alerts = build_anomaly_alerts(
            sales_rows=_sales_rows(),
            return_rows=_return_rows(),
            sku_rows=_sku_rows(),
            inventory_rows=_inventory_rows(),
            today=TODAY,
        )

        alert_keys = {(row["alert_type"], row.get("style_color") or row.get("category")) for row in alerts}
        self.assertIn(("Sales + Return Spike", "nm001-red"), alert_keys)
        self.assertIn(("Overstock Risk", "nm001-red"), alert_keys)
        self.assertIn(("Category Inventory Depth Increase", "Red"), alert_keys)
        self.assertIn(("Category SKU Count Change", "Yellow"), alert_keys)
        self.assertNotIn(("Category Inventory Depth Increase", "NOOS(Green)"), alert_keys)
        self.assertNotIn(("Category SKU Count Change", "Green"), alert_keys)

        combined = next(row for row in alerts if row["alert_type"] == "Sales + Return Spike")
        self.assertEqual(combined["severity"], "Critical")
        self.assertGreater(combined["sales_delta_pct"], 100)
        self.assertGreater(combined["return_delta_pct"], 100)

    def test_api_filters_and_report_download_include_anomaly_alerts(self) -> None:
        def rows_for(table: str, **_kwargs):
            if table == "sales_fact":
                return _sales_rows()
            if table == "returns_fact":
                return _return_rows()
            if table == "sku_master":
                return _sku_rows()
            if table == "inventory_fact":
                return _inventory_rows()
            return []

        with patch("backend.routers.alerts.table_select_all", side_effect=rows_for):
            response = TestClient(app).get("/api/alerts/anomalies", params={"severity": "Critical"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["summary"]["critical"], 1)
        self.assertTrue(all(row["severity"] == "Critical" for row in data["items"]))

        with patch("backend.routers.reports.table_select_all", side_effect=rows_for):
            download = TestClient(app).get(
                "/api/reports/download",
                params={"type": "anomaly_alerts", "format": "csv"},
            )

        self.assertEqual(download.status_code, 200)
        self.assertIn("anomaly-alerts-report.csv", download.headers["content-disposition"])
        self.assertIn("Severity,Alert Type,Scope,Style/Category,Category,Status", download.text)
        self.assertIn("Sales + Return Spike", download.text)


if __name__ == "__main__":
    unittest.main()
