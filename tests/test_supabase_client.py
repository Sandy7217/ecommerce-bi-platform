from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.db import supabase_client


class FakeSettings:
    supabase_url = "https://example.supabase.co"
    supabase_service_key = "service-key"
    has_supabase = True


class FakeResponse:
    def __init__(self, rows: list[dict], content_range: str) -> None:
        self._rows = rows
        self.headers = {"content-range": content_range}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict]:
        return self._rows


class SupabaseClientTest(unittest.TestCase):
    def tearDown(self) -> None:
        supabase_client._clear_select_cache()

    def test_select_all_uses_stable_default_order_for_paginated_tables(self) -> None:
        calls: list[dict] = []

        def fake_get(_url: str, *, params: list[tuple[str, str]], headers: dict, timeout: int) -> FakeResponse:
            del timeout
            calls.append({"params": params, "headers": headers})
            if headers["Range"] == "0-1":
                return FakeResponse([{"id": 1}, {"id": 2}], "0-1/3")
            return FakeResponse([{"id": 3}], "2-2/3")

        with patch("backend.db.supabase_client.get_settings", return_value=FakeSettings()), patch(
            "backend.db.supabase_client.httpx.get",
            side_effect=fake_get,
        ):
            rows = supabase_client.table_select_all("sales_fact", columns="id,date", page_size=2, max_rows=10)

        self.assertEqual(rows, [{"id": 1}, {"id": 2}, {"id": 3}])
        self.assertTrue(calls)
        for call in calls:
            self.assertIn(("order", "date.asc,id.asc"), call["params"])


if __name__ == "__main__":
    unittest.main()
