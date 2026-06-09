from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.reports import _csv_bytes
from backend.security import CurrentUser, require_roles
from backend.services.export_safety import safe_cell


client = TestClient(app)


@pytest.mark.no_auth_override
def test_health_stays_public() -> None:
    response = client.get("/health")

    assert response.status_code == 200


@pytest.mark.no_auth_override
def test_admin_route_requires_bearer_token() -> None:
    response = client.get("/api/admin/users")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_role_dependency_rejects_lower_role() -> None:
    dependency = require_roles("super_admin", "admin")

    with pytest.raises(HTTPException) as exc:
        dependency(CurrentUser(user_id="u1", email="viewer@example.com", role="viewer", is_active=True))

    assert exc.value.status_code == 403


def test_role_dependency_accepts_allowed_role() -> None:
    dependency = require_roles("super_admin", "admin")

    user = dependency(CurrentUser(user_id="u1", email="admin@example.com", role="admin", is_active=True))

    assert user.role == "admin"


@pytest.mark.no_auth_override
def test_cors_rejects_unowned_vercel_origin() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://attacker-controlled.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers.get("access-control-allow-origin") != "https://attacker-controlled.vercel.app"


@pytest.mark.no_auth_override
def test_cors_allows_owned_vercel_origin() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://ecommerce-bi-platform.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers.get("access-control-allow-origin") == "https://ecommerce-bi-platform.vercel.app"


def test_export_cells_escape_spreadsheet_formulas() -> None:
    assert safe_cell("=HYPERLINK(\"https://example.com\")").startswith("'=")

    payload = _csv_bytes(["Style"], [["=HYPERLINK(\"https://example.com\")"]]).decode("utf-8-sig")

    assert "'=HYPERLINK" in payload


def test_next_backend_proxy_uses_cookie_token_not_client_authorization() -> None:
    source = Path("frontend/app/api/backend/[...path]/route.ts").read_text()

    assert 'forwardedRequestHeaders = new Set(["accept", "content-type"])' in source
    assert 'nextHeaders.set("Authorization", `Bearer ${accessToken}`)' in source
    assert "ACCESS_COOKIE" in source
    assert "REFRESH_COOKIE" in source
    assert "refreshSession" in source
    assert "response.status === 401" in source


def test_server_rendered_dashboard_fetches_use_cookie_session_token() -> None:
    source = Path("frontend/lib/server-api.ts").read_text()
    executive_page = Path("frontend/app/(dashboard)/page.tsx").read_text()
    sales_page = Path("frontend/app/(dashboard)/sales/page.tsx").read_text()

    assert "ACCESS_COOKIE" in source
    assert "REFRESH_COOKIE" in source
    assert 'import { cache } from "react"' in source
    assert "Authorization" in source
    assert "refreshSession" in source
    assert "response.status === 401" in source
    assert "serverApiGet" in executive_page
    assert "serverApiGet" in sales_page


def test_public_demo_route_is_explicit_and_dashboard_auth_remains() -> None:
    source = Path("frontend/middleware.ts").read_text()

    assert 'const PUBLIC_ROUTES = ["/login", "/demo"]' in source
    assert "pathname.startsWith(`${route}/`)" in source
    assert "!isPublicRoute" in source
    assert 'NextResponse.redirect(new URL("/login", request.url))' in source
