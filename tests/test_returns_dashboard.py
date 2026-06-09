from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class ReturnsDashboardTest(unittest.TestCase):
    def test_high_return_styles_include_sales_inventory_return_rate_and_grade(self) -> None:
        def select_all(table: str, **kwargs):
            del kwargs
            if table == "returns_fact":
                return [
                    {"date": "2026-05-04", "style_color": "high-return", "return_value": 400, "qty": 4},
                    {"date": "2026-05-04", "style_color": "lower-return", "return_value": 100, "qty": 1},
                ]
            if table == "sales_fact":
                return [
                    {"date": "2026-05-03", "style_color": "high-return", "selling_price": 100, "qty": 10, "source": "myntra_orders"},
                    {"date": "2026-05-03", "style_color": "lower-return", "selling_price": 100, "qty": 5, "source": "myntra_orders"},
                    {"date": "2026-05-03", "style_color": "high-return", "selling_price": 100, "qty": 99, "source": "unicommerce", "channel": "MYNTRAPPMP"},
                ]
            if table == "sku_master":
                return [
                    {"style_color": "high-return", "total_inventory": 25, "sale_grade_old": "NOOS"},
                    {"style_color": "lower-return", "total_inventory": 8, "sale_grade_old": "Red"},
                ]
            return []

        with patch("backend.routers.returns.table_select_all", side_effect=select_all):
            response = TestClient(app).get(
                "/api/returns/high_return_skus",
                params={"from_date": "2026-05-01", "to_date": "2026-05-31"},
            )

        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(rows[0]["style_color"], "high-return")
        self.assertEqual(rows[0]["return_qty"], 4)
        self.assertEqual(rows[0]["sales_qty"], 10)
        self.assertEqual(rows[0]["inventory"], 25)
        self.assertEqual(rows[0]["sale_grade"], "NOOS")
        self.assertEqual(rows[0]["return_pct"], 40)
        self.assertEqual(rows[0]["share"], 80)
