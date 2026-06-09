from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.main import app

try:
    from backend.security import CurrentUser, get_current_user
except ImportError:  # pragma: no cover - older app versions do not protect API routers in tests.
    CurrentUser = None  # type: ignore[assignment]
    get_current_user = None  # type: ignore[assignment]


def _test_user() -> CurrentUser:
    assert CurrentUser is not None
    return CurrentUser(user_id="test-user", email="test@example.com", role="super_admin", is_active=True)


def _sales_row(day: str, channel: str, value: float, qty: int = 1, source: str = "myntra_orders") -> dict:
    return {
        "date": day,
        "channel": channel,
        "marketplace": channel,
        "selling_price": value / qty,
        "qty": qty,
        "source": source,
    }


def _return_row(day: str, channel: str, value: float, qty: int = 1) -> dict:
    return {"date": day, "channel": channel, "return_value": value, "qty": qty}


def _rows_for(table: str, **kwargs):
    filters = dict(kwargs.get("filters") or [])
    if table == "sales_fact":
        if filters.get("date") == "eq.2026-05-23":
            return [
                _sales_row("2026-05-23", "MYNTRAPPMP", 1000, 2),
                _sales_row("2026-05-23", "MYNTRASJIT", 900, 1),
                _sales_row("2026-05-23", "AJIO_DROPSHIP", 600, 1, source="sales_master"),
            ]
        return [
            _sales_row("2026-05-01", "MYNTRAPPMP", 3000, 3),
            _sales_row("2026-05-23", "MYNTRAPPMP", 1000, 2),
            _sales_row("2026-05-23", "MYNTRASJIT", 900, 1),
            _sales_row("2026-05-23", "AJIO_DROPSHIP", 600, 1, source="sales_master"),
        ]
    if table == "returns_fact":
        if filters.get("date") == "eq.2026-05-23":
            return [_return_row("2026-05-23", "MYNTRAPPMP", 500, 1)]
        return [_return_row("2026-05-23", "MYNTRAPPMP", 500, 1), _return_row("2026-05-05", "AJIO_DROPSHIP", 100, 1)]
    if table == "targets":
        return [{"id": 1, "month": "2026-05-01", "channel": "ALL", "target_value": 50000000, "target_qty": 0}]
    return []


def _rows_without_targets_table(table: str, **kwargs):
    if table == "targets":
        raise Exception("PGRST205 Could not find the table 'public.targets'")
    return _rows_for(table, **kwargs)


def _rows_with_small_target(table: str, **kwargs):
    if table == "targets":
        return [{"id": 2, "month": "2026-05-01", "channel": "ALL", "target_value": 10000, "target_qty": 0}]
    return _rows_for(table, **kwargs)


def _rows_with_uniware_ppmp(table: str, **kwargs):
    if table == "sales_fact":
        return [
            _sales_row("2026-05-25", "MYNTRAPPMP", 2000, 2, source="unicommerce"),
            _sales_row("2026-05-25", "MYNTRAPPMP", 1000, 1, source="myntra_orders"),
            _sales_row("2026-05-25", "MYNTRASJIT", 3000, 3, source="myntra_orders"),
            _sales_row("2026-05-25", "AJIO_DROPSHIP", 500, 1, source="unicommerce"),
        ]
    if table == "returns_fact":
        return []
    if table == "targets":
        return [{"id": 1, "month": "2026-05-01", "channel": "ALL", "target_value": 50000000, "target_qty": 0}]
    return []


def _rows_with_mtd_ppmp_sources(table: str, **kwargs):
    if table == "sales_fact":
        return [
            _sales_row("2026-05-24", "MYNTRAPPMP", 4000, 4, source="myntra_orders"),
            _sales_row("2026-05-24", "MYNTRAPPMP", 2000, 2, source="sales_master"),
            _sales_row("2026-05-25", "MYNTRAPPMP", 2000, 2, source="unicommerce"),
            _sales_row("2026-05-25", "MYNTRAPPMP", 1000, 1, source="myntra_orders"),
            _sales_row("2026-05-25", "MYNTRASJIT", 3000, 3, source="myntra_orders"),
        ]
    if table == "returns_fact":
        return []
    if table == "targets":
        return [{"id": 1, "month": "2026-05-01", "channel": "ALL", "target_value": 50000000, "target_qty": 0}]
    return []


