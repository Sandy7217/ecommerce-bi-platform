from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routers import admin, ads, alerts, assistant, categories, forecast, inventory, notifications, regional, reports, returns, sales, targets, upload
from backend.security import ADMIN_ROLES, ALL_ROLES, require_roles


settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router, roles in (
    (sales.router, ALL_ROLES),
    (inventory.router, ALL_ROLES),
    (categories.router, ALL_ROLES),
    (ads.router, ALL_ROLES),
    (alerts.router, ALL_ROLES),
    (returns.router, ALL_ROLES),
    (regional.router, ALL_ROLES),
    (reports.router, ALL_ROLES),
    (forecast.router, ALL_ROLES),
    (targets.router, ADMIN_ROLES),
    (assistant.router, ALL_ROLES),
    (notifications.router, ALL_ROLES),
    (upload.router, ADMIN_ROLES),
    (admin.router, ADMIN_ROLES),
):
    app.include_router(router, prefix=settings.api_prefix, dependencies=[Depends(require_roles(*roles))])


@app.get("/")
def root():
    return {"app": settings.app_name, "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "supabase_configured": settings.has_supabase}
