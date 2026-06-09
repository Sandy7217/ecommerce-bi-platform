from __future__ import annotations

import pytest

from backend.main import app
from backend.security import CurrentUser, get_current_user


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "no_auth_override: run the test without the default authenticated user override")


@pytest.fixture(autouse=True)
def authenticated_test_user(request: pytest.FixtureRequest):
    if request.node.get_closest_marker("no_auth_override"):
        app.dependency_overrides.pop(get_current_user, None)
        yield
        return

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="test-admin",
        email="admin@example.com",
        role="super_admin",
        is_active=True,
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)
