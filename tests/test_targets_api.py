from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
try:
    from backend.security import CurrentUser, get_current_user
except ImportError:  # pragma: no cover - older app versions do not protect API routers in tests.
    CurrentUser = None  # type: ignore[assignment]
    get_current_user = None  # type: ignore[assignment]


TARGET_ROW = {"id": 1, "month": "2026-05-01", "channel": "ALL", "target_value": 50000000, "target_qty": 0}


def _test_user() -> CurrentUser:
    assert CurrentUser is not None
    return CurrentUser(user_id="test-user", email="test@example.com", role="super_admin", is_active=True)


class TargetsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        if get_current_user is not None:
            app.dependency_overrides[get_current_user] = _test_user

    def tearDown(self) -> None:
        if get_current_user is not None:
            app.dependency_overrides.pop(get_current_user, None)

    def test_get_targets_for_month(self) -> None:
        with patch("backend.routers.targets.table_select_all", return_value=[TARGET_ROW]):
            response = TestClient(app).get("/api/targets", params={"month": "2026-05"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["month"], "2026-05-01")
        self.assertEqual(payload["items"][0]["target_value"], 50000000)
        self.assertFalse(payload["setup_required"])

    def test_get_targets_uses_default_when_table_missing(self) -> None:
        with patch("backend.routers.targets.table_select_all", side_effect=Exception("PGRST205 Could not find the table 'public.targets'")):
            response = TestClient(app).get("/api/targets", params={"month": "2026-05"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["setup_required"])
        self.assertEqual(payload["items"][0]["channel"], "ALL")
        self.assertEqual(payload["items"][0]["target_value"], 50000000)

    def test_post_upserts_month_target(self) -> None:
        calls: list[tuple[str, list[dict], str | None]] = []

        def fake_upsert(table: str, rows: list[dict], on_conflict: str | None = None, **_kwargs):
            calls.append((table, rows, on_conflict))
            return len(rows)

        with patch("backend.routers.targets.table_upsert", side_effect=fake_upsert), patch(
            "backend.routers.targets.table_select_all",
            return_value=[TARGET_ROW],
        ):
            response = TestClient(app).post(
                "/api/targets",
                json={"month": "2026-05", "channel": "ALL", "target_value": 50000000, "target_qty": 0},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls[0][0], "targets")
        self.assertEqual(calls[0][2], "month,channel")
        self.assertEqual(response.json()["target_value"], 50000000)


if __name__ == "__main__":
    unittest.main()