class DsrReportTest(unittest.TestCase):
    def setUp(self) -> None:
        if get_current_user is not None:
            app.dependency_overrides[get_current_user] = _test_user

    def tearDown(self) -> None:
        if get_current_user is not None:
            app.dependency_overrides.pop(get_current_user, None)

    def test_dsr_endpoint_calculates_daily_mtd_and_target(self) -> None:
        with patch("backend.services.dsr_report.table_select_all", side_effect=_rows_for):
            response = TestClient(app).get("/api/reports/dsr", params={"date": "2026-05-23"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["date"], "2026-05-23")
        platforms = [row["platform"] for row in payload["daily"]["rows"]]
        self.assertIn("MYNTRAPPMP", platforms)
        self.assertIn("MYNTRA SJIT", platforms)
        myntra = next(row for row in payload["daily"]["rows"] if row["platform"] == "MYNTRAPPMP")
        self.assertEqual(myntra["sale_qty"], 2)
        self.assertEqual(myntra["return_qty"], 1)
        self.assertEqual(myntra["net_sale_qty"], 1)
        self.assertEqual(myntra["net_sale_value"], 500)
        self.assertEqual(payload["target"]["target_value"], 50000000)
        self.assertGreater(payload["target"]["achieved_pct"], 0)

    def test_dsr_endpoint_uses_default_target_when_table_missing(self) -> None:
        with patch("backend.services.dsr_report.table_select_all", side_effect=_rows_without_targets_table):
            response = TestClient(app).get("/api/reports/dsr", params={"date": "2026-05-23"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["target"]["target_value"], 50000000)
        self.assertEqual(payload["target"]["channel"], "ALL")
        self.assertGreater(payload["target"]["achieved_pct"], 0)

    def test_dsr_target_achievement_uses_mtd_sale_value(self) -> None:
        with patch("backend.services.dsr_report.table_select_all", side_effect=_rows_with_small_target):
            response = TestClient(app).get("/api/reports/dsr", params={"date": "2026-05-23"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mtd"]["total"]["sale_value"], 5500)
        self.assertEqual(payload["mtd"]["total"]["net_sale_value"], 4900)
        self.assertEqual(payload["target"]["target_value"], 10000)
        self.assertEqual(payload["target"]["achieved_pct"], 55.0)

    def test_dsr_prefers_uniware_ppmp_and_direct_myntra_sjit(self) -> None:
        with patch("backend.services.dsr_report.table_select_all", side_effect=_rows_with_uniware_ppmp):
            response = TestClient(app).get("/api/reports/dsr", params={"date": "2026-05-25"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ppmp = next(row for row in payload["daily"]["rows"] if row["platform"] == "MYNTRAPPMP")
        sjit = next(row for row in payload["daily"]["rows"] if row["platform"] == "MYNTRA SJIT")
        self.assertEqual(ppmp["sale_qty"], 2)
        self.assertEqual(ppmp["sale_value"], 2000)
        self.assertEqual(sjit["sale_qty"], 3)
        self.assertEqual(payload["daily"]["total"]["sale_qty"], 6)

    def test_dsr_mtd_ppmp_source_priority_is_per_date(self) -> None:
        with patch("backend.services.dsr_report.table_select_all", side_effect=_rows_with_mtd_ppmp_sources):
            response = TestClient(app).get("/api/reports/dsr", params={"date": "2026-05-25"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ppmp = next(row for row in payload["mtd"]["rows"] if row["platform"] == "MYNTRAPPMP")
        self.assertEqual(ppmp["sale_qty"], 6)
        self.assertEqual(ppmp["sale_value"], 6000)
        self.assertEqual(payload["mtd"]["total"]["sale_qty"], 9)

    def test_dsr_excel_download_uses_reference_layout(self) -> None:
        with patch("backend.services.dsr_report.table_select_all", side_effect=_rows_for):
            response = TestClient(app).get("/api/reports/dsr/download", params={"date": "2026-05-23", "format": "excel"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        workbook = load_workbook(BytesIO(response.content))
        sheet = workbook.active
        self.assertEqual(sheet["A1"].value, "NAYAM BY LAKSHITA")
        self.assertEqual(sheet["A3"].value, "DSR")
        self.assertEqual(sheet["C3"].value, "Daily Sale & Return Summary")
        self.assertEqual(sheet["A4"].value, "Date")
        self.assertEqual(sheet["B4"].value, "Platform")
        self.assertEqual(sheet["M4"].value, "Target")
        self.assertEqual(sheet["B7"].value, "MYNTRA SJIT")

    def test_dsr_png_download_returns_image(self) -> None:
        with patch("backend.services.dsr_report.table_select_all", side_effect=_rows_for):
            response = TestClient(app).get("/api/reports/dsr/download", params={"date": "2026-05-23", "format": "png"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
